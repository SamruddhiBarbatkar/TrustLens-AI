from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.db.users import UserRepository
from app.db.analyses import AnalysisRepository
from app.models.user import User
from app.services.analysis import ImageAnalysisService
from app.services.tokens import (
    AuthenticationConfigurationError,
    decode_access_token,
)


bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(request: Request) -> UserRepository:
    repository = request.app.state.user_repository
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        )
    return repository


def get_analysis_repository(request: Request) -> AnalysisRepository:
    repository = request.app.state.analysis_repository
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service is unavailable.",
        )
    return repository


def get_analysis_service(request: Request) -> ImageAnalysisService:
    service = request.app.state.analysis_service
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service is unavailable.",
        )
    return service


async def get_authenticated_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """Validate bearer credentials before any database-dependent lookup."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = decode_access_token(credentials.credentials, request.app.state.settings)
    except (AuthenticationConfigurationError, InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return user_id


async def get_current_user(
    user_id: Annotated[str, Depends(get_authenticated_user_id)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Resolve the authenticated user without exposing JWT failure details."""

    user = await repository.find_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return User.model_validate(user.model_dump())
