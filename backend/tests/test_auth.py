from datetime import datetime, timezone

from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_user_repository
from app.core.config import Settings
from app.main import create_app
from app.models.user import User, UserInDatabase
from app.services.passwords import hash_password
from app.services.tokens import create_access_token, decode_access_token


class FakeUserRepository:
    def __init__(self, user: UserInDatabase) -> None:
        self.user = user

    async def find_by_email(self, email: str) -> UserInDatabase | None:
        return self.user if email == self.user.email else None

    async def find_by_id(self, user_id: str) -> UserInDatabase | None:
        return self.user if user_id == self.user.id else None

    async def create(self, email: str, password_hash: str, *, name: str | None = None, role: str | None = None) -> UserInDatabase:
        assert password_hash != "new-password"
        self.user = self.user.model_copy(update={"email": email, "name": name, "role": role})
        return self.user


def authentication_settings() -> Settings:
    return Settings.from_environment(
        {
            "TRUSTLENS_ENV": "test",
            "TRUSTLENS_JWT_SECRET_KEY": "test-signing-key-that-is-never-used-outside-tests",
            "TRUSTLENS_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        }
    )


def create_authenticated_client() -> tuple[TestClient, UserInDatabase, Settings]:
    settings = authentication_settings()
    user = UserInDatabase(
        id="507f1f77bcf86cd799439011",
        email="ada@example.com",
        password_hash=hash_password("correct horse battery staple"),
        created_at=datetime.now(timezone.utc),
    )
    app = create_app(settings)
    app.dependency_overrides[get_user_repository] = lambda: FakeUserRepository(user)

    @app.get("/test/current-user", response_model=User)
    async def test_current_user(current_user: User = Depends(get_current_user)) -> User:
        return current_user

    return TestClient(app), user, settings


def test_login_issues_a_valid_bearer_token() -> None:
    client, user, settings = create_authenticated_client()
    with client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "correct horse battery staple"},
        )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert decode_access_token(response.json()["access_token"], settings) == user.id


def test_signup_creates_account_and_returns_token() -> None:
    client, user, settings = create_authenticated_client()
    with client:
        response = client.post("/api/v1/auth/signup", json={"name": "New User", "email": "new@example.com", "role": "Reviewer", "password": "new-password"})
    assert response.status_code == 201
    assert decode_access_token(response.json()["access_token"], settings) == user.id
    assert response.json()["user"] == {
        "id": user.id,
        "name": "New User",
        "email": "new@example.com",
        "role": "Reviewer",
        "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
        "last_login": None,
    }


def test_login_rejects_invalid_credentials_without_account_details() -> None:
    client, _, _ = create_authenticated_client()
    with client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrong password"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


def test_current_user_dependency_validates_bearer_token() -> None:
    client, user, settings = create_authenticated_client()
    token = create_access_token(user.id, settings)
    with client:
        response = client.get(
            "/test/current-user",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_current_user_dependency_rejects_invalid_bearer_token() -> None:
    client, _, _ = create_authenticated_client()
    with client:
        response = client.get(
            "/test/current-user",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
