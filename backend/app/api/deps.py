import secrets

from fastapi import Depends, Header, Request
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import require
from app.db.session import get_db
from app.models import AuthSession
from app.services.auth import authenticate, digest

session_cookie = APIKeyCookie(
    name="intakeflow_session",
    auto_error=False,
    description="Random opaque HttpOnly session cookie. Sign in first; never store it in localStorage.",
)


def actor(db: Session = Depends(get_db), token: str | None = Depends(session_cookie)):
    return authenticate(db, token)


def csrf_guard(
    request: Request,
    db: Session = Depends(get_db),
    x_csrf_token: str | None = Header(
        default=None,
        description="Required for all state-changing requests. Obtain from GET /auth/csrf; must match the CSRF cookie and authenticated session.",
    ),
):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    require(not origin or origin == get_settings().app_origin, "CSRF", "Untrusted origin", 403)
    header = x_csrf_token or ""
    cookie = request.cookies.get("intakeflow_csrf", "")
    require(
        bool(header) and secrets.compare_digest(header, cookie),
        "CSRF",
        "CSRF token missing or invalid",
        403,
    )
    token = request.cookies.get("intakeflow_session")
    if token:
        who = authenticate(db, token)
        session = db.get(AuthSession, who.session_id)
        require(
            secrets.compare_digest(session.csrf_hash, digest(header)),
            "CSRF",
            "CSRF token is expired",
            403,
        )
