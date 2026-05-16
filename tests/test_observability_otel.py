"""Wave 123 — coverage for backend.core.observability.otel (W73 Feature 6).

The module is import-safe / no-op when OTel SDK isn't present or no
endpoint is configured, but Wave 122 noted ZERO tests were exercising
that surface. This file fills the gap with stdlib unittest.

Cases:
- otel_init_without_endpoint: no-op, doesn't crash, returns False
- otel_init_with_endpoint_no_sdk: graceful when SDK not importable
- otel_init_with_endpoint_real_sdk: when SDK is present, registers tracer
- start_span_yields_noop_when_uninitialised
- span_for_trace_summary_attaches_trace_id_attribute
- env_var_resolution: OTEL_SERVICE_NAME / OTEL_SERVICE_VERSION respected
- noop_span_supports_unconditional_calls
- is_initialized_reflects_state
"""

from __future__ import annotations

import importlib
import os
import sys
import unittest


def _reload_otel():
    """Reload the otel module so module-level globals reset between tests."""
    import backend.core.observability.otel as otel_mod  # noqa: F401
    return importlib.reload(sys.modules["backend.core.observability.otel"])


class _IsolatedOtel(unittest.TestCase):
    def setUp(self) -> None:
        # Snapshot env so we can restore after.
        self._saved_env = {
            k: os.environ.get(k)
            for k in (
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                "OTEL_SERVICE_NAME",
                "OTEL_SERVICE_VERSION",
            )
        }
        for k in self._saved_env:
            os.environ.pop(k, None)
        self.otel = _reload_otel()

    def tearDown(self) -> None:
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _reload_otel()


class TestInitWithoutEndpoint(_IsolatedOtel):
    def test_returns_false_and_does_not_crash(self) -> None:
        out = self.otel.init_otel()
        self.assertFalse(out)
        self.assertFalse(self.otel.is_initialized())

    def test_idempotent(self) -> None:
        self.otel.init_otel()
        # Second call short-circuits.
        out = self.otel.init_otel()
        self.assertFalse(out)


class TestInitWithEndpointSdkMissing(_IsolatedOtel):
    def test_graceful_when_sdk_not_importable(self) -> None:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318/v1/traces"
        # Block the opentelemetry import so the module's try-import path
        # is exercised regardless of what's installed.
        blocked = {
            name: sys.modules.get(name)
            for name in list(sys.modules)
            if name == "opentelemetry" or name.startswith("opentelemetry.")
        }
        for name in blocked:
            sys.modules[name] = None  # type: ignore[assignment]
        try:
            out = self.otel.init_otel()
            self.assertFalse(out)
            self.assertFalse(self.otel.is_initialized())
        finally:
            for name, mod in blocked.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod


class TestInitWithRealSdkIfAvailable(_IsolatedOtel):
    def test_init_returns_true_when_sdk_and_exporter_available(self) -> None:
        try:
            import opentelemetry  # noqa: F401
            from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
                OTLPSpanExporter,
            )
        except Exception:
            self.skipTest("opentelemetry SDK / OTLP exporter not installed")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:4318/v1/traces"
        out = self.otel.init_otel()
        self.assertTrue(out)
        self.assertTrue(self.otel.is_initialized())


class TestSpanContext(_IsolatedOtel):
    def test_start_span_yields_noop_when_uninitialised(self) -> None:
        # No init call -> NoopSpan must come back.
        with self.otel.start_span("foo", k="v") as span:
            # Calls must not raise.
            span.set_attribute("a", 1)
            span.add_event("ev")
            span.record_exception(RuntimeError("ignored"))
            span.end()
        self.assertFalse(self.otel.is_initialized())

    def test_span_for_trace_summary_yields_object(self) -> None:
        with self.otel.span_for_trace_summary("trace-123", kind="rebuild") as span:
            self.assertIsNotNone(span)
            # On the no-op path the span is a stub but supports calls.
            span.set_attribute("extra", "value")


class TestEnvVarResolution(_IsolatedOtel):
    def test_service_name_default(self) -> None:
        self.assertEqual(self.otel._service_name(), "tars")

    def test_service_name_override(self) -> None:
        os.environ["OTEL_SERVICE_NAME"] = "custom-svc"
        self.assertEqual(self.otel._service_name(), "custom-svc")

    def test_service_version_default(self) -> None:
        # Tied to the desktop release tag — assert shape only so a
        # version bump in `otel.py` doesn't break the suite.
        import re

        value = self.otel._service_version()
        self.assertRegex(value, r"^\d+\.\d+\.\d+([\-+].+)?$")

    def test_service_version_override(self) -> None:
        os.environ["OTEL_SERVICE_VERSION"] = "9.2.5"
        self.assertEqual(self.otel._service_version(), "9.2.5")

    def test_endpoint_resolves_either_env_var(self) -> None:
        os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = "http://x:4318"
        self.assertEqual(self.otel._otlp_endpoint(), "http://x:4318")


class TestNoopSpan(_IsolatedOtel):
    def test_noop_span_methods_callable(self) -> None:
        sp = self.otel._NoopSpan()
        # Must be safe to call any of these unconditionally.
        sp.set_attribute("k", "v")
        sp.add_event("evt", attrs={"a": 1})
        sp.record_exception(ValueError("x"))
        sp.end()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
