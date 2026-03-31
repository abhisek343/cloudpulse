"""
CloudPulse AI - Cost Service
Test configuration and fixtures.
"""
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.cache import get_cache
from app.core.database import Base, get_db
from app.core.rate_limit import rate_limiter
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models import CloudAccount, CostRecord, Organization, User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:cloudpulse-dev-password@localhost:55433/cloudpulse",
)

engine = None
session_factory = None


class FakeRedisClient:
    """Minimal async Redis client for tests."""

    async def ping(self) -> bool:
        return True


class FakeCache:
    """In-memory cache replacement for tests."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}
        self.client = FakeRedisClient()

    async def get(self, key: str) -> object | None:
        return self._store.get(key)

    async def set(self, key: str, value: object, ttl: int | None = None) -> None:
        del ttl
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def flush_pattern(self, pattern: str) -> int:
        prefix = pattern.rstrip("*")
        keys = [key for key in self._store if key.startswith(prefix)]
        for key in keys:
            self._store.pop(key, None)
        return len(keys)

    def clear(self) -> None:
        self._store.clear()

    def generate_key(self, *parts: str) -> str:
        return ":".join(["cloudpulse"] + list(parts))


fake_cache = FakeCache()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    if session_factory is None:
        raise RuntimeError("Test session factory is not initialized")

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def override_get_cache() -> FakeCache:
    return fake_cache


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def test_app() -> AsyncGenerator[None, None]:
    """Set up shared dependency overrides for the test application."""
    global engine, session_factory

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cache] = override_get_cache

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    engine = None
    session_factory = None


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def reset_db() -> AsyncGenerator[None, None]:
    """Reset database state between tests."""
    if engine is None:
        raise RuntimeError("Test engine is not initialized")

    fake_cache.clear()
    rate_limiter.reset()
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for tests."""
    if session_factory is None:
        raise RuntimeError("Test session factory is not initialized")

    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(loop_scope="session")
async def client(test_app: None) -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="session")
async def auth_headers(db_session: AsyncSession) -> dict[str, str]:
    """Create an authenticated admin user and return auth headers."""
    organization = Organization(name="Test Organization", slug="test-organization")
    db_session.add(organization)
    await db_session.flush()

    user = User(
        organization_id=organization.id,
        email="admin@example.com",
        hashed_password=get_password_hash("Password123!"),
        full_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_cost_data(
    db_session: AsyncSession,
    auth_headers: dict[str, str],
) -> dict[str, object]:
    """Seed cloud account and cost records for authenticated tests."""
    result = await db_session.execute(select(User).where(User.email == "admin@example.com"))
    user = result.scalar_one()

    account = CloudAccount(
        organization_id=user.organization_id,
        provider="aws",
        account_id="123456789012",
        account_name="Test AWS Account",
    )
    db_session.add(account)
    await db_session.flush()

    base_date = datetime.now(timezone.utc) - timedelta(days=2)
    records = [
        CostRecord(
            cloud_account_id=account.id,
            date=base_date,
            granularity="daily",
            service="Amazon EC2",
            region="us-east-1",
            amount=Decimal("100.00"),
            currency="USD",
        ),
        CostRecord(
            cloud_account_id=account.id,
            date=base_date + timedelta(days=1),
            granularity="daily",
            service="Amazon S3",
            region="us-west-2",
            amount=Decimal("50.00"),
            currency="USD",
        ),
        CostRecord(
            cloud_account_id=account.id,
            date=base_date + timedelta(days=2),
            granularity="daily",
            service="Amazon EC2",
            region="us-east-1",
            amount=Decimal("75.00"),
            currency="USD",
        ),
    ]
    db_session.add_all(records)
    await db_session.commit()

    return {"account_id": account.id, "headers": auth_headers}
