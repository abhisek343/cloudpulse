"""
Authentication dependency for ML Service.
Verifies JWT tokens issued by the Cost Service.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.cost_service_url}/api/v1/auth/login")

class TokenPayload(BaseModel):
    sub: str | None = None

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> TokenPayload:
    """Verify the JWT token and return the payload."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return TokenPayload(sub=user_id)
    except JWTError:
        raise credentials_exception
