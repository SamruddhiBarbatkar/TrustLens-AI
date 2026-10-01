from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.auth import LoginRequest


def test_cors_allows_only_configured_frontend_origin() -> None:
    app = create_app(
        Settings.from_environment(
            {
                "TRUSTLENS_ENV": "test",
                "TRUSTLENS_CORS_ORIGINS": "http://localhost:5173",
            }
        )
    )
    client = TestClient(app)

    with client:
        allowed_response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected_response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed_response.status_code == 200
    assert allowed_response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected_response.status_code == 400
    assert "access-control-allow-origin" not in rejected_response.headers


def test_validation_and_unhandled_errors_do_not_expose_internal_details() -> None:
    app = create_app(Settings.from_environment({"TRUSTLENS_ENV": "test"}))

    @app.post("/test/validated")
    async def validation_route(_payload: LoginRequest) -> None:
        return None

    @app.get("/test/error")
    async def error_route() -> None:
        raise RuntimeError("internal-only diagnostic")

    client = TestClient(app, raise_server_exceptions=False)
    with client:
        validation_response = client.post(
            "/test/validated", json={"email": "not-an-email", "password": ""}
        )
        error_response = client.get("/test/error")

    assert validation_response.status_code == 422
    assert validation_response.json() == {"detail": "Request validation failed."}
    assert error_response.status_code == 500
    assert error_response.json() == {"detail": "An unexpected error occurred."}
