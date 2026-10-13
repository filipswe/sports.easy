import hashlib
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select

from .config import settings
from .db import get_db, now, utc
from .models import AuthSession, AuthToken, SavedSelection, User

router = APIRouter(prefix="/api/auth", tags=["account"])
hasher = PasswordHash.recommended()
DUMMY_HASH = hasher.hash("timing-only-dummy-password")


def user_required(request: Request, db=Depends(get_db)):
    sid = request.session.get("sid")
    session = db.get(AuthSession, sid) if sid else None
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "Sign in to continue")
    user = db.get(User, session.user_id)
    if not user or not user.verified:
        raise HTTPException(401, "Sign in to continue")
    return user


def admin_required(user=Depends(user_required)):
    if not user.admin:
        raise HTTPException(403, "Administrator access required")
    return user


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class EmailInput(BaseModel):
    email: EmailStr


class TokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str | None = Field(default=None, min_length=12, max_length=128)


def issue_token(db, user, purpose):
    if not settings.smtp_host and settings.app_data_mode != "demo":
        raise HTTPException(503, "Email delivery is not configured")
    raw = secrets.token_urlsafe(32)
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose))
    db.add(
        AuthToken(
            id=hashlib.sha256(raw.encode()).hexdigest(),
            user_id=user.id,
            purpose=purpose,
            expires_at=now() + timedelta(minutes=30),
        )
    )
    db.commit()
    link = f"{settings.public_origin}/account?{purpose}={raw}"
    if settings.smtp_host:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = (
            settings.smtp_from,
            user.email,
            f"sports.easy — {purpose}",
        )
        message.set_content(
            f"Use this link within 30 minutes: {link}\nIf you did not request this, ignore this email."
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_starttls:
                    server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        except (OSError, smtplib.SMTPException):
            raise HTTPException(503, "Email delivery temporarily unavailable") from None
    return (
        link
        if settings.app_data_mode == "demo"
        and settings.app_env == "development"
        and not settings.smtp_host
        else None
    )


@router.get("/csrf")
def csrf(request: Request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf": request.session["csrf"]}


@router.post("/register", status_code=202)
def register(body: Credentials, db=Depends(get_db)):
    email = str(body.email).lower()
    existing = db.scalar(select(User).where(User.email == email))
    link = None
    if not existing:
        user = User(email=email, password_hash=hasher.hash(body.password))
        db.add(user)
        db.flush()
        link = issue_token(db, user, "verify")
    return {"message": "If eligible, check your email to verify your account.", "demo_link": link}


@router.post("/login")
def login(body: Credentials, request: Request, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = hasher.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.verified:
        raise HTTPException(401, "Unable to sign in with these credentials")
    if request.session.get("sid"):
        db.execute(delete(AuthSession).where(AuthSession.id == request.session["sid"]))
    request.session.clear()
    sid = secrets.token_urlsafe(32)
    request.session.update(sid=sid, csrf=secrets.token_urlsafe(32))
    db.add(AuthSession(id=sid, user_id=user.id, expires_at=now() + timedelta(days=7)))
    db.commit()
    return {"id": user.id, "email": user.email, "csrf": request.session["csrf"]}


@router.post("/logout")
def logout(request: Request, db=Depends(get_db)):
    db.execute(delete(AuthSession).where(AuthSession.id == request.session.get("sid", "")))
    db.commit()
    request.session.clear()
    return {"message": "Signed out"}


@router.post("/request-reset", status_code=202)
def request_reset(body: EmailInput, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    link = issue_token(db, user, "reset") if user else None
    return {"message": "If eligible, a reset link has been sent.", "demo_link": link}


@router.post("/verify")
@router.post("/reset")
def consume(body: TokenInput, request: Request, db=Depends(get_db)):
    purpose = request.url.path.rsplit("/", 1)[-1]
    token = db.scalar(
        select(AuthToken)
        .where(AuthToken.id == hashlib.sha256(body.token.encode()).hexdigest())
        .with_for_update()
    )
    if not token or token.purpose != purpose or utc(token.expires_at) <= now():
        raise HTTPException(400, "This link is invalid or expired")
    user = db.get(User, token.user_id)
    if purpose == "reset":
        if not body.password:
            raise HTTPException(422, "A new password is required")
        user.password_hash = hasher.hash(body.password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    else:
        user.verified = True
    db.delete(token)
    db.commit()
    return {
        "message": "Password updated. Sign in again."
        if purpose == "reset"
        else "Email verified. You can now sign in."
    }


@router.get("/me")
def me(user=Depends(user_required)):
    return {
        "id": user.id,
        "email": user.email,
        "preferences": user.preferences,
        "admin": user.admin,
    }


class Preferences(BaseModel):
    timezone: str = Field(default="Europe/Belgrade", max_length=80)
    odds_format: str = Field(default="decimal", pattern="^(decimal|american)$")
    leagues: list[str] = Field(default_factory=list, max_length=10)
    filters: str = Field(default="", max_length=2000)


@router.put("/preferences")
def preferences(body: Preferences, user=Depends(user_required), db=Depends(get_db)):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Choose a valid IANA timezone") from None
    db_user = db.get(User, user.id)
    db_user.preferences = body.model_dump()
    db.commit()
    return db_user.preferences


class DeleteAccount(BaseModel):
    password: str = Field(max_length=128)


@router.delete("/account", status_code=204)
def delete_account(
    body: DeleteAccount, request: Request, user=Depends(user_required), db=Depends(get_db)
):
    if not hasher.verify(body.password, user.password_hash):
        raise HTTPException(401, "Unable to verify credentials")
    for cls in [SavedSelection, AuthToken, AuthSession]:
        db.execute(delete(cls).where(cls.user_id == user.id))
    db.delete(db.get(User, user.id))
    db.commit()
    request.session.clear()
    return Response(status_code=204)
