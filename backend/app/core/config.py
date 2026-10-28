from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_backend: Literal["sqlite", "mongodb"] = "sqlite"
    database_url: str = "sqlite:///./sql_app.db"
    mongodb_uri: str = "mongodb://127.0.0.1:27017/"
    mongodb_database: str = "trustlens_ai"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 10 * 1024 * 1024
    upload_chunk_bytes: int = 1024 * 1024
    tesseract_path: str | None = None
    jwt_secret_key: str = "dev-only-change-this-secret"
    access_token_minutes: int = 480
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "TrustLens Administrator"
    detector_policy_mode: Literal[
        "LEGACY",
        "HYBRID_CANDIDATE",
        "HYBRID_V1",
        "HYBRID_V2",
    ] = "LEGACY"
    ai_generation_candidate_path: Path = (
        BACKEND_DIR
        / "training_outputs"
        / "ai_detector_multigen_candidate.pth"
    )
    evidence_authenticity_candidate_path: Path = (
        BACKEND_DIR
        / "training_outputs"
        / "evidence_authenticity_three_class_candidate.pth"
    )
    multiview_candidate_path: Path = (
        BACKEND_DIR
        / "training_outputs"
        / "evidence_authenticity_forensic_multiview_candidate.pth"
    )
    resnet_shadow_candidate_path: Path = (
        BACKEND_DIR
        / "training_outputs"
        / "tampering_multisource_hardnegative_candidate.pth"
    )
    enable_resnet_shadow: bool = True
    enable_multiview_candidate: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173"
        ]
    )
    cors_origin_regex: str | None = (
        r"^https?://(localhost|127\.0\.0\.1):\d+$"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
