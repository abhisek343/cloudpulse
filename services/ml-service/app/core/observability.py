"""
CloudPulse AI - ML Service
Observability helpers and Prometheus metrics.
"""
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "cloudpulse_ml_service_http_requests_total",
    "Total HTTP requests handled by the ML service.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "cloudpulse_ml_service_http_request_duration_seconds",
    "HTTP request latency for the ML service.",
    ["method", "path"],
)
PREDICTION_DURATION = Histogram(
    "cloudpulse_ml_service_prediction_duration_seconds",
    "Time spent generating cost predictions.",
    ["status"],
)
DETECTION_DURATION = Histogram(
    "cloudpulse_ml_service_detection_duration_seconds",
    "Time spent running anomaly detection.",
    ["status"],
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
        except Exception:
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
