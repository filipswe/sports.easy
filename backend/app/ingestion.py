from datetime import timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from .config import settings
from .crests import safe_crest
from .db import now, utc
from .leagues import BY_SPORT, EUROPEAN_COMPETITIONS, LEAGUES
from .model import VERSION, market_probabilities, outcome_won, predict
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
    QuoteObservation,
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
        result_changed = result_changed or (fixture.home_half_goals, fixture.away_half_goals) != (
            item.get("home_half_goals"),
            item.get("away_half_goals"),
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


def upsert_european_events(db, events, fetched):
    """Real bookmaker event identities, without inventing regulation results or training data."""
    existing_teams = list(db.scalars(select(Team)))
    aliases = {
        m.external_id.casefold(): m.entity_id
        for m in db.scalars(
            select(ProviderMapping).where(
                ProviderMapping.provider == "the-odds-api", ProviderMapping.entity_type == "team"
            )
        )
    }
    active = set()
    for event in events:
        league = BY_SPORT.get(event.get("sport_key"))
        if league not in EUROPEAN_COMPETITIONS:
            continue
        kickoff = parse_time(event["commence_time"])
        if not fetched < kickoff <= fetched + timedelta(days=14):
            continue
        key = f"the-odds-api:{league.id}:{settings.season}"
        comp = db.scalar(select(Competition).where(Competition.provider_id == key))
        if comp is None:
            comp = Competition(
                provider_id=key, name=league.name, season=settings.season, mode="live"
            )
            db.add(comp)
            db.flush()
        teams = []
        for side in ("home_team", "away_team"):
            name = event[side]
            candidates = [
                t
                for t in existing_teams
                if t.provider_id.startswith(settings.football_provider + ":")
                and t.name.casefold() == name.casefold()
            ]
            team = (
                db.get(Team, aliases[name.casefold()])
                if name.casefold() in aliases
                else candidates[0]
                if len(candidates) == 1
                else None
            )
            if team is None:
                team_key = "the-odds-api:" + fingerprint(name.casefold())[:40]
                team = db.scalar(select(Team).where(Team.provider_id == team_key))
                if team is None:
                    team = Team(provider_id=team_key, name=name)
                    db.add(team)
                    db.flush()
            teams.append(team.id)
        key = "the-odds-api:" + event["id"]
        active.add(key)
        fixture = db.scalar(select(Fixture).where(Fixture.provider_id == key))
        if fixture is None:
            fixture = Fixture(
                provider_id=key,
                competition_id=comp.id,
                home_id=teams[0],
                away_id=teams[1],
                mode="live",
            )
            db.add(fixture)
        elif (fixture.home_id, fixture.away_id) != tuple(teams):
            fixture.status = "unconfirmed"
            continue
        fixture.kickoff, fixture.status, fixture.fetched_at = kickoff, "scheduled", fetched
    # Missing events are unavailable, not fabricated cancellations or final scores.
    for fixture in db.scalars(
        select(Fixture).where(
            Fixture.provider_id.startswith("the-odds-api:"),
            Fixture.kickoff > fetched,
            Fixture.kickoff <= fetched + timedelta(days=14),
        )
    ):
        if fixture.provider_id not in active:
            fixture.status = "unconfirmed"
    db.flush()


def odds_refresh_due(db, at=None):
    at = at or now()
    scope = f"odds-refresh:{settings.odds_region}:{settings.odds_bookmaker_key}"
    latest = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.provider == scope, IngestionRun.status == "complete")
        .order_by(IngestionRun.created_at.desc())
    )
    return latest is None or (at - utc(latest.created_at)).total_seconds() >= max(
        60, settings.odds_poll_seconds
    )


def refresh_odds(db):
    """Explicit operator refresh; caller holds the provider lock and commits the result."""
    if settings.app_data_mode != "live" or not settings.live_retention_approved:
        raise ProviderUnavailable("Real price refresh requires approved live mode")
    events = TheOddsAPI(db).odds()
    # Model fitting and provider calls can outlast the initial fixture fetch.
    # Observe prices when received, retaining their upstream timestamps.
    received = now()
    rejected = store_odds(db, events, fetched=received, observed=True)
    db.add(
        IngestionRun(
            provider=f"odds-refresh:{settings.odds_region}:{settings.odds_bookmaker_key}",
            status="complete",
            created_at=received,
            detail={"events": len(events)},
        )
    )
    return {"events": len(events), "unmatched_events": rejected}


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
    if mode == "live":
        try:
            upsert_european_events(db, TheOddsAPI(db).european_events(), fetched)
        except ProviderUnavailable:
            db.add(
                IngestionRun(
                    provider="european-fixtures",
                    status="unavailable",
                    detail={
                        "message": "European event feed unavailable; existing records retained"
                    },
                )
            )
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
                [
                    (
                        f.id,
                        f.home_goals,
                        f.away_goals,
                        f.home_half_goals,
                        f.away_half_goals,
                        f.result_available_at,
                    )
                    for f in league_history
                ],
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
    refresh = mode == "live" and odds_refresh_due(db)
    if refresh:
        rejected = refresh_odds(db)["unmatched_events"]
    else:
        rejected = store_odds(db, events, fetched=fetched, observed=True)
    # Reuse available recorded quotes with today's new prediction without altering quote ages.
    from .matchday import current_quotes

    for row in current_quotes(db):
        quote = db.get(Quote, row["quote_id"])
        prediction = db.scalar(
            select(Prediction)
            .where(Prediction.fixture_id == quote.fixture_id, Prediction.mode == mode)
            .order_by(Prediction.generated_at.desc())
        )
        if (
            prediction
            and utc(prediction.fixture_kickoff) == utc(db.get(Fixture, quote.fixture_id).kickoff)
            and quote.outcome in market_probabilities(prediction, quote.market)
            and not db.scalar(
                select(Publication.id).where(
                    Publication.prediction_id == prediction.id, Publication.quote_id == quote.id
                )
            )
        ):
            db.add(Publication(prediction_id=prediction.id, quote_id=quote.id))
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


def store_odds(db, events, fetched=None, observed=False):
    """Import recorded provider snapshots without fetching or refreshing their source age."""
    mode, fetched = settings.app_data_mode, fetched or now()
    prefix = "demo" if mode == "demo" else settings.football_provider
    fixtures = list(db.scalars(select(Fixture).where(Fixture.mode == mode)))
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
        fixture = next(
            (f for f in candidates if f.provider_id == "the-odds-api:" + event["id"]), None
        ) or match_fixture(event, candidates, names, aliases)
        if (
            not fixture
            or fixture.status != "scheduled"
            or utc(fixture.kickoff) <= now()
            or abs((utc(fixture.kickoff) - parse_time(event["commence_time"])).total_seconds())
            > 900
        ):
            rejected += 1
            continue
        if mode == "live":
            home_team, away_team = db.get(Team, fixture.home_id), db.get(Team, fixture.away_id)

            def side_matches(team, name):
                return team.name.casefold() == name.casefold() or team.id in {
                    names.get(name.casefold()),
                    aliases.get(name.casefold()),
                }

            if not side_matches(home_team, event["home_team"]) or not side_matches(
                away_team, event["away_team"]
            ):
                rejected += 1
                continue
            mapping = db.scalar(
                select(ProviderMapping).where(
                    ProviderMapping.provider == "the-odds-api",
                    ProviderMapping.entity_type == "fixture",
                    ProviderMapping.external_id == event["id"],
                )
            )
            if mapping and mapping.entity_id != fixture.id:
                rejected += 1
                continue
            if mapping is None:
                db.add(
                    ProviderMapping(
                        provider="the-odds-api",
                        entity_type="fixture",
                        external_id=event["id"],
                        entity_id=fixture.id,
                    )
                )
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
                kind = {
                    "h2h": "1x2",
                    "h2h_3_way": "1x2",
                    "totals": "totals",
                    "alternate_totals": "totals",
                    "btts": "btts",
                    "double_chance": "double_chance",
                    "totals_h1": "half_totals",
                    "alternate_totals_h1": "half_totals",
                }.get(market["key"])
                if not kind:
                    continue
                updated = market.get("last_update") or book.get("last_update")
                stamp = parse_time(updated) if updated else None
                if stamp and stamp > fetched + timedelta(minutes=1):
                    continue
                snapshot = fingerprint([event["id"], book["key"], market, updated])
                for outcome in market["outcomes"]:
                    quote_kind = kind
                    if kind in {"totals", "half_totals"}:
                        point = outcome.get("point")
                        if point not in {n + 0.5 for n in range(10)}:
                            continue  # Integer/Asian lines need push/partial-win settlement.
                        quote_kind = (
                            "totals" if kind == "totals" and point == 2.5 else f"{kind}_{point:g}"
                        )
                    selection = {
                        event["home_team"]: "home",
                        event["away_team"]: "away",
                        "Draw": "draw",
                        "Over": "over",
                        "Under": "under",
                        "Yes": "yes",
                        "No": "no",
                    }.get(outcome["name"])
                    if kind == "double_chance":
                        combinations = {
                            frozenset((event["home_team"], "Draw")): "1x",
                            frozenset((event["away_team"], "Draw")): "x2",
                            frozenset((event["home_team"], event["away_team"])): "12",
                        }
                        selection = combinations.get(frozenset(outcome["name"].split(" or ")))
                    allowed = {
                        "1x2": {"home", "draw", "away"},
                        "totals": {"over", "under"},
                        "half_totals": {"over", "under"},
                        "btts": {"yes", "no"},
                        "double_chance": {"1x", "x2", "12"},
                    }
                    try:
                        price = Decimal(str(outcome["price"]))
                    except (InvalidOperation, KeyError, ValueError):
                        continue
                    if (
                        selection not in allowed[kind]
                        or not price.is_finite()
                        or not 1 < price <= 1000
                    ):
                        continue
                    quote = db.scalar(
                        select(Quote).where(
                            Quote.fixture_id == fixture.id,
                            Quote.bookmaker_id == bookmaker.id,
                            Quote.snapshot_key == snapshot,
                            Quote.market == quote_kind,
                            Quote.outcome == selection,
                        )
                    )
                    if quote is None:
                        quote = Quote(
                            fixture_id=fixture.id,
                            bookmaker_id=bookmaker.id,
                            market=quote_kind,
                            outcome=selection,
                            price=price,
                            snapshot_key=snapshot,
                            source_updated_at=stamp,
                            fetched_at=fetched,
                            mode=mode,
                        )
                        db.add(quote)
                        db.flush()
                    if observed and not db.scalar(
                        select(QuoteObservation.id).where(
                            QuoteObservation.quote_id == quote.id,
                            QuoteObservation.observed_at == fetched,
                        )
                    ):
                        db.add(
                            QuoteObservation(
                                quote_id=quote.id,
                                observed_at=fetched,
                                fixture_kickoff=fixture.kickoff,
                            )
                        )
                    prediction = db.scalar(
                        select(Prediction)
                        .where(Prediction.fixture_id == fixture.id, Prediction.mode == mode)
                        .order_by(Prediction.generated_at.desc())
                    )
                    if (
                        prediction
                        and utc(prediction.fixture_kickoff) == utc(fixture.kickoff)
                        and selection in market_probabilities(prediction, quote_kind)
                        and utc(prediction.generated_at) < utc(fixture.kickoff)
                    ):
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
            home, away = fixture.home_goals, fixture.away_goals
            if quote.market.startswith("half_"):
                if fixture.home_half_goals is None or fixture.away_half_goals is None:
                    continue
                home, away = fixture.home_half_goals, fixture.away_half_goals
            result = "won" if outcome_won(quote.market, quote.outcome, home, away) else "lost"
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
        if quote.market.startswith("half_"):
            signature += f":half:{fixture.home_half_goals}:{fixture.away_half_goals}"
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
