import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from bson import ObjectId

from app.db.analyses import AnalysisRepository
from app.schemas.analysis import AnalysisSignal
from app.schemas.xai import (
    AnalysisExplanation,
    ELAExplanation,
    ExplanationFactor,
    FusionExplanation,
    ImageQualityExplanation,
    ModelSignalExplanation,
    OCRExplanation,
    TrustScoreExplanation,
)


class FakeCollection:
    def __init__(self) -> None:
        self.document: dict[str, object] | None = None

    async def insert_one(self, document: dict[str, object]) -> SimpleNamespace:
        self.document = document
        return SimpleNamespace(inserted_id="507f1f77bcf86cd799439012")


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, name: str) -> FakeCollection:
        assert name == "analyses"
        return self.collection


class Cursor:
    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents

    def sort(self, _field: str, _direction: int) -> "Cursor":
        self.documents.sort(key=lambda item: item["created_at"], reverse=True)
        return self

    def skip(self, offset: int) -> "Cursor":
        self.documents = self.documents[offset:]
        return self

    def limit(self, limit: int) -> "Cursor":
        self.documents = self.documents[:limit]
        return self

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, object]:
        if self._index >= len(self.documents):
            raise StopAsyncIteration
        value = self.documents[self._index]
        self._index += 1
        return value


class HistoryCollection(FakeCollection):
    def __init__(self, documents: list[dict[str, object]]) -> None:
        super().__init__()
        self.documents = documents

    def find(self, query: dict[str, ObjectId]) -> Cursor:
        return Cursor([document for document in self.documents if document["owner_id"] == query["owner_id"]])


class HistoryDatabase:
    def __init__(self, collection: HistoryCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> HistoryCollection:
        assert name == "analyses"
        return self.collection


def test_xai_schema_serializes_partial_real_signal_explanations() -> None:
    explanation = AnalysisExplanation(
        overall_summary="The available signals provide decision-support evidence.",
        trust_score=TrustScoreExplanation(
            score=55,
            category="Needs Review",
            contributing_factors=(
                ExplanationFactor(
                    signal="tampering",
                    direction="requires_review",
                    explanation="The tampering classifier returned its recorded classification.",
                ),
            ),
        ),
        tampering=ModelSignalExplanation(
            status="available",
            classification="tampered",
            confidence=0.82,
        ),
        ai_generated=ModelSignalExplanation(status="unavailable"),
        ocr=OCRExplanation(status="available", text_region_count=0),
        image_quality=ImageQualityExplanation(status="available", width=640, height=480),
        ela=ELAExplanation(status="failed"),
        fusion=FusionExplanation(signals_considered=("tampering",)),
    )

    restored = AnalysisExplanation.model_validate(explanation.model_dump(mode="json"))

    assert restored.tampering is not None and restored.tampering.confidence == 0.82
    assert restored.ai_generated is not None and restored.ai_generated.status == "unavailable"
    assert restored.image_quality is not None and restored.image_quality.width == 640
    assert restored.ela is not None and restored.ela.status == "failed"


def test_analysis_repository_persists_optional_xai_explanation() -> None:
    database = FakeDatabase()
    repository = AnalysisRepository(database)
    explanation = AnalysisExplanation(ocr=OCRExplanation(status="available", text_region_count=2))

    record = asyncio.run(
        repository.create(
            "507f1f77bcf86cd799439011",
            {"ocr": AnalysisSignal(status="available", result={"regions": []})},
            explanation=explanation,
        )
    )

    assert database.collection.document is not None
    assert database.collection.document["explanation"] == explanation.model_dump(mode="json")
    assert record.explanation == explanation


def test_analysis_repository_reads_older_documents_without_xai_data() -> None:
    record = AnalysisRepository._to_model(
        {
            "_id": "507f1f77bcf86cd799439012",
            "owner_id": "507f1f77bcf86cd799439011",
            "created_at": datetime.now(timezone.utc),
            "signals": {"ocr": {"status": "unavailable", "message": "Signal is unavailable."}},
        }
    )

    assert record.explanation is None
    assert record.trust_score is None


def test_analysis_repository_treats_empty_legacy_xai_object_as_absent() -> None:
    record = AnalysisRepository._to_model(
        {
            "_id": "507f1f77bcf86cd799439012",
            "owner_id": "507f1f77bcf86cd799439011",
            "created_at": datetime.now(timezone.utc),
            "signals": {"ocr": {"status": "unavailable"}},
            "explanation": {},
        }
    )

    assert record.explanation is None


def test_owner_history_pagination_keeps_legacy_xai_data_private() -> None:
    owner = ObjectId("507f1f77bcf86cd799439011")
    other_owner = ObjectId("507f1f77bcf86cd799439013")
    documents: list[dict[str, object]] = [
        {"_id": ObjectId("507f1f77bcf86cd799439021"), "owner_id": owner, "created_at": datetime(2026, 9, 30, 11, tzinfo=timezone.utc), "signals": {"ocr": {"status": "unavailable"}}},
        {"_id": ObjectId("507f1f77bcf86cd799439022"), "owner_id": owner, "created_at": datetime(2026, 9, 30, 10, tzinfo=timezone.utc), "signals": {"ocr": {"status": "unavailable"}}, "explanation": {}},
        {"_id": ObjectId("507f1f77bcf86cd799439023"), "owner_id": other_owner, "created_at": datetime(2026, 9, 30, 12, tzinfo=timezone.utc), "signals": {"ocr": {"status": "unavailable"}}},
    ]
    repository = AnalysisRepository(HistoryDatabase(HistoryCollection(documents)))

    records = asyncio.run(repository.list_for_owner(str(owner), limit=1, offset=1))

    assert len(records) == 1
    assert records[0].id == "507f1f77bcf86cd799439022"
    assert records[0].owner_id == str(owner)
    assert records[0].explanation is None
