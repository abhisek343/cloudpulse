"""
CloudPulse AI - Cost Service
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
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")

    settings = Settings()

    assert settings.jwt_secret_key == "prod-secret-0123456789abcdef012345"
    get_settings.cache_clear()


def test_production_requires_secure_auth_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production must not allow insecure auth cookies."""
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-secret-0123456789abcdef012345")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        Settings()

    get_settings.cache_clear()


def test_production_live_sync_requires_credentials_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production live cloud sync must encrypt stored credentials."""
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-secret-0123456789abcdef012345")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("ALLOW_LIVE_CLOUD_SYNC", "true")
    monkeypatch.delenv("ACCOUNT_CREDENTIALS_KEY", raising=False)

    with pytest.raises(ValueError, match="ACCOUNT_CREDENTIALS_KEY"):
        Settings()

    get_settings.cache_clear()
