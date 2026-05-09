"""OpenTelemetry wrapper — opt-in OTLP export (Wave 73 Feature 6).

What this gives you:

- Call :func:`init_otel` from the FastAPI lifespan. It is a no-op
  unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set AND the SDK +
  exporter packages are importable. Both conditions guard with
  try-import so missing optional deps don't crash the host.
- Call :func:`start_span(name, **attrs)` as a context manager
  anywhere in the code. When OTel is initialised the call yields
  a real span; otherwise it yields a no-op object.
- :func:`span_for_trace_summary` wraps the existing
  :mod:`backend.core.meeet.trace_summary` rebuild so a single
  ``trace_id`` propagates between meeet's event store and any
  OTLP backend (Honeycomb, Tempo, Datadog, ...).

This module deliberately does NOT auto-instrument FastAPI/HTTPX —
that would be a behaviour change. The point of v0.1 is to land a
real OTel exporter wired to our trace_id surface so the cockpit's
"observability" claim stops being a lie. Operators who want full
auto-instrumentation can add the ``opentelemetry-instrumentation-*``
packages and call ``FastAPIInstrumentor.instrument_app`` on the
exported ``app``.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Iterator


log = logging.getLogger("tars.observability.otel")


_INITIALIZED = False
_TRACER = None


def _otlp_endpoint() -> str | None:
    raw = (
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )
    raw = (raw or "").strip()
    return raw or None


def _service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME") or "tars"


def _service_version() -> str:
    return os.getenv("OTEL_SERVICE_VERSION") or "9.1.0"


def init_otel() -> bool:
    """Initialise the OTel SDK + OTLP HTTP exporter.

    Returns True iff a tracer was wired. Safe to call multiple times.
    Never raises — missing deps / bad endpoint just leave the module
    in no-op mode.
    """

    global _INITIALIZED, _TRACER
    if _INITIALIZED:
        return _TRACER is not None

    endpoint = _otlp_endpoint()
    if not endpoint:
        _INITIALIZED = True
        log.debug("otel: no OTEL_EXPORTER_OTLP_ENDPOINT, staying in no-op mode")
        return False

    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:  # missing opentelemetry-sdk
        log.warning(
            "otel: SDK not importable (%s); install opentelemetry-api+sdk to enable",
            exc,
        )
        _INITIALIZED = True
        return False

    # Pick the OTLP HTTP exporter — works against any OTLP collector
    # without grpc as a heavy dep. If the user installed the gRPC one
    # instead we fall back to it.
    exporter = None
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=endpoint)
    except Exception as exc:
        log.debug("otel: HTTP exporter not available (%s); trying gRPC", exc)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as _Grpc
            exporter = _Grpc(endpoint=endpoint)
        except Exception as exc2:
            log.warning(
                "otel: no OTLP exporter installed (%s); install "
                "opentelemetry-exporter-otlp to enable export",
                exc2,
            )
            _INITIALIZED = True
            return False

    resource = Resource.create({
        "service.name": _service_name(),
        "service.version": _service_version(),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)
    _TRACER = otel_trace.get_tracer("tars.observability", _service_version())
    _INITIALIZED = True
    log.info(
        "otel: initialised tracer service=%s endpoint=%s",
        _service_name(), endpoint,
    )
    return True


def is_initialized() -> bool:
    return _INITIALIZED and _TRACER is not None


@contextlib.contextmanager
def start_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Open a span if OTel is wired, otherwise yield a no-op stub.

    Usage::

        with start_span("chat.message", thread_id=tid):
            ...
    """

    if not is_initialized() or _TRACER is None:
        yield _NoopSpan()
        return
    span_cm = _TRACER.start_as_current_span(name)
    span = span_cm.__enter__()
    try:
        for k, v in attributes.items():
            try:
                span.set_attribute(k, v if isinstance(v, (str, int, float, bool)) else str(v))
            except Exception:
                pass
        yield span
    except Exception as exc:
        try:
            span.record_exception(exc)
        except Exception:
            pass
        raise
    finally:
        span_cm.__exit__(None, None, None)


@contextlib.contextmanager
def span_for_trace_summary(trace_id: str | None, **attributes: Any) -> Iterator[Any]:
    """Wrap the existing meeet ``trace_summary`` rebuild into an OTel span.

    Usage::

        with span_for_trace_summary(trace_id, kind="rebuild") as span:
            await summary_store.rebuild()

    Attaches the ``meeet.trace_id`` attribute so the OTLP backend can
    cross-reference our local meeet event store.
    """

    attrs = {"meeet.trace_id": trace_id or "", **attributes}
    with start_span("meeet.trace_summary", **attrs) as span:
        yield span


class _NoopSpan:
    """Tiny stub so callers can do `span.set_attribute(...)` unconditionally."""

    def set_attribute(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        return None

    def add_event(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_exception(self, *args: Any, **kwargs: Any) -> None:
        return None

    def end(self) -> None:
        return None


__all__ = [
    "init_otel",
    "is_initialized",
    "span_for_trace_summary",
    "start_span",
]
