from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument

from app.models.analysis import AnalysisInDatabase
from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.schemas.xai import AnalysisExplanation


class AnalysisRepository:
    """Data access layer for owner-scoped analysis records."""

    collection_name = "analyses"

    def __init__(self, database: Any) -> None:
        self._collection = database[self.collection_name]

    async def ensure_indexes(self) -> None:
        """Create indexes used by future owner history and report lookups."""
        await self._collection.create_index(
            [("owner_id", ASCENDING), ("created_at", DESCENDING)],
            name="owner_created_at_desc",
        )

    async def create(
        self,
        owner_id: str,
        signals: dict[str, AnalysisSignal],
        trust_score: TrustScore | None = None,
        explanation: AnalysisExplanation | None = None,
        image_artifact_filename: str | None = None,
    ) -> AnalysisInDatabase:
        """Persist results under the authenticated owner only."""
        if not ObjectId.is_valid(owner_id):
            raise ValueError("Owner identifier is invalid.")
        document = {
            "owner_id": ObjectId(owner_id),
            "created_at": datetime.now(timezone.utc),
            "signals": {name: signal.model_dump(mode="json") for name, signal in signals.items()},
            "trust_score": None if trust_score is None else trust_score.model_dump(mode="json"),
            "explanation": None if explanation is None else explanation.model_dump(mode="json"),
            "image_artifact_filename": image_artifact_filename,
        }
        result = await self._collection.insert_one(document)
        document["_id"] = result.inserted_id
        return self._to_model(document)

    async def list_for_owner(self, owner_id: str, limit: int, offset: int) -> list[AnalysisInDatabase]:
        if not ObjectId.is_valid(owner_id):
            return []
        cursor = self._collection.find({"owner_id": ObjectId(owner_id)}).sort(
            "created_at", DESCENDING
        ).skip(offset).limit(limit)
        return [self._to_model(document) async for document in cursor]

    async def find_for_owner(self, analysis_id: str, owner_id: str) -> AnalysisInDatabase | None:
        if not ObjectId.is_valid(analysis_id) or not ObjectId.is_valid(owner_id):
            return None
        document = await self._collection.find_one({"_id": ObjectId(analysis_id), "owner_id": ObjectId(owner_id)})
        return None if document is None else self._to_model(document)

    async def update_report_title(self, analysis_id: str, owner_id: str, report_title: str) -> AnalysisInDatabase | None:
        """Persist a display title only for the authenticated record owner."""
        if not ObjectId.is_valid(analysis_id) or not ObjectId.is_valid(owner_id):
            return None
        result = await self._collection.find_one_and_update(
            {"_id": ObjectId(analysis_id), "owner_id": ObjectId(owner_id)},
            {"$set": {"report_title": report_title}},
            return_document=ReturnDocument.AFTER,
        )
        return None if result is None else self._to_model(result)

    @staticmethod
    def _to_model(document: dict[str, Any]) -> AnalysisInDatabase:
        explanation = document.get("explanation")
        return AnalysisInDatabase(
            id=str(document["_id"]),
            owner_id=str(document["owner_id"]),
            created_at=document["created_at"],
            signals={
                name: AnalysisSignal.model_validate(signal)
                for name, signal in document["signals"].items()
            },
            trust_score=None if document.get("trust_score") is None else TrustScore.model_validate(document["trust_score"]),
            explanation=None if not explanation else AnalysisExplanation.model_validate(explanation),
            report_title=document.get("report_title"),
            image_artifact_filename=document.get("image_artifact_filename"),
        )
