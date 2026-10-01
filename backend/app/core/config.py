import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


class SettingsValidationError(ValueError):
    """Raised when a runtime setting has an invalid value."""


def _read_bool(value: str, name: str) -> bool:
    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    raise SettingsValidationError(f"{name} must be a boolean value.")


def _read_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise SettingsValidationError("TRUSTLENS_API_PORT must be an integer.") from error

    if not 1 <= port <= 65535:
        raise SettingsValidationError("TRUSTLENS_API_PORT must be between 1 and 65535.")
    return port


def _read_positive_int(value: str, name: str) -> int:
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise SettingsValidationError(f"{name} must be an integer.") from error
    if parsed_value < 1:
        raise SettingsValidationError(f"{name} must be greater than zero.")
    return parsed_value


def _read_origins(value: str) -> tuple[str, ...]:
    origins = tuple(origin.strip().rstrip("/") for origin in value.split(",") if origin.strip())
    if "*" in origins:
        raise SettingsValidationError("TRUSTLENS_CORS_ORIGINS must not contain a wildcard.")
    if any(not origin.startswith(("http://", "https://")) for origin in origins):
        raise SettingsValidationError(
            "TRUSTLENS_CORS_ORIGINS entries must start with http:// or https://."
        )
    return origins


@dataclass(frozen=True)
class Settings:
    environment: str
    api_host: str
    api_port: int
    debug: bool
    log_level: str
    mongodb_uri: str | None
    mongodb_database: str
    jwt_secret_key: str | None
    jwt_access_token_expire_minutes: int
    cors_origins: tuple[str, ...]
    tampering_model_path: Path
    ai_detector_model_path: Path
    easyocr_model_storage_path: Path
    easyocr_download_enabled: bool
    uploads_path: Path
    xai_api_key: str | None
    xai_model: str

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if environ is None else environ
        environment = values.get("TRUSTLENS_ENV", "development").strip().lower()
        if environment not in {"development", "test", "production"}:
            raise SettingsValidationError(
                "TRUSTLENS_ENV must be development, test, or production."
            )

        debug_default = "true" if environment == "development" else "false"
        api_host = values.get("TRUSTLENS_API_HOST", "127.0.0.1").strip()
        if not api_host:
            raise SettingsValidationError("TRUSTLENS_API_HOST must not be empty.")

        mongodb_database = values.get("TRUSTLENS_MONGODB_DATABASE", "trustlens").strip()
        if not mongodb_database:
            raise SettingsValidationError("TRUSTLENS_MONGODB_DATABASE must not be empty.")

        mongodb_uri = values.get("TRUSTLENS_MONGODB_URI", "").strip() or None
        jwt_secret_key = values.get("TRUSTLENS_JWT_SECRET_KEY", "").strip() or None
        cors_default = "http://localhost:5173" if environment == "development" else ""
        cors_origins = _read_origins(values.get("TRUSTLENS_CORS_ORIGINS", cors_default))
        default_tampering_model_path = (
            Path(__file__).resolve().parents[3] / "models" / "best_model.pth"
        )
        tampering_model_path = Path(
            values.get("TRUSTLENS_TAMPERING_MODEL_PATH", str(default_tampering_model_path))
        ).expanduser()
        default_ai_detector_model_path = (
            Path(__file__).resolve().parents[3] / "models" / "ai_detector_best.pth"
        )
        ai_detector_model_path = Path(
            values.get("TRUSTLENS_AI_DETECTOR_MODEL_PATH", str(default_ai_detector_model_path))
        ).expanduser()
        default_easyocr_model_storage_path = (
            Path(__file__).resolve().parents[2] / "model_weights" / "easyocr"
        )
        easyocr_model_storage_path = Path(
            values.get(
                "TRUSTLENS_EASYOCR_MODEL_STORAGE_PATH",
                str(default_easyocr_model_storage_path),
            )
        ).expanduser()
        default_uploads_path = Path(__file__).resolve().parents[2] / "uploads"
        uploads_path = Path(
            values.get("TRUSTLENS_UPLOADS_PATH", str(default_uploads_path))
        ).expanduser()
        xai_api_key = values.get("XAI_API_KEY", "").strip() or None
        xai_model = values.get("TRUSTLENS_XAI_MODEL", "grok-4.7").strip() or "grok-4.7"

        if environment == "production":
            if _read_bool(values.get("TRUSTLENS_DEBUG", debug_default), "TRUSTLENS_DEBUG"):
                raise SettingsValidationError("TRUSTLENS_DEBUG must be disabled in production.")
            if jwt_secret_key is None or len(jwt_secret_key) < 32:
                raise SettingsValidationError(
                    "TRUSTLENS_JWT_SECRET_KEY must be at least 32 characters in production."
                )
            if not cors_origins:
                raise SettingsValidationError(
                    "TRUSTLENS_CORS_ORIGINS must be configured in production."
                )

        return cls(
            environment=environment,
            api_host=api_host,
            api_port=_read_port(values.get("TRUSTLENS_API_PORT", "8000")),
            debug=_read_bool(values.get("TRUSTLENS_DEBUG", debug_default), "TRUSTLENS_DEBUG"),
            log_level=values.get("TRUSTLENS_LOG_LEVEL", "INFO").strip().upper(),
            mongodb_uri=mongodb_uri,
            mongodb_database=mongodb_database,
            jwt_secret_key=jwt_secret_key,
            jwt_access_token_expire_minutes=_read_positive_int(
                values.get("TRUSTLENS_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"),
                "TRUSTLENS_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            ),
            cors_origins=cors_origins,
            tampering_model_path=tampering_model_path,
            ai_detector_model_path=ai_detector_model_path,
            easyocr_model_storage_path=easyocr_model_storage_path,
            easyocr_download_enabled=_read_bool(
                values.get("TRUSTLENS_EASYOCR_DOWNLOAD_ENABLED", "false"),
                "TRUSTLENS_EASYOCR_DOWNLOAD_ENABLED",
            ),
            uploads_path=uploads_path,
            xai_api_key=xai_api_key,
            xai_model=xai_model,
        )
