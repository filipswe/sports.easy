"""A transparent bookmaker baseline when European match history is absent."""

from sqlalchemy import select

from .config import settings
from .db import now, utc
from .leagues import EUROPEAN_COMPETITIONS
from .model import no_vig
from .models import Competition, Fixture, ModelVersion, Prediction, Publication, Quote
from .providers import fingerprint

VERSION = "bookmaker-baseline-v1"


def publish_european_predictions(db):
    if settings.app_data_mode != "live":
        return
    from .matchday import current_quotes

    competitions = {
        c.id
        for c in db.scalars(select(Competition))
        if c.mode == "live"
        and c.provider_id.split(":")[1] in {str(league.id) for league in EUROPEAN_COMPETITIONS}
    }
    groups = {}
    for row in current_quotes(db, markets_filter=("1x2",)):
        if row["competition_id"] in competitions:
            groups.setdefault(row["fixture_id"], []).append(row)
    if not groups:
        return
    if not db.get(ModelVersion, VERSION):
        db.add(
            ModelVersion(
                id=VERSION,
                methodology={
                    "kind": "Bookmaker baseline",
                    "method": "Normalize inverse decimal prices across a complete 1X2 snapshot to remove its margin. This is a market estimate, not an independently trained statistical forecast.",
                },
            )
        )
        db.flush()
    for fixture_id, rows in groups.items():
        fixture = db.get(Fixture, fixture_id)
        latest = db.scalar(
            select(Prediction)
            .where(Prediction.fixture_id == fixture_id, Prediction.mode == "live")
            .order_by(Prediction.generated_at.desc())
        )
        if (
            latest
            and latest.model_id != VERSION
            and utc(latest.fixture_kickoff) == utc(fixture.kickoff)
        ):
            continue
        quotes = [db.get(Quote, row["quote_id"]) for row in rows]
        probabilities = no_vig(quotes, "1x2")
        if probabilities is None:
            continue
        hsh = fingerprint([fixture.kickoff, sorted(q.id for q in quotes), VERSION])
        prediction = db.scalar(
            select(Prediction).where(
                Prediction.fixture_id == fixture_id,
                Prediction.model_id == VERSION,
                Prediction.input_hash == hsh,
            )
        )
        if prediction is None:
            at = now()
            prediction = Prediction(
                fixture_id=fixture_id,
                model_id=VERSION,
                input_hash=hsh,
                fixture_kickoff=fixture.kickoff,
                generated_at=at,
                input_cutoff=at,
                history_fetched_at=max(utc(row["observed_at"]) for row in rows),
                probabilities={"1x2": probabilities},
                factors={"basis": "market", "bookmaker": rows[0]["bookmaker"]},
                quality="Market-based",
                mode="live",
            )
            db.add(prediction)
            db.flush()
        for quote in quotes:
            if not db.scalar(
                select(Publication.id).where(
                    Publication.prediction_id == prediction.id, Publication.quote_id == quote.id
                )
            ):
                db.add(Publication(prediction_id=prediction.id, quote_id=quote.id))
    db.flush()
