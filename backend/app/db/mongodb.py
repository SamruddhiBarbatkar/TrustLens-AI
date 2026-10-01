from collections.abc import Callable
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings


class DatabaseUnavailableError(RuntimeError):
    """Raised when an operation requires an unavailable MongoDB connection."""


MongoClientFactory = Callable[..., AsyncMongoClient[Any]]


class MongoDB:
    """Manage one bounded-lifetime asynchronous MongoDB client."""

    def __init__(
        self,
        settings: Settings,
        client_factory: MongoClientFactory = AsyncMongoClient,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory
        self._client: AsyncMongoClient[Any] | None = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def connect(self) -> bool:
        """Connect and ping MongoDB without exposing connection details."""
        if self._client is not None:
            return True
        if self._settings.mongodb_uri is None:
            return False

        client = self._client_factory(
            self._settings.mongodb_uri,
            connectTimeoutMS=5_000,
            serverSelectionTimeoutMS=5_000,
        )
        try:
            await client.admin.command("ping")
        except PyMongoError:
            await client.close()
            return False

        self._client = client
        return True

    async def close(self) -> None:
        """Close the active client during application shutdown."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def database(self) -> Any:
        """Return the configured database only when the client is available."""
        if self._client is None:
            raise DatabaseUnavailableError("MongoDB is not available.")
        return self._client[self._settings.mongodb_database]
