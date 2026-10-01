import asyncio

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.db.mongodb import DatabaseUnavailableError, MongoDB


class FakeAdmin:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def command(self, name: str) -> dict[str, int]:
        assert name == "ping"
        if self.error is not None:
            raise self.error
        return {"ok": 1}


class FakeClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.admin = FakeAdmin(error)
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    def __getitem__(self, name: str) -> dict[str, str]:
        return {"database": name}


def settings_with_database_uri() -> Settings:
    return Settings.from_environment({"TRUSTLENS_MONGODB_URI": "mongodb://localhost:27017"})


def test_unconfigured_database_is_unavailable_without_creating_a_client() -> None:
    database = MongoDB(Settings.from_environment({}))

    assert asyncio.run(database.connect()) is False
    assert database.is_available is False
    with pytest.raises(DatabaseUnavailableError):
        database.database()


def test_failed_ping_closes_client_and_keeps_database_unavailable() -> None:
    fake_client = FakeClient(ServerSelectionTimeoutError("unreachable"))
    database = MongoDB(
        settings_with_database_uri(), client_factory=lambda _uri, **_options: fake_client
    )

    assert asyncio.run(database.connect()) is False
    assert fake_client.closed is True
    assert database.is_available is False


def test_successful_ping_exposes_database_and_closes_on_shutdown() -> None:
    fake_client = FakeClient()
    database = MongoDB(
        settings_with_database_uri(), client_factory=lambda _uri, **_options: fake_client
    )

    assert asyncio.run(database.connect()) is True
    assert database.database() == {"database": "trustlens"}
    asyncio.run(database.close())
    assert fake_client.closed is True
    assert database.is_available is False
