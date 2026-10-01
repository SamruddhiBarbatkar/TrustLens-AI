from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import User


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: str | None = Field(default=None, max_length=160)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 characters.")
        return value

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
