"""
CloudPulse AI - Cost Service
Health check endpoints.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache, get_cache
from app.core.config import get_settings
from app.core.database import get_db
from app.schemas import HealthCheck

router = APIRouter()
settings = get_settings()


@router.get("/", response_model=HealthCheck)
async def health_check(
    db: AsyncSession = Depends(get_db),
    cache: RedisCache = Depends(get_cache),
) -> HealthCheck:
    """Comprehensive health check for all dependencies."""
    # Check database
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
    
    # Check Redis
    redis_status = "connected"
    try:
        await cache.client.ping()
    except Exception:
        redis_status = "disconnected"
    
    return HealthCheck(
        status="healthy" if db_status == "connected" and redis_status == "connected" else "degraded",
        version=settings.app_version,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready")
async def readiness_check() -> dict:
    """Kubernetes readiness probe."""
    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe."""
    return {"live": True}
