import pytest

from app.core.config import Settings, SettingsValidationError
from app.main import create_app


def test_development_defaults_are_local_and_debug_enabled() -> None:
    settings = Settings.from_environment({})

    assert settings.environment == "development"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.debug is True


def test_production_defaults_disable_debug_and_api_documentation() -> None:
    settings = Settings.from_environment(
        {
            "TRUSTLENS_ENV": "production",
            "TRUSTLENS_JWT_SECRET_KEY": "a-32-character-production-signing-key",
            "TRUSTLENS_CORS_ORIGINS": "https://app.trustlens.example",
        }
    )
    app = create_app(settings)

    assert settings.debug is False
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"TRUSTLENS_ENV": "staging"}, "TRUSTLENS_ENV"),
        ({"TRUSTLENS_API_PORT": "0"}, "TRUSTLENS_API_PORT"),
        ({"TRUSTLENS_DEBUG": "sometimes"}, "TRUSTLENS_DEBUG"),
    ],
)
def test_invalid_settings_are_rejected(values: dict[str, str], message: str) -> None:
    with pytest.raises(SettingsValidationError, match=message):
        Settings.from_environment(values)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {
                "TRUSTLENS_ENV": "production",
                "TRUSTLENS_JWT_SECRET_KEY": "a-32-character-production-signing-key",
                "TRUSTLENS_CORS_ORIGINS": "*",
            },
            "CORS",
        ),
        (
            {
                "TRUSTLENS_ENV": "production",
                "TRUSTLENS_JWT_SECRET_KEY": "short",
                "TRUSTLENS_CORS_ORIGINS": "https://app.trustlens.example",
            },
            "JWT",
        ),
        (
            {
                "TRUSTLENS_ENV": "production",
                "TRUSTLENS_JWT_SECRET_KEY": "a-32-character-production-signing-key",
            },
            "CORS",
        ),
    ],
)
def test_unsafe_production_security_settings_are_rejected(
    values: dict[str, str], message: str
) -> None:
    with pytest.raises(SettingsValidationError, match=message):
        Settings.from_environment(values)
