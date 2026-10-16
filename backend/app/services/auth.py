import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.errors import require
from app.models import AuthSession, LoginAttempt, Membership, Organization, User, utcnow

hasher = PasswordHasher()  # Argon2id; salt and work factors are encoded in the hash.
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(20))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Actor:
    user_id: str
    org_id: str
    role: str
    session_id: str = ""


def staff(actor):
    require(actor.role in {"ADMIN", "STAFF"}, "FORBIDDEN", "Staff access required", 403)


def admin(actor):
    require(actor.role == "ADMIN", "FORBIDDEN", "Administrator access required", 403)


def tenant(actor):
    require(actor.role == "TENANT", "FORBIDDEN", "Tenant access required", 403)


def authenticate(db, token):
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == digest(token or ""), AuthSession.expires_at > utcnow()
        )
    )
    require(session is not None, "UNAUTHENTICATED", "Please sign in", 401)
    member = db.scalar(
        select(Membership).where(
            Membership.org_id == session.org_id,
            Membership.user_id == session.user_id,
            Membership.active.is_(True),
        )
    )
    require(member is not None, "UNAUTHENTICATED", "Membership is inactive", 401)
    return Actor(session.user_id, session.org_id, member.role, session.id)


def rate_limit(db, key):
    key_hash = digest(key)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key_hash[:15], 16)})
    count = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.key_hash == key_hash,
            LoginAttempt.created_at > utcnow() - timedelta(minutes=15),
        )
    )
    require(count < 10, "RATE_LIMITED", "Too many attempts; try again in 15 minutes", 429)
    db.add(LoginAttempt(key_hash=key_hash))
    db.commit()


def new_session(db, user, org_id):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            org_id=org_id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=utcnow() + timedelta(hours=get_settings().session_hours),
        )
    )
    db.commit()
    return token, csrf


def register(db, data):
    require(
        db.scalar(select(User).where(User.email == str(data.email).lower())) is None,
        "EMAIL_EXISTS",
        "Email is already registered",
        409,
    )
    org = Organization(name=data.organization_name, timezone=data.timezone)
    user = User(
        name=data.name, email=str(data.email).lower(), password_hash=hasher.hash(data.password)
    )
    db.add_all([org, user])
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role="ADMIN"))
    db.commit()
    return new_session(db, user, org.id)


def login(db, data, ip):
    # IP-wide and account-wide limits apply even if credentials are correct.
    rate_limit(db, f"ip:{ip}")
    rate_limit(db, f"email:{str(data.email).lower()}")
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    try:
        valid = hasher.verify(user.password_hash if user else DUMMY_HASH, data.password)
    except VerificationError:
        valid = False
    require(valid and user is not None, "INVALID_CREDENTIALS", "Invalid email or password", 401)
    query = select(Membership).where(Membership.user_id == user.id, Membership.active.is_(True))
    if data.organization_id:
        query = query.where(Membership.org_id == data.organization_id)
    memberships = db.scalars(query).all()
    require(
        len(memberships) == 1,
        "ORGANIZATION_REQUIRED",
        "Select a valid organization ID for this account",
        400,
    )
    return new_session(db, user, memberships[0].org_id)


def profile(db, actor):
    user, org = db.get(User, actor.user_id), db.get(Organization, actor.org_id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": actor.role,
        "organization": {"id": org.id, "name": org.name, "timezone": org.timezone},
        "ai_provider": get_settings().ai_provider,
    }
