"""W237 — HTTP endpoint coverage for the Models switcher router.

Cases (4):
  - GET /api/providers/list returns array with required keys
  - POST /api/providers/set_active rejects unknown model_id (400)
  - POST /api/providers/set_active accepts valid id + persists to file
  - GET /api/providers/active reads back the persisted active id
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestProvidersRouter(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w237-providers-")
        self._home = Path(self._tmp) / "home"
        self._home.mkdir()
        os.environ["HOME"] = str(self._home)
        # Make sure the persisted active model file lives inside the
        # test home dir; clear env defaults so resolution falls back
        # to "first available" predictably.
        self._active_path = self._home / ".tars" / "active_model"
        os.environ["TARS_ACTIVE_MODEL_PATH"] = str(self._active_path)
        os.environ.pop("TARS_DEFAULT_MODEL", None)
        # Force at least one provider available so list_models picks
        # a real active id even on a bare CI env.
        os.environ["ANTHROPIC_API_KEY"] = "test-key-for-w237"

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available in this environment")
            return

        from web_extras.routers.providers import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("TARS_ACTIVE_MODEL_PATH", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass

    # 1) /list returns array with required keys
    def test_list_returns_required_shape(self) -> None:
        r = self.client.get("/api/providers/list")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertIn("models", body)
        models = body["models"]
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0)
        required = {
            "id",
            "label",
            "provider",
            "in_per_1k_usd",
            "out_per_1k_usd",
            "context_window",
            "available",
            "active",
            "tags",
        }
        for row in models:
            self.assertTrue(
                required.issubset(row.keys()),
                msg=f"missing keys in row {row!r}",
            )
            self.assertIsInstance(row["tags"], list)
            self.assertIsInstance(row["in_per_1k_usd"], float)
            self.assertIsInstance(row["out_per_1k_usd"], float)
        # exactly one row marked active
        active_count = sum(1 for r in models if r.get("active"))
        self.assertEqual(active_count, 1)

    # 2) /set_active rejects unknown model_id (400)
    def test_set_active_rejects_unknown_id(self) -> None:
        r = self.client.post(
            "/api/providers/set_active",
            json={"model_id": "fake:not-a-real-model"},
        )
        self.assertEqual(r.status_code, 400)
        body = r.json()
        # FastAPI default error envelope uses "detail"; W120 wraps it
        # with error_code but keeps detail. Both paths are fine for
        # this assertion.
        msg = body.get("detail") or body.get("error_code") or ""
        self.assertIn("unknown", str(msg).lower())

    # 3) /set_active accepts valid id + persists to file
    def test_set_active_persists_to_file(self) -> None:
        target = "anthropic:claude-3-5-haiku"
        r = self.client.post(
            "/api/providers/set_active",
            json={"model_id": target},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("active"), target)
        # file on disk has the id
        self.assertTrue(self._active_path.is_file())
        self.assertEqual(
            self._active_path.read_text(encoding="utf-8").strip(),
            target,
        )

    # 4) /active reads back the persisted active id
    def test_active_reads_persisted_value(self) -> None:
        target = "anthropic:claude-opus-4-6"
        # Pre-seed the file directly (bypassing /set_active) so
        # this test isolates the read path.
        self._active_path.parent.mkdir(parents=True, exist_ok=True)
        self._active_path.write_text(target, encoding="utf-8")

        r = self.client.get("/api/providers/active")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("model_id"), target)
        self.assertEqual(body.get("label"), "Claude Opus 4.6")


if __name__ == "__main__":
    unittest.main()
