"""
CloudPulse AI - ML Service
Test configuration and fixtures.
"""
import sys
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) in sys.path:
    sys.path.remove(str(SERVICE_ROOT))
sys.path.insert(0, str(SERVICE_ROOT))

from app.core.config import get_settings
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create a valid JWT for authenticated ML endpoints."""
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "test-user",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_cost_data() -> list[dict]:
    """Generate sample cost data for testing."""
    base_date = datetime(2026, 1, 1)
    data = []

    for i in range(60):
        date = base_date + timedelta(days=i)
        base_amount = 100 + (i % 7) * 10
        if i % 30 < 5:
            base_amount *= 1.2

        data.append({
            "date": date,
            "amount": round(base_amount + (i * 0.5), 2),
            "service": "Amazon EC2" if i % 2 == 0 else "Amazon RDS",
        })

    return data


@pytest.fixture
def sample_anomaly_data() -> list[dict]:
    """Generate sample data with anomalies."""
    base_date = datetime(2026, 1, 1)
    data = []

    for i in range(30):
        date = base_date + timedelta(days=i)
        amount = 100 + (i % 5) * 5

        if i == 15:
            amount = 500
        if i == 25:
            amount = 10

        data.append({
            "date": date,
            "amount": amount,
        })

    return data
