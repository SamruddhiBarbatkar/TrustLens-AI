from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password
)
from app.db.database import SessionLocal, get_db
from app.db.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegistrationRequest(BaseModel):
    email: str
    full_name: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@"):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value):
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return normalized


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value):
        if len(value) < 8:
            raise ValueError("New password must contain at least 8 characters.")
        return value


def serialize_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": bool(user.is_active)
    }


def authentication_response(user):
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "user": serialize_user(user)
    }


@router.post("/register", status_code=201)
def register(request: RegistrationRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user is not None:
        raise HTTPException(status_code=409, detail="An account already exists for this email.")

    user = User(
        email=request.email,
        full_name=request.full_name,
        password_hash=hash_password(request.password),
        role="CLAIMANT"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return authentication_response(user)


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")

    return authentication_response(user)


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.put("/profile")
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.full_name = request.full_name
    db.commit()
    db.refresh(current_user)
    return serialize_user(current_user)


@router.post("/change-password")
def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password."
        )

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully."}


def ensure_bootstrap_admin():
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password

    if not email or not password:
        return

    if len(password) < 8:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 8 characters.")

    db = SessionLocal()
    try:
        normalized_email = email.strip().lower()
        existing_user = db.query(User).filter(User.email == normalized_email).first()

        if existing_user is None:
            db.add(
                User(
                    email=normalized_email,
                    full_name=settings.bootstrap_admin_name,
                    password_hash=hash_password(password),
                    role="ADMIN"
                )
            )
            db.commit()
    finally:
        db.close()
