from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from app.models.user import UserInDatabase


class UserAlreadyExistsError(RuntimeError):
    """Raised when a user with the normalized email already exists."""


def normalize_email(email: str) -> str:
    """Normalize an email consistently before storage and lookup."""
    return email.strip().casefold()


class UserRepository:
    """Data access layer for the private users collection."""

    collection_name = "users"

    def __init__(self, database: Any) -> None:
        self._collection = database[self.collection_name]

    async def ensure_indexes(self) -> None:
        """Create the database-level uniqueness guarantee for user emails."""
        await self._collection.create_index(
            [("email", ASCENDING)],
            name="uniq_users_email",
            unique=True,
        )

    async def create(self, email: str, password_hash: str, *, name: str | None = None, role: str | None = None) -> UserInDatabase:
        """Persist a user with a password hash, never a plaintext password."""
        normalized_email = normalize_email(email)
        document = {
            "name": name,
            "email": normalized_email,
            "role": role,
            "password_hash": password_hash,
            "created_at": datetime.now(timezone.utc),
            "last_login": None,
        }
        try:
            result = await self._collection.insert_one(document)
        except DuplicateKeyError as error:
            raise UserAlreadyExistsError("A user with this email already exists.") from error

        document["_id"] = result.inserted_id
        return self._to_model(document)

    async def find_by_email(self, email: str) -> UserInDatabase | None:
        """Find a user by normalized email."""
        document = await self._collection.find_one({"email": normalize_email(email)})
        if document is None:
            return None
        return self._to_model(document)

    async def find_by_id(self, user_id: str) -> UserInDatabase | None:
        """Find a user by its immutable database identifier."""
        if not ObjectId.is_valid(user_id):
            return None
        document = await self._collection.find_one({"_id": ObjectId(user_id)})
        if document is None:
            return None
        return self._to_model(document)

    @staticmethod
    def _to_model(document: dict[str, Any]) -> UserInDatabase:
        identifier = document["_id"]
        if isinstance(identifier, ObjectId):
            identifier = str(identifier)
        return UserInDatabase(
            id=str(identifier),
            name=document.get("name"),
            email=document["email"],
            role=document.get("role"),
            password_hash=document["password_hash"],
            created_at=document["created_at"],
            last_login=document.get("last_login"),
        )
