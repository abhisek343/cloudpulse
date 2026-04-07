"""
CloudPulse AI - Cost Service
FastAPI application entry point.
"""
import logging
import signal
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

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler with graceful shutdown."""
    # Startup
    await init_db()
    await cache.connect()
    flush_traces = setup_tracing(
        app,
        engine=engine,
        instrument_redis=True,
    )

    # Register signal handlers for graceful shutdown
    import asyncio
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler(sig: int) -> None:
        logger.info("Received signal %s, initiating graceful shutdown…", signal.Signals(sig).name)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler, sig)

    logger.info("Cost service started (pid=%d)", __import__("os").getpid())
    yield

    # Shutdown — drain resources in order
    logger.info("Shutting down: flushing traces…")
    flush_traces()
    logger.info("Shutting down: disconnecting cache…")
    await cache.disconnect()
    logger.info("Shutting down: closing database pool…")
    await close_db()
    logger.info("Shutdown complete.")


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

    # Global API rate limiting
    from app.core.rate_limit import rate_limiter, RateLimitPolicy, _request_ip
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import JSONResponse

    global_policy = RateLimitPolicy(
        name="api",
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            path = request.url.path
            if path.startswith(("/health", "/metrics", "/docs", "/redoc", "/openapi")):
                return await call_next(request)
            ip = _request_ip(request)  # type: ignore[arg-type]
            try:
                await rate_limiter.hit(f"global:{ip}", global_policy)
            except Exception:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                )
            return await call_next(request)

    app.add_middleware(GlobalRateLimitMiddleware)

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
