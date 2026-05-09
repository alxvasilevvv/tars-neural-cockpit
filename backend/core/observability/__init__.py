"""Observability (Wave 73 Feature 6) — OpenTelemetry wrapper.

Closes Tasks #32 + #107 which closed in the task list with no
``opentelemetry`` import in the codebase. The wrapper here:

- imports ``opentelemetry.sdk`` lazily; missing deps are a soft
  failure (``init_otel`` becomes a no-op);
- enables the OTLP HTTP exporter only when ``OTEL_EXPORTER_OTLP_ENDPOINT``
  is set;
- bridges the existing meeet ``trace_summary`` rebuild into OTel
  spans so a single trace_id maps cleanly between meeet's event
  store and any OTLP-aware backend (Honeycomb, Tempo, Datadog, ...).
"""

from .otel import (
    init_otel,
    is_initialized,
    span_for_trace_summary,
    start_span,
)

__all__ = [
    "init_otel",
    "is_initialized",
    "span_for_trace_summary",
    "start_span",
]
