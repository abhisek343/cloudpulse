"""
CloudPulse AI - Cost Service
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, kubernetes
from app.api.router import api_router
from app.core.cache import cache
from app.core.config import get_settings
from app.core.database import close_db, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    await init_db()
    await cache.connect()
    yield
    # Shutdown
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
    
    # CORS middleware
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )
    
    # Include API Routers
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(chat.router, prefix=f"{settings.api_prefix}/chat", tags=["AI Analyst"])
    app.include_router(kubernetes.router, prefix=f"{settings.api_prefix}/k8s", tags=["Kubernetes"])
    
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
