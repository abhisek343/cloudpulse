"""
CloudPulse AI - Cost Service Tests
Test configuration and fixtures.
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.main import app


# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cloudpulse_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_organization_data() -> dict:
    """Sample organization data for tests."""
    return {
        "name": "Test Organization",
        "slug": "test-org",
    }


@pytest.fixture
def sample_cloud_account_data() -> dict:
    """Sample cloud account data for tests."""
    return {
        "provider": "aws",
        "account_id": "123456789012",
        "account_name": "Test AWS Account",
    }


@pytest.fixture
def sample_cost_record_data() -> dict:
    """Sample cost record data for tests."""
    from datetime import datetime
    from decimal import Decimal
    
    return {
        "date": datetime.utcnow(),
        "granularity": "daily",
        "service": "Amazon EC2",
        "region": "us-east-1",
        "amount": Decimal("125.50"),
        "currency": "USD",
    }
