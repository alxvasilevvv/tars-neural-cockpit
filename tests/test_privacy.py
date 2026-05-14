"""W244 -- privacy mode + data plane indicator tests.

Cases (5):
  1) privacy mode blocks anthropic
  2) strict mode blocks meeet.world
  3) local:* models always allowed regardless of mode
  4) recent-flows ring buffer caps at 1000
  5) config persists across reload
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path


class TestPrivacyModule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w244-privacy-")
        self._cfg_path = Path(self._tmp) / "privacy.json"
        os.environ["TARS_PRIVACY_CONFIG_PATH"] = str(self._cfg_path)
        from backend.core import privacy
        privacy.reset_for_tests()

    def tearDown(self) -> None:
        os.environ.pop("TARS_PRIVACY_CONFIG_PATH", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        from backend.core import privacy
        privacy.reset_for_tests()

    def _set_mode(self, mode: str) -> None:
        from backend.core.privacy import PrivacyConfig, save_privacy
        save_privacy(PrivacyConfig.preset_for(mode))  # type: ignore[arg-type]

    # 1) privacy mode blocks an anthropic call.
    def test_privacy_blocks_anthropic(self) -> None:
        from backend.core.privacy import check_can_call
        self._set_mode("privacy")
        allowed, reason = check_can_call("anthropic")
        self.assertFalse(allowed)
        # Either ``local_only_models`` or ``privacy_block_cloud_llm`` is
        # acceptable -- the preset for privacy turns both flags on.
        self.assertIn(reason, ("local_only_models", "privacy_block_cloud_llm"))

    # 2) strict mode blocks the meeet.world ingest.
    def test_strict_blocks_meeet(self) -> None:
        from backend.core.privacy import check_can_call
        self._set_mode("strict")
        allowed, reason = check_can_call("meeet.world")
        self.assertFalse(allowed)
        self.assertEqual(reason, "strict_block_outbound")

    # 3) local:* models always go through, regardless of mode.
    def test_local_models_always_allowed(self) -> None:
        from backend.core.privacy import check_can_call
        for mode in ("normal", "privacy", "strict"):
            self._set_mode(mode)
            allowed, reason = check_can_call("local:llama-3-8b")
            self.assertTrue(
                allowed,
                msg=f"local: was unexpectedly blocked in mode={mode} reason={reason}",
            )
            self.assertEqual(reason, "")
            # Bare "ollama" / "lmstudio" sentinels too.
            for sentinel in ("ollama", "lmstudio", "local"):
                allowed, _ = check_can_call(sentinel)
                self.assertTrue(allowed, msg=f"{sentinel} blocked in {mode}")

    # 4) ring buffer caps at 1000 events.
    def test_ring_buffer_caps_at_1000(self) -> None:
        from backend.core import privacy
        from backend.core.privacy import check_can_call

        privacy.reset_for_tests()
        # Push 1500 events; ring max is 1000.
        for i in range(1500):
            check_can_call(f"local:test-{i % 10}")
        self.assertEqual(privacy._ring_size(), 1000)

        # ``recent_flows`` should honour the request cap (max == ring_max).
        rows = privacy.recent_flows(limit=2000)
        self.assertEqual(len(rows), 1000)
        # Newest first -- last entry written was i=1499 -> dest=local:test-9
        self.assertEqual(rows[0]["dest"], "local:test-9")

    # 5) config persists across a fresh load.
    def test_config_persists_across_reload(self) -> None:
        from backend.core.privacy import (
            PrivacyConfig,
            load_privacy,
            save_privacy,
        )
        from backend.core import privacy

        cfg = PrivacyConfig(
            mode="privacy",
            block_cloud_llm=True,
            block_meeet_telemetry=False,
            block_outbound_connectors=False,
            local_only_models=True,
        )
        save_privacy(cfg)

        # Drop the in-process cache, simulating a fresh import / reboot.
        privacy.reset_for_tests()

        out = load_privacy()
        self.assertEqual(out.mode, "privacy")
        self.assertTrue(out.block_cloud_llm)
        self.assertTrue(out.local_only_models)
        self.assertFalse(out.block_meeet_telemetry)
        self.assertFalse(out.block_outbound_connectors)


class TestPrivacyRouter(unittest.TestCase):
    """Smoke coverage of the HTTP surface."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="tars-w244-router-")
        os.environ["TARS_PRIVACY_CONFIG_PATH"] = str(
            Path(self._tmp) / "privacy.json"
        )
        from backend.core import privacy
        privacy.reset_for_tests()

        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not available")
            return

        from web_extras.routers.privacy import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("TARS_PRIVACY_CONFIG_PATH", None)
        try:
            shutil.rmtree(self._tmp)
        except Exception:
            pass
        from backend.core import privacy
        privacy.reset_for_tests()

    def test_get_config_defaults_to_normal(self) -> None:
        r = self.client.get("/api/privacy/config")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["config"]["mode"], "normal")

    def test_post_config_switches_mode(self) -> None:
        r = self.client.post("/api/privacy/config", json={"mode": "strict"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["config"]["mode"], "strict")
        self.assertTrue(body["config"]["block_cloud_llm"])
        self.assertTrue(body["config"]["block_outbound_connectors"])

    def test_data_plane_snapshot_shape(self) -> None:
        # Trigger a flow to populate the ring.
        from backend.core.privacy import check_can_call
        check_can_call("anthropic")
        check_can_call("local:llama")

        r = self.client.get("/api/privacy/data_plane?limit=10")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("recent_flows", body)
        self.assertIn("allowed_destinations", body)
        self.assertIn("blocked_destinations", body)
        self.assertIn("ring_capacity", body)


if __name__ == "__main__":
    unittest.main()
