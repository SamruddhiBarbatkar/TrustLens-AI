from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_user_repository
from app.db.users import UserAlreadyExistsError, UserRepository
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.services.passwords import hash_password, verify_password
from app.services.tokens import AuthenticationConfigurationError, create_access_token


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, request: Request, repository: Annotated[UserRepository, Depends(get_user_repository)]) -> TokenResponse:
    try:
        user = await repository.create(
            str(payload.email), hash_password(payload.password), name=payload.name, role=payload.role
        )
    except UserAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from None
    return TokenResponse(
        access_token=create_access_token(user.id, request.app.state.settings),
        user=User.model_validate(user.model_dump()),
    )


@router.post("/login", response_model=TokenResponse, summary="Authenticate a user")
async def login(
    payload: LoginRequest,
    request: Request,
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> TokenResponse:
    """Return a bearer token for valid credentials without revealing account existence."""
    user = await repository.find_by_email(str(payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        access_token = create_access_token(user.id, request.app.state.settings)
    except AuthenticationConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from None
    return TokenResponse(access_token=access_token, user=User.model_validate(user.model_dump()))
