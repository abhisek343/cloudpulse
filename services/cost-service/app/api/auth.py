"""
CloudPulse AI - Cost Service
Authentication and registration endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Organization, User
from app.schemas.auth import LoginRequest, Token, TokenPayload, UserCreate, UserResponse
from app.services.audit_service import AuditService

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to get the current authenticated user."""
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
        token_data = TokenPayload(sub=user_id)
    except JWTError:
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
    
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
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
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user information."""
    return current_user
