"""
Authentication dependency for the ML Service.

User JWTs identify the organization that owns a model. Cost-service calls use
a separate internal token and must carry the organization explicitly.
"""
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.cost_service_url}/api/v1/auth/login",
    auto_error=False,
)


class TokenPayload(BaseModel):
    sub: str | None = None
    organization_id: str | None = None
    caller_type: str = "user"


def _credentials_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
    internal_organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
) -> TokenPayload:
    """Authenticate either a user JWT or an authenticated internal caller."""
    if internal_token is not None:
        configured = settings.internal_service_token
        if not configured or not hmac.compare_digest(internal_token, configured):
            raise _credentials_exception("Invalid internal service credentials")
        if not internal_organization_id:
            raise _credentials_exception("Internal requests must identify an organization")
        return TokenPayload(
            sub="internal:cost-service",
            organization_id=internal_organization_id,
            caller_type="service",
        )

    if not token:
        raise _credentials_exception()

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        token_type = payload.get("type")
        if token_type not in {None, "access"}:
            raise _credentials_exception()
        user_id = payload.get("sub")
        if user_id is None:
            raise _credentials_exception()
        # Legacy tokens without an organization claim are isolated to the user
        # subject instead of sharing an unscoped process-global model.
        organization_id = payload.get("organization_id") or f"user:{user_id}"
        return TokenPayload(sub=str(user_id), organization_id=str(organization_id))
    except JWTError as exc:
        raise _credentials_exception() from exc
