import asyncio
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db.users import UserAlreadyExistsError, UserRepository, normalize_email
from app.services.passwords import hash_password, verify_password


class FakeInsertResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class FakeUsersCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}
        self.indexes: list[tuple[list[tuple[str, int]], dict[str, object]]] = []

    async def create_index(
        self, keys: list[tuple[str, int]], **options: object
    ) -> str:
        self.indexes.append((keys, options))
        return str(options["name"])

    async def insert_one(self, document: dict[str, object]) -> FakeInsertResult:
        email = str(document["email"])
        if email in self.documents:
            raise DuplicateKeyError("duplicate email")
        stored = dict(document)
        inserted_id = ObjectId()
        stored["_id"] = inserted_id
        self.documents[email] = stored
        return FakeInsertResult(inserted_id)

    async def find_one(self, query: dict[str, str]) -> dict[str, object] | None:
        if "_id" in query:
            document = next(
                (item for item in self.documents.values() if item["_id"] == query["_id"]),
                None,
            )
        else:
            document = self.documents.get(query["email"])
        return None if document is None else dict(document)


class FakeDatabase:
    def __init__(self) -> None:
        self.users = FakeUsersCollection()

    def __getitem__(self, name: str) -> FakeUsersCollection:
        assert name == "users"
        return self.users


def test_normalize_email_strips_and_casefolds() -> None:
    assert normalize_email("  Ada.Lovelace@EXAMPLE.com ") == "ada.lovelace@example.com"


def test_repository_creates_unique_normalized_users_with_hashes_only() -> None:
    database = FakeDatabase()
    repository = UserRepository(database)
    password_hash = hash_password("correct horse battery staple")

    asyncio.run(repository.ensure_indexes())
    user = asyncio.run(repository.create("  Ada.Lovelace@EXAMPLE.com ", password_hash, name="Ada Lovelace", role="Researcher"))
    found_user = asyncio.run(repository.find_by_email("ada.lovelace@example.com"))

    assert database.users.indexes == [
        ([("email", 1)], {"name": "uniq_users_email", "unique": True})
    ]
    assert user.email == "ada.lovelace@example.com"
    assert user.name == "Ada Lovelace"
    assert user.role == "Researcher"
    assert found_user == user
    assert asyncio.run(repository.find_by_id(user.id)) == user
    assert verify_password("correct horse battery staple", user.password_hash)
    assert "correct horse battery staple" not in str(database.users.documents)
    assert "password" not in database.users.documents[user.email]


def test_repository_rejects_duplicate_normalized_emails() -> None:
    repository = UserRepository(FakeDatabase())
    password_hash = hash_password("correct horse battery staple")

    asyncio.run(repository.create("ada@example.com", password_hash))

    with pytest.raises(UserAlreadyExistsError):
        asyncio.run(repository.create(" ADA@EXAMPLE.COM ", password_hash))
