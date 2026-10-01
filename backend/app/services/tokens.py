from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings


class AuthenticationConfigurationError(RuntimeError):
    """Raised when token handling is attempted without a signing key."""


def _signing_key(settings: Settings) -> str:
    if settings.jwt_secret_key is None:
        raise AuthenticationConfigurationError("JWT signing key is not configured.")
    return settings.jwt_secret_key


def create_access_token(user_id: str, settings: Settings) -> str:
    """Create a short-lived signed bearer token for an immutable user ID."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, _signing_key(settings), algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> str:
    """Return the token subject or raise an invalid-token error."""
    payload = jwt.decode(token, _signing_key(settings), algorithms=["HS256"])
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Token subject is missing.")
    return subject
