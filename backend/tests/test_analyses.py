import asyncio
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from app.api.dependencies import (
    get_analysis_repository,
    get_analysis_service,
    get_user_repository,
)
from app.core.config import Settings
from app.db.analyses import AnalysisRepository
from app.models.analysis import AnalysisInDatabase
from app.models.user import UserInDatabase
from app.main import create_app
from app.schemas.analysis import AnalysisSignal
from app.schemas.trust_score import TrustScore
from app.schemas.xai import AnalysisExplanation, OCRExplanation
from app.services.ai_detector import AIDetectorModelUnavailableError
from app.services.analysis import ImageAnalysisService
from app.services.ela import ELAService
from app.services.ocr import OCRUnavailableError
from app.services.tampering_detector import TamperingModelUnavailableError
from app.services.tokens import create_access_token


class FakeUserRepository:
    def __init__(self, user: UserInDatabase) -> None:
        self.user = user

    async def find_by_id(self, user_id: str) -> UserInDatabase | None:
        return self.user if user_id == self.user.id else None


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.created: AnalysisInDatabase | None = None

    async def create(
        self,
        owner_id: str,
        signals: dict[str, AnalysisSignal],
        trust_score: TrustScore | None = None,
        explanation: AnalysisExplanation | None = None,
        image_artifact_filename: str | None = None,
    ) -> AnalysisInDatabase:
        self.created = AnalysisInDatabase(
            id="507f1f77bcf86cd799439012",
            owner_id=owner_id,
            created_at=datetime.now(timezone.utc),
            signals=signals,
            trust_score=trust_score,
            explanation=explanation,
            image_artifact_filename=image_artifact_filename,
        )
        return self.created

    async def list_for_owner(self, owner_id: str, _limit: int, _offset: int) -> list[AnalysisInDatabase]:
        return [] if self.created is None or self.created.owner_id != owner_id else [self.created]

    async def find_for_owner(self, analysis_id: str, owner_id: str) -> AnalysisInDatabase | None:
        if self.created is not None and self.created.id == analysis_id and self.created.owner_id == owner_id:
            return self.created
        return None

    async def update_report_title(self, analysis_id: str, owner_id: str, report_title: str) -> AnalysisInDatabase | None:
        analysis = await self.find_for_owner(analysis_id, owner_id)
        if analysis is None:
            return None
        self.created = analysis.model_copy(update={"report_title": report_title})
        return self.created


class UnavailableTamperingDetector:
    def predict(self, _image: Image.Image) -> None:
        raise TamperingModelUnavailableError("unavailable")


class UnavailableAIDetector:
    def predict(self, _image: Image.Image) -> None:
        raise AIDetectorModelUnavailableError("unavailable")


class UnavailableOCRService:
    def extract(self, _image: Image.Image) -> None:
        raise OCRUnavailableError("unavailable")


class UnavailableSignalService:
    def analyze(self, _image: Image.Image) -> tuple[dict[str, AnalysisSignal], TrustScore | None]:
        return {"ocr": AnalysisSignal(status="unavailable", message="Signal is unavailable.")}, None

    def explain_evidence(
        self, _signals: dict[str, AnalysisSignal], _trust_score: TrustScore | None
    ) -> AnalysisExplanation:
        return AnalysisExplanation(
            overall_summary="OCR is unavailable.",
            ocr=OCRExplanation(status="unavailable", interpretation="OCR is unavailable."),
        )


class FakeAnalysisCollection:
    def __init__(self) -> None:
        self.indexes: list[tuple[object, dict[str, object]]] = []
        self.document: dict[str, object] | None = None

    async def create_index(self, keys: object, **options: object) -> None:
        self.indexes.append((keys, options))

    async def insert_one(self, document: dict[str, object]) -> SimpleNamespace:
        self.document = document
        return SimpleNamespace(inserted_id="507f1f77bcf86cd799439012")


class FakeDatabase:
    def __init__(self, collection: FakeAnalysisCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> FakeAnalysisCollection:
        assert name == "analyses"
        return self.collection


def test_image_analysis_service_keeps_unavailable_signals_explicit() -> None:
    service = ImageAnalysisService(
        UnavailableTamperingDetector(),  # type: ignore[arg-type]
        UnavailableAIDetector(),  # type: ignore[arg-type]
        UnavailableOCRService(),  # type: ignore[arg-type]
        ELAService(),
    )

    signals, trust_score = service.analyze(Image.new("RGB", (8, 8), "black"))

    assert signals["tampering"].status == "unavailable"
    assert signals["ai_generation"].status == "unavailable"
    assert signals["ocr"].status == "unavailable"
    assert signals["quality"].status == "available"
    assert signals["ela"].status == "available"
    assert trust_score is None


def test_authenticated_analysis_persists_under_token_owner(tmp_path) -> None:
    settings = Settings.from_environment(
        {
            "TRUSTLENS_ENV": "test",
            "TRUSTLENS_JWT_SECRET_KEY": "test-signing-key-that-is-never-used-outside-tests",
            "TRUSTLENS_UPLOADS_PATH": str(tmp_path),
        }
    )
    user = UserInDatabase(
        id="507f1f77bcf86cd799439011",
        email="ada@example.com",
        password_hash="not-returned",
        created_at=datetime.now(timezone.utc),
    )
    repository = FakeAnalysisRepository()
    app = create_app(settings)
    app.dependency_overrides[get_user_repository] = lambda: FakeUserRepository(user)
    app.dependency_overrides[get_analysis_repository] = lambda: repository
    app.dependency_overrides[get_analysis_service] = lambda: UnavailableSignalService()
    token = create_access_token(user.id, settings)
    image = BytesIO()
    Image.new("RGB", (4, 4), "white").save(image, format="PNG")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            headers={"Authorization": f"Bearer {token}"},
            files={"image": ("sample.png", image.getvalue(), "image/png")},
        )

    assert response.status_code == 201
    assert response.json()["signals"]["ocr"]["status"] == "unavailable"
    assert response.json()["trust_score"] is None
    assert response.json()["explanation"]["ocr"]["status"] == "unavailable"
    assert response.json()["source_image_available"] is True
    assert repository.created is not None
    assert repository.created.owner_id == user.id
    assert repository.created.explanation is not None
    assert repository.created.image_artifact_filename is not None
    with TestClient(app) as client:
        source_image = client.get(
            f"/api/v1/analyses/{repository.created.id}/source-image",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert source_image.status_code == 200
    assert source_image.headers["content-type"] == "image/png"
    assert source_image.headers["cache-control"] == "private, no-store"


def test_analysis_repository_persists_owner_and_owner_history_index() -> None:
    collection = FakeAnalysisCollection()
    repository = AnalysisRepository(FakeDatabase(collection))

    asyncio.run(repository.ensure_indexes())
    result = asyncio.run(
        repository.create(
            "507f1f77bcf86cd799439011",
            {"ela": AnalysisSignal(status="available", result={"metric": 0.0})},
        )
    )

    assert collection.indexes[0][1]["name"] == "owner_created_at_desc"
    assert collection.document is not None
    assert result.owner_id == "507f1f77bcf86cd799439011"
    assert result.signals["ela"].status == "available"
    assert result.trust_score is None


def test_analysis_rejects_invalid_upload_and_missing_credentials() -> None:
    app = create_app(Settings.from_environment({"TRUSTLENS_ENV": "test"}))
    client = TestClient(app)

    with client:
        unauthenticated = client.post(
            "/api/v1/analyses",
            files={"image": ("sample.png", b"not an image", "image/png")},
        )

    assert unauthenticated.status_code == 401


def test_analysis_rejects_oversized_upload_before_decoding() -> None:
    settings = Settings.from_environment({"TRUSTLENS_ENV": "test", "TRUSTLENS_JWT_SECRET_KEY": "test-signing-key-that-is-never-used-outside-tests"})
    user = UserInDatabase(id="507f1f77bcf86cd799439011", email="ada@example.com", password_hash="x", created_at=datetime.now(timezone.utc))
    app = create_app(settings)
    app.dependency_overrides[get_user_repository] = lambda: FakeUserRepository(user)
    app.dependency_overrides[get_analysis_repository] = lambda: FakeAnalysisRepository()
    app.dependency_overrides[get_analysis_service] = lambda: UnavailableSignalService()
    token = create_access_token(user.id, settings)
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses", headers={"Authorization": f"Bearer {token}"}, files={"image": ("large.png", b"0" * (10 * 1024 * 1024 + 1), "image/png")})
    assert response.status_code == 413


def test_history_and_report_are_owner_scoped() -> None:
    settings = Settings.from_environment({"TRUSTLENS_ENV": "test", "TRUSTLENS_JWT_SECRET_KEY": "test-signing-key-that-is-never-used-outside-tests"})
    user = UserInDatabase(id="507f1f77bcf86cd799439011", email="ada@example.com", password_hash="x", created_at=datetime.now(timezone.utc))
    repository = FakeAnalysisRepository()
    asyncio.run(repository.create(user.id, {"ela": AnalysisSignal(status="available", result={"value": 0})}))
    app = create_app(settings)
    app.dependency_overrides[get_user_repository] = lambda: FakeUserRepository(user)
    app.dependency_overrides[get_analysis_repository] = lambda: repository
    token = create_access_token(user.id, settings)
    with TestClient(app) as client:
        history = client.get("/api/v1/analyses", headers={"Authorization": f"Bearer {token}"})
        report = client.get("/api/v1/analyses/507f1f77bcf86cd799439012/report", headers={"Authorization": f"Bearer {token}"})
        absent = client.get("/api/v1/analyses/507f1f77bcf86cd799439013/report", headers={"Authorization": f"Bearer {token}"})
    assert history.status_code == 200 and len(history.json()["items"]) == 1
    assert history.json()["items"][0]["explanation"] is None
    assert report.status_code == 200 and report.headers["content-type"] == "application/pdf"
    assert absent.status_code == 404


def test_report_title_is_owner_scoped_and_persisted() -> None:
    settings = Settings.from_environment({"TRUSTLENS_ENV": "test", "TRUSTLENS_JWT_SECRET_KEY": "test-signing-key-that-is-never-used-outside-tests"})
    user = UserInDatabase(id="507f1f77bcf86cd799439011", email="ada@example.com", password_hash="x", created_at=datetime.now(timezone.utc))
    repository = FakeAnalysisRepository()
    asyncio.run(repository.create(user.id, {"ela": AnalysisSignal(status="available", result={"value": 0})}))
    app = create_app(settings)
    app.dependency_overrides[get_user_repository] = lambda: FakeUserRepository(user)
    app.dependency_overrides[get_analysis_repository] = lambda: repository
    token = create_access_token(user.id, settings)
    with TestClient(app) as client:
        renamed = client.patch("/api/v1/analyses/507f1f77bcf86cd799439012/report-title", headers={"Authorization": f"Bearer {token}"}, json={"report_title": "Kitchen claim review"})
        history = client.get("/api/v1/analyses", headers={"Authorization": f"Bearer {token}"})
        missing = client.patch("/api/v1/analyses/507f1f77bcf86cd799439013/report-title", headers={"Authorization": f"Bearer {token}"}, json={"report_title": "No access"})
    assert renamed.status_code == 200 and renamed.json()["report_title"] == "Kitchen claim review"
    assert history.json()["items"][0]["report_title"] == "Kitchen claim review"
    assert missing.status_code == 404
