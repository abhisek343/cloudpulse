"""
CloudPulse AI - Cost Service
Authentication and registration endpoints.
"""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache, get_cache
from app.core.config import get_settings
from app.core.rate_limit import auth_rate_limit

settings = get_settings()
from app.core.database import get_db
from app.core.security import (
    decode_token,
    create_access_token,
    create_refresh_token,
    generate_csrf_token,
    get_token_ttl_seconds,
    get_password_hash,
    verify_password,
)
from app.models import Organization, User
from app.schemas.auth import (
    LogoutRequest,
    RefreshTokenRequest,
    Token,
    TokenPayload,
    UserCreate,
    UserResponse,
)
from app.services.audit_service import AuditService

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


def _set_refresh_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    """Set refresh/csrf cookies for browser clients."""
    cookie_max_age = settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=cookie_max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=cookie_max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookies(response: Response) -> None:
    """Clear refresh/csrf cookies."""
    response.delete_cookie(settings.refresh_cookie_name, path=f"{settings.api_prefix}/auth")
    response.delete_cookie(settings.csrf_cookie_name, path=f"{settings.api_prefix}/auth")


def _get_revocation_cache_key(cache: RedisCache, jti: str) -> str:
    return cache.generate_key("auth", "revoked", jti)


async def _is_token_revoked(token_data: TokenPayload, cache: RedisCache) -> bool:
    if not token_data.jti:
        return False
    return await cache.exists(_get_revocation_cache_key(cache, token_data.jti))


async def _revoke_token(token: str | None, cache: RedisCache) -> TokenPayload | None:
    if not token:
        return None

    try:
        payload = decode_token(token)
    except JWTError:
        return None

    token_data = TokenPayload(
        sub=payload.get("sub"),
        type=payload.get("type"),
        csrf=payload.get("csrf"),
        jti=payload.get("jti"),
        exp=payload.get("exp"),
    )
    if not token_data.jti:
        return token_data

    ttl_seconds = get_token_ttl_seconds(payload)
    if ttl_seconds > 0:
        await cache.set(
            _get_revocation_cache_key(cache, token_data.jti),
            {"revoked": True},
            ttl=ttl_seconds,
        )

    return token_data


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
) -> User:
    """Dependency to get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(
            sub=user_id,
            type=payload.get("type"),
            csrf=payload.get("csrf"),
            jti=payload.get("jti"),
            exp=payload.get("exp"),
        )
    except JWTError:
        raise credentials_exception

    if token_data.type not in {None, "access"}:
        raise credentials_exception

    if await _is_token_revoked(token_data, cache):
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    request: Request,
    response: Response,
    _: None = Depends(auth_rate_limit("register")),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user and create an organization."""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    
    # Create Organization
    slug = user_in.organization_name.lower().replace(" ", "-")
    org = Organization(
        name=user_in.organization_name,
        slug=slug,
    )
    db.add(org)
    await db.flush()  # Get org.id
    
    # Create User
    user = User(
        organization_id=org.id,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name or user_in.email.split("@")[0],
        role="admin",  # First user is admin
    )
    db.add(user)
    
    # Log Audit
    await AuditService.log(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="REGISTER",
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email, "org_name": org.name},
        ip_address=request.client.host if request.client else None,
    )
    
    await db.commit()
    await db.refresh(user)

    csrf_token = generate_csrf_token()
    refresh_token = create_refresh_token(subject=user.id, csrf_token=csrf_token)
    _set_refresh_cookies(response, refresh_token, csrf_token)

    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    response: Response,
    _: None = Depends(auth_rate_limit("login")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Login to get an access token."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        # Optional: Log failed login attempt (careful with DoS)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Log Successful Login
    await AuditService.log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="LOGIN",
        resource_type="auth",
        details={"user_agent": request.headers.get("user-agent")},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit() # Commit log
    
    access_token = create_access_token(subject=user.id)
    csrf_token = generate_csrf_token()
    refresh_token = create_refresh_token(subject=user.id, csrf_token=csrf_token)
    _set_refresh_cookies(response, refresh_token, csrf_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    response: Response,
    request: Request,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias=settings.csrf_cookie_name)] = None,
    _: None = Depends(auth_rate_limit("refresh")),
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
) -> dict:
    """Exchange a refresh token for a fresh access token."""
    use_cookie_refresh = payload.refresh_token is None and refresh_cookie is not None
    refresh_token = payload.refresh_token or refresh_cookie
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Refresh token is required")

    if use_cookie_refresh:
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(status_code=403, detail="CSRF validation failed")

    try:
        decoded = decode_token(refresh_token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    token_data = TokenPayload(
        sub=decoded.get("sub"),
        type=decoded.get("type"),
        csrf=decoded.get("csrf"),
        jti=decoded.get("jti"),
        exp=decoded.get("exp"),
    )
    if token_data.sub is None or token_data.type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if await _is_token_revoked(token_data, cache):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    next_csrf_token = generate_csrf_token()
    next_refresh_token = create_refresh_token(
        subject=user.id,
        csrf_token=next_csrf_token,
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    access_token = create_access_token(subject=user.id)
    _set_refresh_cookies(response, next_refresh_token, next_csrf_token)
    await _revoke_token(refresh_token, cache)

    await AuditService.log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="REFRESH_TOKEN",
        resource_type="auth",
        details={"user_agent": request.headers.get("user-agent")},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "access_token": access_token,
        "refresh_token": next_refresh_token,
        "token_type": "bearer",
        "csrf_token": next_csrf_token,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    _: None = Depends(auth_rate_limit("logout")),
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
) -> None:
    """Revoke active tokens and clear browser cookies."""
    token_candidates = [
        payload.access_token if payload else None,
        payload.refresh_token if payload else None,
    ]
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token_candidates.append(authorization.split(" ", maxsplit=1)[1])

    subjects: set[str] = set()
    for token in token_candidates:
        token_data = await _revoke_token(token, cache)
        if token_data and token_data.sub:
            subjects.add(token_data.sub)

    for subject in subjects:
        result = await db.execute(select(User).where(User.id == subject))
        user = result.scalar_one_or_none()
        if user is None:
            continue
        await AuditService.log(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            action="LOGOUT",
            resource_type="auth",
            details={"user_agent": request.headers.get("user-agent")},
            ip_address=request.client.host if request.client else None,
        )

    _clear_refresh_cookies(response)


@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user information."""
    return current_user
