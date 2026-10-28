import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import Claim, User


PASSWORD_ITERATIONS = 600_000
bearer_scheme = HTTPBearer(auto_error=False)


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        _base64url_encode(salt),
        _base64url_encode(digest)
    )


def verify_password(password, encoded_password):
    try:
        algorithm, iterations, salt, expected_digest = (
            encoded_password.split("$", 3)
        )
        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _base64url_decode(salt),
            int(iterations)
        )
        return hmac.compare_digest(
            _base64url_encode(digest),
            expected_digest
        )
    except (TypeError, ValueError):
        return False


def create_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.access_token_minutes)).timestamp()
        )
    }
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _base64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def decode_access_token(token):
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256
        ).digest()
        supplied_signature = _base64url_decode(encoded_signature)

        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise ValueError("Invalid signature")

        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))

        if header.get("alg") != "HS256":
            raise ValueError("Invalid algorithm")

        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("Expired token")

        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from error

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is unavailable.")

    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return current_user


def require_claim_access(claim: Claim | None, current_user: User):
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    if current_user.role != "ADMIN" and claim.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Claim not found.")

    return claim
