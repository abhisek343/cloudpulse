"""
CloudPulse AI - ML Service
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ml import router as ml_router
from app.core.config import get_settings
from app.core.observability import ObservabilityMiddleware, metrics_response
from app.core.tracing import setup_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup - nothing to initialize for ML service
    flush_traces = setup_tracing(app)
    yield
    # Shutdown
    flush_traces()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ML Service for Cost Prediction and Anomaly Detection",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(ObservabilityMiddleware)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include ML routes
    app.include_router(ml_router, prefix=f"{settings.api_prefix}/ml", tags=["ML"])
    
    return app


app = create_app()


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    from app.services import get_detector, get_predictor
    
    predictor = get_predictor()
    detector = get_detector()
    
    return {
        "status": "healthy",
        "version": settings.app_version,
        "service": "ml-service",
        "models": {
            "predictor_ready": predictor.is_fitted,
            "detector_ready": detector.is_fitted,
        },
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": "CloudPulse AI - ML Service",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/metrics")
async def metrics() -> object:
    """Prometheus scrape endpoint."""
    return metrics_response()
