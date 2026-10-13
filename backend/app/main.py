import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text
from starlette.middleware.sessions import SessionMiddleware

from .auth import admin_required, user_required
from .auth import router as auth_router
from .config import settings
from .crests import team_logo
from .db import get_db, now, utc
from .evaluation import metrics
from .matchday import router as matchday_router
from .model import VERSION, no_vig
from .models import (
    Bookmaker,
    Competition,
    EvaluationRun,
    Fixture,
    IngestionRun,
    Job,
    Prediction,
    Publication,
    Quote,
    SavedSelection,
    Settlement,
    Team,
)
from .picks import recommendation_rows
from .research import Filters, all_rows, quote_stale, require_fixture, search

logger = logging.getLogger("sports.easy")


@asynccontextmanager
async def lifespan(app):
    if (settings.app_data_mode == "live" or settings.app_env == "production") and (
        len(settings.session_secret) < 32
        or "local-only" in settings.session_secret
        or "replace-with" in settings.session_secret
    ):
        raise RuntimeError("Live mode requires a private SESSION_SECRET")
    origin = urlsplit(settings.public_origin)
    local_http = (
        settings.app_env == "development"
        and origin.scheme == "http"
        and origin.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        (settings.app_data_mode == "live" or settings.app_env == "production")
        and (not settings.cookie_secure or origin.scheme != "https")
        and not local_http
    ):
        raise RuntimeError("Public live deployments require HTTPS and COOKIE_SECURE=true")
    if settings.app_env == "production" and (
        origin.scheme != "https" or not settings.cookie_secure
    ):
        raise RuntimeError("Production requires HTTPS and COOKIE_SECURE=true")
    if settings.app_env == "production" and not settings.smtp_host:
        raise RuntimeError("Production account workflows require SMTP delivery")
    yield


app = FastAPI(
    title="sports.easy API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.include_router(auth_router)
app.include_router(matchday_router)
requests_by_ip = defaultdict(deque)


@app.middleware("http")
async def controls(request: Request, call_next):
    started = time.monotonic()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 32_768:
            return JSONResponse({"error": {"message": "Request too large"}}, status_code=413)
    request._body = bytes(body)
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        origin, csrf = request.headers.get("origin"), request.headers.get("x-csrf-token")
        if (
            origin != settings.public_origin
            or not csrf
            or not secrets.compare_digest(csrf, request.session.get("csrf", ""))
        ):
            return JSONResponse(
                {"error": {"message": "Request verification failed. Refresh and try again."}},
                status_code=403,
            )
    ip = request.client.host if request.client else "unknown"
    category = (
        "auth-mutation" if "/auth/" in request.url.path and request.method != "GET" else "research"
    )
    key = (ip, category)
    queue = requests_by_ip[key]
    stamp = time.monotonic()
    while queue and queue[0] < stamp - 60:
        queue.popleft()
    limit = 20 if category == "auth-mutation" else 180
    if len(queue) >= limit:
        return JSONResponse(
            {"error": {"message": "Too many requests. Try again in a minute."}},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    queue.append(stamp)
    if len(requests_by_ip) > 10000:
        for old_key in list(requests_by_ip):
            if not requests_by_ip[old_key] or requests_by_ip[old_key][-1] < stamp - 60:
                del requests_by_ip[old_key]
    try:
        response = await call_next(request)
    except Exception:
        # No request bodies, passwords, provider keys, reset tokens or exception URLs in logs.
        logger.error(json.dumps({"event": "request_error", "route": request.url.path}))
        response = JSONResponse(
            {"error": {"message": "Service temporarily unavailable"}}, status_code=500
        )
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Cache-Control": "no-store",
        }
    )
    logger.info(
        json.dumps(
            {
                "event": "request",
                "route": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


# SessionMiddleware must wrap CSRF middleware so signed session data is available.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="sports_session",
    same_site="lax",
    https_only=settings.cookie_secure,
    max_age=604800,
)


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({"error": {"message": exc.detail}}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        {
            "error": {
                "message": "Check your filters or form fields.",
                "fields": [
                    {"field": ".".join(map(str, e["loc"])), "message": e["msg"]}
                    for e in exc.errors()
                ],
            }
        },
        status_code=422,
    )


@app.get("/api/health", tags=["operations"])
def health():
    return {"status": "ok"}


@app.get("/api/ready", tags=["operations"])
def ready(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    db.scalar(select(func.count()).select_from(Fixture))
    return {"status": "ready", "mode": settings.app_data_mode}


@app.get("/api/meta")
def meta(db=Depends(get_db)):
    latest = db.scalar(
        select(func.max(Fixture.fetched_at)).where(Fixture.mode == settings.app_data_mode)
    )
    return {
        "mode": settings.app_data_mode,
        "model_version": VERSION,
        "football_provider": settings.football_provider
        if settings.app_data_mode == "live"
        else "demo",
        "feed_notice": "Delayed results · Daily recorded odds"
        if settings.app_data_mode == "live" and settings.poll_seconds >= 86400
        else "",
        "data_fetched_at": latest,
        "leagues": [
            {"id": c.id, "name": c.name, "season": c.season}
            for c in db.scalars(
                select(Competition).where(Competition.mode == settings.app_data_mode)
            )
        ],
        "bookmakers": [
            {"id": b.id, "name": b.name, "region": b.region}
            for b in db.scalars(
                select(Bookmaker).where(Bookmaker.provider_id.like(settings.app_data_mode + ":%"))
            )
        ],
        "markets": ["1x2", "totals", "btts"]
        if settings.app_data_mode == "demo"
        else ["1x2", "totals"],
        "region": settings.odds_region,
        "freshness_seconds": settings.quote_max_age_seconds,
        "regional_notice": settings.regional_notice,
        "email_demo": settings.app_data_mode == "demo" and not settings.smtp_host,
    }


@app.get("/api/predictions", tags=["research"])
@app.get("/api/research", tags=["research"])
def research(filters: Filters = Query(), db=Depends(get_db)):
    return search(db, filters)


@app.get("/api/fixtures", tags=["research"])
def fixtures(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db=Depends(get_db)
):
    query = select(Fixture).where(
        Fixture.mode == settings.app_data_mode,
        Fixture.kickoff > now(),
        Fixture.status == "scheduled",
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            {
                "id": f.id,
                "home": db.get(Team, f.home_id).name,
                "away": db.get(Team, f.away_id).name,
                "kickoff": f.kickoff,
                "status": f.status,
            }
            for f in db.scalars(
                query.order_by(Fixture.kickoff).offset((page - 1) * page_size).limit(page_size)
            )
        ],
        "total": total,
    }


@app.get("/api/fixtures/{fixture_id}", tags=["research"])
def detail(fixture_id: str, db=Depends(get_db)):
    f = require_fixture(db, fixture_id)
    p = db.scalar(
        select(Prediction)
        .where(Prediction.fixture_id == f.id)
        .order_by(Prediction.generated_at.desc())
    )
    competition = db.get(Competition, f.competition_id)
    history_ids = [
        c.id
        for c in db.scalars(select(Competition))
        if c.mode == f.mode and c.provider_id.split(":")[1] == competition.provider_id.split(":")[1]
    ]
    history = list(
        db.scalars(
            select(Fixture)
            .where(
                Fixture.mode == f.mode,
                Fixture.competition_id.in_(history_ids),
                Fixture.status == "finished",
                Fixture.kickoff < (p.input_cutoff if p else now()),
            )
            .order_by(Fixture.kickoff.desc())
        )
    )
    history = [
        x
        for x in history
        if x.result_available_at
        and utc(x.result_available_at) < utc(p.input_cutoff if p else now())
    ]

    def team_stats(team_id):
        played = [x for x in history if team_id in (x.home_id, x.away_id)]

        def summary(rows):
            scored = sum(x.home_goals if x.home_id == team_id else x.away_goals for x in rows)
            conceded = sum(x.away_goals if x.home_id == team_id else x.home_goals for x in rows)
            return {"matches": len(rows), "scored": scored, "conceded": conceded}

        return {
            "recent": [
                {
                    "opponent": db.get(Team, x.away_id if x.home_id == team_id else x.home_id).name,
                    "opponent_logo": team_logo(
                        db.get(Team, x.away_id if x.home_id == team_id else x.home_id)
                    ),
                    "score": f"{x.home_goals}–{x.away_goals}",
                    "kickoff": x.kickoff,
                    "result": "D"
                    if x.home_goals == x.away_goals
                    else "W"
                    if (x.home_goals > x.away_goals) == (x.home_id == team_id)
                    else "L",
                }
                for x in played[:5]
            ],
            "home": summary([x for x in played if x.home_id == team_id]),
            "away": summary([x for x in played if x.away_id == team_id]),
            "rest_days": (utc(f.kickoff) - utc(played[0].kickoff)).days if played else None,
        }

    quotes = list(
        db.scalars(select(Quote).where(Quote.fixture_id == f.id).order_by(Quote.fetched_at.desc()))
    )
    groups, seen = {}, set()
    for q in quotes:
        key = (q.bookmaker_id, q.market, q.outcome)
        if key in seen:
            continue
        seen.add(key)
        groups.setdefault((q.bookmaker_id, q.market, q.snapshot_key), []).append(q)
    comparison = [
        {
            "bookmaker": db.get(Bookmaker, book).name,
            "market": market,
            "outcomes": {q.outcome: float(q.price) for q in qs},
            "no_vig": no_vig(qs, market),
            "stale": any(quote_stale(q) for q in qs),
            "source_updated_at": qs[0].source_updated_at,
        }
        for (book, market, _), qs in groups.items()
    ]
    h2h = [x for x in history if {x.home_id, x.away_id} == {f.home_id, f.away_id}]
    return {
        "id": f.id,
        "home": db.get(Team, f.home_id).name,
        "away": db.get(Team, f.away_id).name,
        "home_logo": team_logo(db.get(Team, f.home_id)),
        "away_logo": team_logo(db.get(Team, f.away_id)),
        "competition": db.get(Competition, f.competition_id).name,
        "kickoff": utc(f.kickoff),
        "status": "kickoff reached / awaiting feed"
        if f.status == "scheduled" and utc(f.kickoff) <= now()
        else f.status,
        "venue": f.venue,
        "mode": f.mode,
        "prediction": {
            "id": p.id,
            "probabilities": p.probabilities,
            "factors": p.factors,
            "model_version": p.model_id,
            "generated_at": p.generated_at,
            "input_cutoff": p.input_cutoff,
            "history_fetched_at": p.history_fetched_at,
        }
        if p
        else None,
        "fixture_fetched_at": f.fetched_at,
        "fixture_provider_updated_at": f.provider_updated_at,
        "home_stats": team_stats(f.home_id),
        "away_stats": team_stats(f.away_id),
        "head_to_head_sample": len(h2h),
        "head_to_head": [
            {
                "home": db.get(Team, x.home_id).name,
                "away": db.get(Team, x.away_id).name,
                "home_logo": team_logo(db.get(Team, x.home_id)),
                "away_logo": team_logo(db.get(Team, x.away_id)),
                "score": f"{x.home_goals}–{x.away_goals}",
            }
            for x in h2h[:5]
        ],
        "standings": None,
        "injuries": None,
        "suspensions": None,
        "lineups": None,
        "xg": None,
        "comparison": comparison,
        "selections": search(
            db,
            Filters(team=db.get(Team, f.home_id).name, page_size=48, region=settings.odds_region),
        )["items"],
        "explanation": {
            "kind": "Deterministic statistical explanation",
            "text": f"The model fits opponent-adjusted attack and defence strengths to past goals, with home advantage and 180-day recency weighting. The inputs contain {p.factors['league_sample']} historical matches. Injuries, xG and lineups are not used. Independent Poisson scores can miss low-score dependence and team changes."
            if p
            else "Insufficient historical coverage: the model abstains.",
            "sources": [p.id] if p else [],
            "missing": ["injuries", "xG", "lineups"],
        },
    }


@app.get("/api/fixtures/{fixture_id}/odds-history", tags=["research"])
def odds_history(fixture_id: str, limit: int = Query(100, ge=1, le=500), db=Depends(get_db)):
    require_fixture(db, fixture_id)
    return {
        "items": [
            {
                "id": q.id,
                "market": q.market,
                "outcome": q.outcome,
                "odds": float(q.price),
                "bookmaker": db.get(Bookmaker, q.bookmaker_id).name,
                "source_updated_at": q.source_updated_at,
                "fetched_at": q.fetched_at,
            }
            for q in db.scalars(
                select(Quote)
                .where(Quote.fixture_id == fixture_id)
                .order_by(Quote.fetched_at.desc())
                .limit(limit)
            )
        ]
    }


class SaveInput(BaseModel):
    publication_id: str


@app.post("/api/saved", status_code=201, tags=["saved research"])
def save(body: SaveInput, user=Depends(user_required), db=Depends(get_db)):
    pub = db.get(Publication, body.publication_id)
    p = db.get(Prediction, pub.prediction_id) if pub else None
    if not p or p.mode != settings.app_data_mode:
        raise HTTPException(404, "Selection not found")
    f = db.get(Fixture, p.fixture_id)
    if (
        f.status != "scheduled"
        or utc(f.kickoff) <= now()
        or utc(p.fixture_kickoff) != utc(f.kickoff)
    ):
        raise HTTPException(409, "This fixture is no longer available for pre-match research")
    saved = db.scalar(
        select(SavedSelection).where(
            SavedSelection.user_id == user.id, SavedSelection.publication_id == pub.id
        )
    )
    if not saved:
        saved = SavedSelection(user_id=user.id, publication_id=pub.id)
        db.add(saved)
        db.commit()
    return {"id": saved.id}


@app.get("/api/saved", tags=["saved research"])
def saved(user=Depends(user_required), db=Depends(get_db)):
    rows = {r["id"]: r for r in all_rows(db, archive=True)}
    current = {}
    for row in all_rows(db):
        current.setdefault(
            (row["fixture_id"], row["market"], row["outcome"], row["bookmaker_id"]), row
        )
    items = []
    for item in db.scalars(
        select(SavedSelection)
        .where(SavedSelection.user_id == user.id)
        .order_by(SavedSelection.created_at.desc())
    ):
        original = rows.get(item.publication_id)
        if original:
            items.append(
                {
                    "id": item.id,
                    "saved_at": item.created_at,
                    "original": original,
                    "current": current.get(
                        (
                            original["fixture_id"],
                            original["market"],
                            original["outcome"],
                            original["bookmaker_id"],
                        )
                    ),
                }
            )
    return {"items": items}


@app.delete("/api/saved/{saved_id}", status_code=204, tags=["saved research"])
def unsave(saved_id: str, user=Depends(user_required), db=Depends(get_db)):
    record = db.scalar(
        select(SavedSelection).where(
            SavedSelection.id == saved_id, SavedSelection.user_id == user.id
        )
    )
    if not record:
        raise HTTPException(404, "Saved selection not found")
    db.delete(record)
    db.commit()
    return Response(status_code=204)


@app.get("/api/performance", tags=["evaluation"])
def performance(page: int = Query(1, ge=1), db=Depends(get_db)):
    canonical = {r["id"]: r for r in recommendation_rows(db)}
    archive, observations, returns = [], [], []
    wins = 0
    for row in canonical.values():
        settlement = db.scalar(
            select(Settlement)
            .where(Settlement.publication_id == row["id"])
            .order_by(Settlement.recorded_at.desc())
        )
        status = settlement.result if settlement else "pending"
        archive.append(
            {**row, "result": status, "corrected": bool(settlement and settlement.supersedes_id)}
        )
        if status in ["won", "lost"]:
            y = int(status == "won")
            wins += y
            observations.append((row["probability"], y))
            returns.append(row["odds"] - 1 if y else -1)
    evaluation = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.mode == settings.app_data_mode)
        .order_by(EvaluationRun.created_at.desc())
    )
    return {
        "mode": settings.app_data_mode,
        "record_type": "Synthetic demo records"
        if settings.app_data_mode == "demo"
        else "Forward-recorded observations",
        "count": len(archive),
        "settled": len(observations),
        "wins": wins,
        "win_rate": wins / len(observations) if observations else None,
        **metrics(observations),
        "hypothetical_return_units": sum(returns) if returns else None,
        "date_from": min((r["generated_at"] for r in archive), default=None),
        "date_to": max((r["generated_at"] for r in archive), default=None),
        "policy": "Only official recommended picks are counted, once per match, at their original recorded odds. One hypothetical unit per settled pick. Pending, void and postponed picks are excluded from win rate and return.",
        "archive": archive[(page - 1) * 30 : page * 30],
        "page": page,
        "backtest": evaluation.report if evaluation else None,
        "claim": "This model has not demonstrated a validated advantage over bookmaker prices.",
    }


@app.get("/api/admin/status", tags=["admin"])
def admin_status(user=Depends(admin_required), db=Depends(get_db)):
    def records(cls):
        return [
            {"id": r.id, "status": r.status, "created_at": r.created_at, "detail": r.detail}
            for r in db.scalars(select(cls).order_by(cls.created_at.desc()).limit(50))
        ]

    return {
        "mode": settings.app_data_mode,
        "model": VERSION,
        "jobs": records(Job),
        "ingestion": records(IngestionRun),
        "daily_budgets": {
            "football": settings.provider_daily_budget,
            "odds_credits": settings.odds_daily_budget,
        },
        "coverage": meta(db),
        "credentials_present": {
            "football": bool(settings.api_football_key),
            "odds": bool(settings.odds_api_key),
        },
    }
