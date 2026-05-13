"""HTTP-level tests for the Cowork FastAPI router (Wave 149).

Uses Starlette's TestClient — no live server, no SQLite write to the
operator's home dir (every test isolates its own DB via env var).

Tests cover the 10 contract routes from `docs/contracts/COWORK.md`:
  - POST /api/cowork/sessions                    create
  - GET  /api/cowork/sessions                    list
  - GET  /api/cowork/sessions/:slug              fetch
  - POST /api/cowork/sessions/:id/members        add member
  - GET  /api/cowork/sessions/:id/members        list members
  - POST /api/cowork/sessions/:id/heartbeat      presence ping
  - POST /api/cowork/sessions/:id/cursor         cursor publish
  - POST /api/cowork/sessions/:id/handoff        open handoff
  - POST /api/cowork/handoff/:token/accept       accept handoff
  - POST /api/cowork/sessions/:id/end            end session

Stream endpoint (GET /sessions/:id/stream) is tested at the publish/
subscribe level by `tests/test_cowork_presence.py` — TestClient can't
hold a long-running SSE connection clean, so we skip the HTTP layer
there.
"""

from __future__ import annotations

import os
import tempfile
import unittest


def _build_app():
    """Build a fresh FastAPI app with just the Cowork router.

    Bypasses `web_extras/app.py` (which carries a thick stack of
    middleware + 30+ routers). The router under test is self-contained.
    """

    from fastapi import FastAPI
    from web_extras.routers import cowork as cowork_router

    app = FastAPI()
    app.include_router(cowork_router.router)
    return app


class CoworkRouterCase(unittest.TestCase):
    """Base case: fresh SQLite per test, isolated tracker/store."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp.close()
        os.environ["TARS_COWORK_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_COWORK_STORE", None)

        from backend.core.cowork import reset_store, reset_tracker
        from backend.core.cowork.stream import reset_subscribers
        reset_store()
        reset_tracker()
        reset_subscribers()

        from starlette.testclient import TestClient
        self.app = _build_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        from backend.core.cowork import reset_store, reset_tracker
        from backend.core.cowork.stream import reset_subscribers
        reset_store()
        reset_tracker()
        reset_subscribers()
        for path in (
            self._tmp.name,
            self._tmp.name + "-shm",
            self._tmp.name + "-wal",
            self._tmp.name + "-journal",
        ):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        os.environ.pop("TARS_COWORK_DB_PATH", None)


# ---------- sessions --------------------------------------------------------


class TestSessions(CoworkRouterCase):
    def test_create_session_returns_full_record(self) -> None:
        r = self.client.post(
            "/api/cowork/sessions",
            json={"name": "Smoke", "owner_user_id": "u_a"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["name"], "Smoke")
        self.assertEqual(body["owner_user_id"], "u_a")
        self.assertEqual(body["status"], "live")
        self.assertTrue(body["slug"].startswith("smoke-"))
        self.assertIn("id", body)

    def test_list_sessions_filters_by_owner(self) -> None:
        self.client.post("/api/cowork/sessions", json={"name": "A", "owner_user_id": "u_a"})
        self.client.post("/api/cowork/sessions", json={"name": "B", "owner_user_id": "u_b"})
        r = self.client.get("/api/cowork/sessions", params={"owner_user_id": "u_a"})
        self.assertEqual(r.status_code, 200)
        names = [s["name"] for s in r.json()["sessions"]]
        self.assertEqual(names, ["A"])

    def test_get_session_by_slug_or_id(self) -> None:
        created = self.client.post(
            "/api/cowork/sessions", json={"name": "Path test", "owner_user_id": "u_a"}
        ).json()
        # by slug
        r1 = self.client.get(f"/api/cowork/sessions/{created['slug']}")
        # by id
        r2 = self.client.get(f"/api/cowork/sessions/{created['id']}")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["id"], r2.json()["id"])

    def test_get_session_404_on_unknown(self) -> None:
        r = self.client.get("/api/cowork/sessions/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_end_session_idempotent(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u_a"}
        ).json()
        r1 = self.client.post(f"/api/cowork/sessions/{s['id']}/end")
        r2 = self.client.post(f"/api/cowork/sessions/{s['id']}/end")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r1.json()["ok"])
        self.assertFalse(r2.json()["ok"])  # second end is a no-op


# ---------- members ---------------------------------------------------------


class TestMembers(CoworkRouterCase):
    def test_add_member_returns_token_exactly_once(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u_a"}
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/members",
            json={"display_name": "Alice", "user_id": "u_a", "role": "owner"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("token", body)
        self.assertTrue(len(body["token"]) > 30)
        self.assertEqual(body["role"], "owner")
        self.assertEqual(body["color"], "#6366F1")  # first palette colour

        # List endpoint must NOT leak the token.
        lr = self.client.get(f"/api/cowork/sessions/{s['id']}/members")
        for m in lr.json()["members"]:
            self.assertNotIn("token", m)

    def test_add_member_session_not_found(self) -> None:
        r = self.client.post(
            "/api/cowork/sessions/cw_bogus/members",
            json={"display_name": "X"},
        )
        self.assertEqual(r.status_code, 404)


# ---------- presence + cursor ----------------------------------------------


class TestPresenceAndCursor(CoworkRouterCase):
    def test_heartbeat_succeeds_with_valid_token(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u"}
        ).json()
        m = self.client.post(
            f"/api/cowork/sessions/{s['id']}/members",
            json={"display_name": "A"},
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/heartbeat",
            json={"member_token": m["token"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["ok"])

    def test_heartbeat_rejects_bad_token(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u"}
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/heartbeat",
            json={"member_token": "bogus"},
        )
        self.assertEqual(r.status_code, 401)

    def test_cursor_publish_for_editor_role(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u"}
        ).json()
        m = self.client.post(
            f"/api/cowork/sessions/{s['id']}/members",
            json={"display_name": "A", "role": "editor"},
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/cursor",
            json={"member_token": m["token"], "path": "plan.md", "line": 12, "col": 4},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["path"], "plan.md")
        self.assertEqual(r.json()["line"], 12)

    def test_cursor_rejects_viewer_role(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u"}
        ).json()
        m = self.client.post(
            f"/api/cowork/sessions/{s['id']}/members",
            json={"display_name": "Viewer", "role": "viewer"},
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/cursor",
            json={"member_token": m["token"], "path": "x", "line": 0, "col": 0},
        )
        self.assertEqual(r.status_code, 403)


# ---------- handoff ---------------------------------------------------------


class TestHandoff(CoworkRouterCase):
    def test_open_and_accept_transfers_ownership(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u_a"}
        ).json()
        h = self.client.post(
            f"/api/cowork/sessions/{s['id']}/handoff",
            json={"from_user_id": "u_a", "to_email": "b@example.com"},
        )
        self.assertEqual(h.status_code, 200, h.text)
        token = h.json()["token"]

        acc = self.client.post(
            f"/api/cowork/handoff/{token}/accept",
            json={"accepted_by_user_id": "u_b"},
        )
        self.assertEqual(acc.status_code, 200, acc.text)

        # Owner has switched.
        s2 = self.client.get(f"/api/cowork/sessions/{s['id']}").json()
        self.assertEqual(s2["owner_user_id"], "u_b")

    def test_open_handoff_rejects_non_owner(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u_a"}
        ).json()
        r = self.client.post(
            f"/api/cowork/sessions/{s['id']}/handoff",
            json={"from_user_id": "u_intruder"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("owner", r.json()["detail"].lower())

    def test_double_accept_loses_race(self) -> None:
        s = self.client.post(
            "/api/cowork/sessions", json={"name": "X", "owner_user_id": "u_a"}
        ).json()
        h = self.client.post(
            f"/api/cowork/sessions/{s['id']}/handoff",
            json={"from_user_id": "u_a"},
        ).json()
        self.client.post(
            f"/api/cowork/handoff/{h['token']}/accept",
            json={"accepted_by_user_id": "u_b"},
        )
        r = self.client.post(
            f"/api/cowork/handoff/{h['token']}/accept",
            json={"accepted_by_user_id": "u_c"},
        )
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
