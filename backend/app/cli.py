import argparse
import json

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .evaluation import evaluate
from .ingestion import ingest
from .models import AdminAudit, User

parser = argparse.ArgumentParser(description="sports.easy operations")
parser.add_argument("command", choices=["seed", "ingest", "evaluate", "promote-admin"])
parser.add_argument("--email")
args = parser.parse_args()
with SessionLocal() as db:
    if args.command == "seed":
        if settings.app_data_mode != "demo":
            raise SystemExit("Seed is only available in demo mode")
        print(json.dumps(ingest(db)))
    elif args.command == "ingest":
        print(json.dumps(ingest(db)))
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
