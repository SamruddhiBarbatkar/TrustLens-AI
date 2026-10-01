from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


client = TestClient(create_app(Settings.from_environment({})))


def test_health_endpoint_reports_unconfigured_database_without_details() -> None:
    with client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unavailable"}
