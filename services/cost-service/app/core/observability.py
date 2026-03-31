"""
CloudPulse AI - Cost Service
Observability helpers, metrics, and error handling.
"""
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "cloudpulse_cost_service_http_requests_total",
    "Total HTTP requests handled by the cost service.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "cloudpulse_cost_service_http_request_duration_seconds",
    "HTTP request latency for the cost service.",
    ["method", "path"],
)
SYNC_DURATION = Histogram(
    "cloudpulse_cost_service_sync_duration_seconds",
    "Duration of cloud account sync jobs.",
    ["provider", "mode", "status"],
)
SYNC_TASKS_PUBLISHED = Counter(
    "cloudpulse_cost_service_sync_tasks_published_total",
    "Total sync tasks published to RabbitMQ.",
    ["task_type", "status"],
)
API_ERRORS = Counter(
    "cloudpulse_cost_service_api_errors_total",
    "Unhandled API errors returned by the cost service.",
    ["kind"],
)


def metrics_response() -> Response:
    """Expose Prometheus metrics for scraping."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Capture request metrics and normalize unexpected errors."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
        except SQLAlchemyError:
            API_ERRORS.labels(kind="database").inc()
            response = JSONResponse(
                status_code=503,
                content={"detail": "A database error occurred. Please try again shortly."},
            )
        except Exception:
            API_ERRORS.labels(kind="unhandled").inc()
            response = JSONResponse(
                status_code=500,
                content={"detail": "An unexpected server error occurred."},
            )

        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
        REQUEST_COUNT.labels(
            method=method,
            path=path,
            status=str(response.status_code),
        ).inc()
        return response
