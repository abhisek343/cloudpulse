"""
CloudPulse AI - Cost Service
Distributed tracing helpers.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

try:
    from opentelemetry import propagate, trace
    from opentelemetry.context import Context
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    from opentelemetry.trace import SpanKind

    OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency path
    Context = Any  # type: ignore[assignment]
    FastAPIInstrumentor = None  # type: ignore[assignment]
    HTTPXClientInstrumentor = None  # type: ignore[assignment]
    RedisInstrumentor = None  # type: ignore[assignment]
    SQLAlchemyInstrumentor = None  # type: ignore[assignment]
    SpanKind = None  # type: ignore[assignment]
    OTEL_AVAILABLE = False


class _NoopSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None


class _NoopSpanContext:
    def __enter__(self) -> _NoopSpan:
        return _NoopSpan()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _NoopTracer:
    def start_as_current_span(self, name: str, **_: Any) -> _NoopSpanContext:
        return _NoopSpanContext()


_provider: TracerProvider | None = None if OTEL_AVAILABLE else None
_httpx_instrumented = False
_redis_instrumented = False
_sqlalchemy_instrumented = False
_missing_dependency_logged = False


def tracing_enabled() -> bool:
    """Return whether tracing is configured and available."""
    global _missing_dependency_logged

    if not settings.otel_enabled:
        return False

    if settings.otel_exporter_otlp_endpoint:
        endpoint_configured = True
    else:
        endpoint_configured = False
        if not _missing_dependency_logged:
            logger.warning(
                "Tracing is enabled but OTEL_EXPORTER_OTLP_ENDPOINT is not configured; skipping tracing setup."
            )
            _missing_dependency_logged = True

    if endpoint_configured and OTEL_AVAILABLE:
        return True

    if endpoint_configured and not OTEL_AVAILABLE and not _missing_dependency_logged:
        logger.warning(
            "Tracing is enabled but OpenTelemetry packages are not installed; skipping tracing setup."
        )
        _missing_dependency_logged = True

    return False


def get_tracer(name: str) -> Any:
    """Return an OpenTelemetry tracer or a no-op tracer."""
    if tracing_enabled() and OTEL_AVAILABLE:
        return trace.get_tracer(name)
    return _NoopTracer()


def get_span_kind(name: str) -> Any | None:
    """Get an OpenTelemetry span kind by name when tracing is available."""
    if not OTEL_AVAILABLE or SpanKind is None:
        return None
    return getattr(SpanKind, name.upper(), None)


def inject_trace_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject the current span context into outbound carrier headers."""
    carrier = headers or {}
    if tracing_enabled() and OTEL_AVAILABLE:
        propagate.inject(carrier)
    return carrier


def extract_trace_context(headers: Mapping[str, Any] | None) -> Context | None:
    """Extract an inbound tracing context from carrier headers."""
    if not tracing_enabled() or not OTEL_AVAILABLE:
        return None

    if not headers:
        return None

    normalized_headers = {
        str(key): value.decode() if isinstance(value, bytes) else str(value)
        for key, value in headers.items()
    }
    return propagate.extract(normalized_headers)


def _get_provider(service_name: str) -> TracerProvider | None:
    """Get or create the global tracer provider for this process."""
    global _provider

    if not tracing_enabled() or not OTEL_AVAILABLE:
        return None

    if _provider is not None:
        return _provider

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.environment,
        }
    )
    sampler = ParentBased(TraceIdRatioBased(settings.otel_sampler_ratio))
    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint,
                insecure=settings.otel_exporter_otlp_insecure,
            )
        )
    )
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def setup_tracing(
    app: Any | None = None,
    *,
    engine: Any | None = None,
    service_name: str | None = None,
    instrument_redis: bool = False,
) -> callable:
    """Configure tracing for the current process and instrument supported libraries."""
    global _httpx_instrumented, _redis_instrumented, _sqlalchemy_instrumented

    provider = _get_provider(service_name or settings.otel_service_name)
    if provider is None:
        return lambda: None

    if app is not None and not getattr(app.state, "tracing_instrumented", False):
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls=settings.otel_excluded_urls,
        )
        app.state.tracing_instrumented = True

    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _httpx_instrumented = True

    if instrument_redis and not _redis_instrumented:
        RedisInstrumentor().instrument(tracer_provider=provider)
        _redis_instrumented = True

    if engine is not None and not _sqlalchemy_instrumented:
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            tracer_provider=provider,
        )
        _sqlalchemy_instrumented = True

    return lambda: provider.force_flush()
