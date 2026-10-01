from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Safe user representation for application use and future API responses."""

    id: str
    name: str | None = None
    email: EmailStr
    role: str | None = None
    created_at: datetime
    last_login: datetime | None = None


class UserInDatabase(User):
    """Private persistent user model; never return this model from an API."""

    password_hash: str = Field(repr=False)
