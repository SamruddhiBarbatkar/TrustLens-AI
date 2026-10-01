from app.schemas.health import HealthResponse


def get_health_status(database_available: bool) -> HealthResponse:
    """Build the public health response without exposing internal details."""
    if database_available:
        return HealthResponse(status="ok", database="available")
    return HealthResponse(status="degraded", database="unavailable")
