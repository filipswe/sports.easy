from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from .config import settings
from .crests import safe_crest
from .db import now, utc
from .leagues import BY_SPORT, LEAGUES
from .model import VERSION, outcome_won, predict
from .models import (
    Bookmaker,
    Competition,
    Fixture,
    IngestionRun,
    ModelVersion,
    Prediction,
    ProviderMapping,
    Publication,
    Quote,
    Settlement,
    Team,
)
from .providers import (
    APIFootball,
    DemoFootball,
    DemoOdds,
    FootballData,
    ProviderUnavailable,
    TheOddsAPI,
    fingerprint,
    match_fixture,
    parse_time,
)


def ensure_model(db):
    if not db.get(ModelVersion, VERSION):
        db.add(
            ModelVersion(
                id=VERSION,
                methodology={
                    "family": "regularized Poisson",
                    "half_life_days": 180,
                    "minimum_team_matches": 8,
                    "minimum_league_matches": 40,
                    "markets": ["1x2", "totals", "btts"],
                },
            )
        )
        db.flush()


def upsert_fixtures(db, records, mode, fetched):
    prefix = "demo" if mode == "demo" else settings.football_provider
    for item in records:
        comp_key = f"{prefix}:{item.get('league_id', settings.league_id)}:{item['season']}"
        comp = db.scalar(select(Competition).where(Competition.provider_id == comp_key))
        if not comp:
            comp = Competition(
                provider_id=comp_key,
                name=item.get("league_name", settings.league_name),
                season=item["season"],
                mode=mode,
            )
            db.add(comp)
            db.flush()
        ids = []
        for side in ["home", "away"]:
            t = item[side]
            key = f"{prefix}:{t['id']}"
            team = db.scalar(select(Team).where(Team.provider_id == key))
            if not team:
                team = Team(provider_id=key, name=t["name"])
                db.add(team)
                db.flush()
            crest = safe_crest(t.get("crest") or t.get("logo"))
            if crest:
                team.crest_url = crest
            ids.append(team.id)
        key = f"{prefix}:{item['id']}"
        fixture = db.scalar(select(Fixture).where(Fixture.provider_id == key))
        if not fixture:
            fixture = Fixture(
                provider_id=key, competition_id=comp.id, home_id=ids[0], away_id=ids[1], mode=mode
            )
            db.add(fixture)
        result_changed = (fixture.home_goals, fixture.away_goals) != (
            item["home_goals"],
            item["away_goals"],
        )
        for field in ["kickoff", "status", "venue", "home_goals", "away_goals"]:
            setattr(fixture, field, item[field])
        for field in ["home_half_goals", "away_half_goals"]:
            setattr(fixture, field, item.get(field))
        fixture.fetched_at = fetched
        fixture.provider_updated_at = item.get("provider_updated_at")
        if item["status"] == "finished" and (result_changed or fixture.result_available_at is None):
            # Live history first seen now cannot be pretended to have been available earlier.
            fixture.result_available_at = (
                item["kickoff"] + timedelta(hours=2) if mode == "demo" else fetched
            )
    db.flush()


def ingest(db):
    mode, fetched = settings.app_data_mode, now()
    ensure_model(db)
    if mode == "demo":
        existing = db.scalar(
            select(Fixture).where(Fixture.mode == "demo").order_by(Fixture.kickoff)
        )
        coverage = {
            c.provider_id.split(":")[1]
            for c in db.scalars(select(Competition).where(Competition.mode == "demo"))
        }
        if (
            existing
            and coverage >= {str(league.id) for league in LEAGUES}
            and db.scalar(
                select(Prediction.id)
                .where(Prediction.mode == "demo", Prediction.model_id == VERSION)
                .limit(1)
            )
        ):
            from .picks import publish_recommendations

            settle(db)
            publish_recommendations(db)
            db.commit()
            return {"status": "unchanged", "message": "Demo anchor and source ages preserved"}
        anchor = utc(existing.kickoff) + timedelta(days=280) if existing else fetched
        records = [f for league in LEAGUES for f in DemoFootball(anchor, league.id).fixtures()]
        events = DemoOdds(records, anchor).odds()
    else:
        if not settings.live_retention_approved:
            raise ProviderUnavailable(
                "Live ingestion disabled until retention/display terms are reviewed"
            )
        provider = FootballData if settings.football_provider == "football-data" else APIFootball
        records = provider(db).fixtures()
        events = []
    upsert_fixtures(db, records, mode, fetched)
    if mode == "live" and settings.football_provider == "football-data":
        from .team_aliases import install_football_data_aliases

        install_football_data_aliases(db)
    db.commit()
    prefix = "demo" if mode == "demo" else settings.football_provider
    fixtures = list(
        db.scalars(
            select(Fixture).where(
                Fixture.mode == mode, Fixture.provider_id.startswith(prefix + ":")
            )
        )
    )
    competitions = {c.id: c.provider_id.split(":")[1] for c in db.scalars(select(Competition))}
    histories = {}
    for f in fixtures:
        if f.status == "finished":
            histories.setdefault(competitions[f.competition_id], []).append(f)
    strength_cache = {}
    cutoff = now()
    for fixture in fixtures:
        if fixture.status != "scheduled" or utc(fixture.kickoff) <= fetched:
            continue
        league_history = histories.get(competitions[fixture.competition_id], [])
        hsh = fingerprint(
            [
                [(f.id, f.home_goals, f.away_goals, f.result_available_at) for f in league_history],
                fixture.kickoff,
                fetched.date(),
                VERSION,
            ]
        )
        if db.scalar(
            select(Prediction.id).where(
                Prediction.fixture_id == fixture.id, Prediction.input_hash == hsh
            )
        ):
            continue
        prediction = predict(
            league_history, fixture.home_id, fixture.away_id, cutoff, strength_cache=strength_cache
        )
        if prediction:
            if mode == "demo":
                prediction["quality"] = "Limited"
            db.add(
                Prediction(
                    fixture_id=fixture.id,
                    model_id=VERSION,
                    input_cutoff=cutoff,
                    history_fetched_at=max(utc(f.fetched_at) for f in league_history),
                    fixture_kickoff=fixture.kickoff,
                    mode=mode,
                    input_hash=hsh,
                    **prediction,
                )
            )
    db.commit()
    settle(db)
    db.commit()
    if mode == "live":
        events = TheOddsAPI(db).odds()
    rejected = store_odds(db, events, fetched=fetched)
    settle(db)
    db.add(
        IngestionRun(
            provider=mode,
            status="complete",
            detail={"fixtures": len(records), "unmatched_events": rejected},
        )
    )
    db.commit()
    from .picks import publish_recommendations

    publish_recommendations(db)
    db.commit()
    return {"fixtures": len(records), "unmatched_events": rejected, "mode": mode}


def store_odds(db, events, fetched=None):
    """Import recorded provider snapshots without fetching or refreshing their source age."""
    mode, fetched = settings.app_data_mode, fetched or now()
    prefix = "demo" if mode == "demo" else settings.football_provider
    fixtures = list(
        db.scalars(
            select(Fixture).where(
                Fixture.mode == mode, Fixture.provider_id.startswith(prefix + ":")
            )
        )
    )
    competitions = {c.id: c.provider_id.split(":")[1] for c in db.scalars(select(Competition))}
    teams = list(db.scalars(select(Team)))
    names = {}
    for t in teams:
        if t.provider_id.startswith(prefix + ":"):
            if t.name.casefold() in names:  # Duplicate identity names must not resolve.
                names[t.name.casefold()] = None
            else:
                names[t.name.casefold()] = t.id
    aliases = {
        m.external_id.casefold(): m.entity_id
        for m in db.scalars(
            select(ProviderMapping).where(
                ProviderMapping.provider == "the-odds-api", ProviderMapping.entity_type == "team"
            )
        )
    }
    rejected = 0
    for event in events:
        league = BY_SPORT.get(event.get("sport_key"))
        candidates = [
            f for f in fixtures if league and competitions[f.competition_id] == str(league.id)
        ]
        fixture = match_fixture(event, candidates, names, aliases)
        if not fixture or fixture.status != "scheduled" or utc(fixture.kickoff) <= now():
            rejected += 1
            continue
        for book in event.get("bookmakers", []):
            key = f"{mode}:{settings.odds_region}:{book['key']}"
            bookmaker = db.scalar(select(Bookmaker).where(Bookmaker.provider_id == key))
            if not bookmaker:
                bookmaker = Bookmaker(
                    provider_id=key, name=book["title"], region=settings.odds_region
                )
                db.add(bookmaker)
                db.flush()
            for market in book.get("markets", []):
                kind = {"h2h": "1x2", "totals": "totals", "btts": "btts"}.get(market["key"])
                if not kind or (mode == "live" and kind == "btts"):
                    continue
                updated = market.get("last_update") or book.get("last_update")
                stamp = parse_time(updated) if updated else None
                if stamp and stamp > fetched + timedelta(minutes=1):
                    continue
                snapshot = fingerprint([event["id"], book["key"], market, updated])
                for outcome in market["outcomes"]:
                    if kind == "totals" and outcome.get("point") != 2.5:
                        continue
                    selection = {
                        event["home_team"]: "home",
                        event["away_team"]: "away",
                        "Draw": "draw",
                        "Over": "over",
                        "Under": "under",
                        "Yes": "yes",
                        "No": "no",
                    }.get(outcome["name"])
                    price = Decimal(str(outcome["price"]))
                    if not selection or not price.is_finite() or not 1 < price <= 1000:
                        continue
                    quote = db.scalar(
                        select(Quote).where(
                            Quote.fixture_id == fixture.id,
                            Quote.bookmaker_id == bookmaker.id,
                            Quote.snapshot_key == snapshot,
                            Quote.market == kind,
                            Quote.outcome == selection,
                        )
                    )
                    if quote is None:
                        quote = Quote(
                            fixture_id=fixture.id,
                            bookmaker_id=bookmaker.id,
                            market=kind,
                            outcome=selection,
                            price=price,
                            snapshot_key=snapshot,
                            source_updated_at=stamp,
                            fetched_at=fetched,
                            mode=mode,
                        )
                        db.add(quote)
                        db.flush()
                    prediction = db.scalar(
                        select(Prediction)
                        .where(Prediction.fixture_id == fixture.id)
                        .order_by(Prediction.generated_at.desc())
                    )
                    if prediction and utc(prediction.generated_at) < utc(fixture.kickoff):
                        exists = db.scalar(
                            select(Publication.id).where(
                                Publication.prediction_id == prediction.id,
                                Publication.quote_id == quote.id,
                            )
                        )
                        if not exists:
                            db.add(Publication(prediction_id=prediction.id, quote_id=quote.id))
    return rejected


def settle(db):
    records = db.execute(
        select(Publication, Quote, Fixture)
        .join(Quote, Publication.quote_id == Quote.id)
        .join(Fixture, Quote.fixture_id == Fixture.id)
        .where(Fixture.mode == settings.app_data_mode)
    ).all()
    for pub, quote, fixture in records:
        if (
            fixture.status == "finished"
            and fixture.home_goals is not None
            and fixture.away_goals is not None
        ):
            result = (
                "won"
                if outcome_won(quote.market, quote.outcome, fixture.home_goals, fixture.away_goals)
                else "lost"
            )
            reason = (
                "Verified provider regulation-time result"
                if fixture.mode == "live"
                else "Synthetic demo result"
            )
        elif fixture.status in ["cancelled", "abandoned"]:
            result, reason = (
                "void",
                "Research policy: cancelled/abandoned fixtures are void; bookmaker rules may differ",
            )
        elif fixture.status == "postponed":
            result, reason = "postponed", "Await rescheduled verified result; no return counted"
        else:
            continue
        signature = f"{fixture.status}:{fixture.home_goals}:{fixture.away_goals}"
        previous = db.scalar(
            select(Settlement)
            .where(Settlement.publication_id == pub.id)
            .order_by(Settlement.recorded_at.desc())
        )
        if previous and previous.result_signature.split("|")[0] == signature:
            continue
        # Repeated signatures after corrections still get their own audited revision.
        if previous:
            signature += "|" + previous.id
        db.add(
            Settlement(
                publication_id=pub.id,
                result=result,
                result_signature=signature,
                reason=reason,
                supersedes_id=previous.id if previous else None,
            )
        )
