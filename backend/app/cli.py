import argparse
import json

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .evaluation import evaluate
from .ingestion import ingest, refresh_odds, settle
from .models import AdminAudit, User
from .providers import ProviderUnavailable

parser = argparse.ArgumentParser(description="sports.easy operations")
parser.add_argument(
    "command",
    choices=[
        "seed",
        "ingest",
        "evaluate",
        "promote-admin",
        "readiness",
        "refresh",
        "refresh-prices",
    ],
)
parser.add_argument("--email")
args = parser.parse_args()
with SessionLocal() as db:
    if args.command == "readiness":
        from .readiness import release_blockers

        print(
            json.dumps(
                {
                    "configuration_blockers": release_blockers(),
                    "note": "Also complete docs/production-readiness.md; configuration alone does not certify release.",
                },
                indent=2,
            )
        )
    elif args.command in {"refresh", "refresh-prices"}:
        from .readiness import release_blockers
        from .worker import tick

        if settings.app_env == "production" and release_blockers():
            raise SystemExit(
                "Production configuration incomplete: " + ", ".join(release_blockers())
            )
        try:
            if args.command == "refresh":
                result = tick()
            else:
                from .picks import publish_recommendations
                from .price_refresh import provider_lock

                with provider_lock(db) as acquired:
                    if acquired:
                        result = {"status": "complete", **refresh_odds(db)}
                        settle(db)
                        publish_recommendations(db)
                        db.commit()
                    else:
                        result = {"status": "busy"}
        except Exception:
            raise SystemExit("Refresh failed; inspect sanitized application logs") from None
        print(json.dumps(result))
        if result["status"] in {"failed", "unavailable"}:
            raise SystemExit(2)
    elif args.command == "seed":
        if settings.app_data_mode != "demo":
            raise SystemExit("Seed is only available in demo mode")
        print(json.dumps(ingest(db)))
    elif args.command == "ingest":
        try:
            print(json.dumps(ingest(db)))
        except ProviderUnavailable as exc:
            print("Provider refresh unavailable: " + str(exc))
            raise SystemExit(2) from None
    elif args.command == "evaluate":
        print(json.dumps(evaluate(db), indent=2))
    else:
        user = db.scalar(select(User).where(User.email == args.email, User.verified.is_(True)))
        if not user:
            raise SystemExit("Register and verify this account first")
        user.admin = True
        db.add(AdminAudit(actor="local-operator", action=f"promote-admin:{user.id}"))
        db.commit()
        print("Administrator role granted; audit recorded")
