from fastapi import APIRouter, Request

from app.schemas.health import HealthResponse
from app.services.health import get_health_status


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Check API availability")
def read_health(request: Request) -> HealthResponse:
    """Return the public availability state of the API."""
    return get_health_status(request.app.state.mongodb.is_available)
