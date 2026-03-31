"""
CloudPulse AI - Cost Service
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.cache import cache
from app.core.config import get_settings
from app.core.database import close_db, engine, init_db
from app.core.observability import ObservabilityMiddleware, metrics_response
from app.core.tracing import setup_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    await init_db()
    await cache.connect()
    flush_traces = setup_tracing(
        app,
        engine=engine,
        instrument_redis=True,
    )
    yield
    # Shutdown
    flush_traces()
    await cache.disconnect()
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-Powered Cloud Cost Prediction & Optimization Platform",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )
    
    app.add_middleware(ObservabilityMiddleware)

    # CORS middleware
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
        )
    
    # Include API Routers
    app.include_router(api_router, prefix=settings.api_prefix)
    
    return app


app = create_app()


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "service": "cost-service",
    }


@app.get("/metrics")
async def metrics() -> object:
    """Prometheus scrape endpoint."""
    return metrics_response()
