"""
CloudPulse AI - ML Service
Configuration tests for production safety rails.
"""
import pytest

from app.core.config import Settings, get_settings


def test_production_rejects_default_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production must not boot with the shared development JWT secret."""
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings()

    get_settings.cache_clear()


def test_production_accepts_explicit_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """A strong explicit secret should be accepted in production."""
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-secret-0123456789abcdef012345")
    monkeypatch.setenv("DEBUG", "false")

    settings = Settings()

    assert settings.jwt_secret_key == "prod-secret-0123456789abcdef012345"
    get_settings.cache_clear()
