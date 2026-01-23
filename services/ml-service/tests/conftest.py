"""
CloudPulse AI - ML Service
Test configuration and fixtures.
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_cost_data() -> list[dict]:
    """Generate sample cost data for testing."""
    from datetime import datetime, timedelta
    
    base_date = datetime(2026, 1, 1)
    data = []
    
    for i in range(60):  # 60 days of data
        date = base_date + timedelta(days=i)
        # Simulate some variance with a pattern
        base_amount = 100 + (i % 7) * 10  # Weekly pattern
        if i % 30 < 5:  # Month start spike
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
    from datetime import datetime, timedelta
    
    base_date = datetime(2026, 1, 1)
    data = []
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        amount = 100 + (i % 5) * 5
        
        # Inject anomalies
        if i == 15:
            amount = 500  # Spike
        if i == 25:
            amount = 10   # Drop
        
        data.append({
            "date": date,
            "amount": amount,
        })
    
    return data
