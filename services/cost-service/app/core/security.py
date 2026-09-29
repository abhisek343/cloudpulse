"""
CloudPulse AI - Cost Service
Security utilities for authentication and authorization.
"""
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from jose import jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_ALGORITHM = "sha256"
HASH_PREFIX = "pbkdf2_sha256"

SENSITIVE_CREDENTIAL_KEYS = frozenset(
    {
        "access_key_id",
        "secret_access_key",
        "session_token",
        "client_secret",
        "service_account_json",
        "service_account_file",
        "api_key",
        "token",
        "password",
    }
)


def _contains_sensitive_credentials(credentials: dict[str, Any]) -> bool:
    return any(key.lower() in SENSITIVE_CREDENTIAL_KEYS for key in credentials)


def _without_sensitive_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
    """Keep demo metadata while ensuring unexpected secrets are never stored plaintext."""
    return {
        key: value
        for key, value in credentials.items()
        if key.lower() not in SENSITIVE_CREDENTIAL_KEYS
    }


def _is_live_credential_context(credentials: dict[str, Any]) -> bool:
    mode = str(credentials.get("mode", settings.cloud_sync_mode)).lower()
    return mode == "live" or settings.cloud_sync_mode == "live"


def _get_credentials_fernet() -> Fernet | None:
    """Return a Fernet instance when credential encryption is configured."""
    if not settings.account_credentials_key:
        return None

    try:
        return Fernet(settings.account_credentials_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("ACCOUNT_CREDENTIALS_KEY is invalid.") from exc


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    organization_id: str | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    issued_at = datetime.now(timezone.utc)
    to_encode = {
        "exp": expire,
        "iat": issued_at,
        "jti": str(uuid4()),
        "sub": str(subject),
        "type": "access",
    }
    if organization_id:
        to_encode["organization_id"] = str(organization_id)
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(
    subject: str | Any,
    csrf_token: str,
    expires_delta: timedelta | None = None,
    organization_id: str | None = None,
) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    issued_at = datetime.now(timezone.utc)
    to_encode = {
        "exp": expire,
        "iat": issued_at,
        "jti": str(uuid4()),
        "sub": str(subject),
        "type": "refresh",
        "csrf": csrf_token,
    }
    if organization_id:
        to_encode["organization_id"] = str(organization_id)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def get_token_ttl_seconds(payload: dict[str, Any]) -> int:
    """Return the remaining lifetime for a decoded token payload."""
    exp = payload.get("exp")
    if isinstance(exp, datetime):
        expires_at = exp.astimezone(timezone.utc)
    elif isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    elif isinstance(exp, str) and exp.isdigit():
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    else:
        raise ValueError("Token payload does not contain a valid exp claim")

    remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(remaining, 0)


def generate_csrf_token() -> str:
    """Generate a CSRF token suitable for the refresh cookie flow."""
    return base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("=")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    if hashed_password.startswith(f"{HASH_PREFIX}$"):
        try:
            _, iterations, salt_b64, digest_b64 = hashed_password.split("$", maxsplit=3)
        except ValueError:
            return False

        derived_key = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            plain_password.encode("utf-8"),
            base64.b64decode(salt_b64),
            int(iterations),
        )
        expected = base64.b64decode(digest_b64)
        return hmac.compare_digest(derived_key, expected)

    if hashed_password.startswith("$pbkdf2-sha256$"):
        from passlib.hash import pbkdf2_sha256

        return pbkdf2_sha256.verify(plain_password, hashed_password)

    return False


def get_password_hash(password: str) -> str:
    """Generate a PBKDF2-SHA256 hash with a random salt."""
    salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(derived_key).decode("ascii")
    return f"{HASH_PREFIX}${PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"


def encrypt_credentials(credentials: dict[str, Any] | None) -> dict[str, Any] | None:
    """Encrypt provider credentials, failing closed for live configurations."""
    if credentials is None:
        return None

    fernet = _get_credentials_fernet()
    if fernet is None:
        if _is_live_credential_context(credentials) and credentials:
            raise RuntimeError(
                "ACCOUNT_CREDENTIALS_KEY is required before storing live provider credentials."
            )
        return _without_sensitive_credentials(credentials)

    payload = json.dumps(credentials).encode("utf-8")
    ciphertext = fernet.encrypt(payload).decode("utf-8")
    return {"_encrypted": True, "ciphertext": ciphertext}


def decrypt_credentials(credentials: dict[str, Any] | None) -> dict[str, Any]:
    """Decrypt provider credentials stored in the DB."""
    if credentials is None:
        return {}

    if not credentials.get("_encrypted"):
        if _is_live_credential_context(credentials) and _contains_sensitive_credentials(credentials):
            raise RuntimeError(
                "Stored live provider credentials are not encrypted; refusing to use them."
            )
        return _without_sensitive_credentials(credentials)

    fernet = _get_credentials_fernet()
    if fernet is None:
        raise RuntimeError(
            "Account credentials are encrypted but ACCOUNT_CREDENTIALS_KEY is not configured."
        )

    ciphertext = credentials.get("ciphertext")
    if not isinstance(ciphertext, str):
        raise RuntimeError("Encrypted credentials payload is malformed.")

    try:
        plaintext = fernet.decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored account credentials.") from exc

    try:
        data = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Decrypted credentials payload is malformed.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Decrypted credentials payload is malformed.")

    return data
