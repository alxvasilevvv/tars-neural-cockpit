"""CRUD + state-machine tests for the webhooks SQLite store.

Stdlib unittest only. Each test isolates its own DB via tempfile so
the operator's ``~/.tars/webhooks.sqlite`` is never touched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import unittest

from backend.core.webhooks import (
    DeliveryStatus,
    OutgoingWebhook,
    WebhookStore,
    build_envelope,
    new_token,
    reset_store,
)


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    """Helper base — each test gets its own SQLite file."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".sqlite", delete=False
        )
        self._tmp.close()
        os.environ["TARS_WEBHOOKS_DB_PATH"] = self._tmp.name
        os.environ.pop("TARS_WEBHOOKS_STORE", None)
        reset_store()
        self.store = WebhookStore(self._tmp.name)

    def tearDown(self) -> None:
        for path in (
            self._tmp.name,
            self._tmp.name + "-shm",
            self._tmp.name + "-wal",
            self._tmp.name + "-journal",
        ):
            try:
                os.unlink(path)
            except OSError:
                pass
        os.environ.pop("TARS_WEBHOOKS_DB_PATH", None)
        reset_store()


class TestOutgoingCRUD(_IsolatedStoreCase):
    def test_create_and_get_outgoing(self):
        rec = _run(
            self.store.create_outgoing(
                name="slack",
                url="https://hooks.slack.com/services/X",
                secret=b"shh",
                event_filter=["playbook.*"],
            )
        )
        self.assertTrue(rec.id.startswith("ohk_"))
        self.assertEqual(rec.name, "slack")
        self.assertEqual(rec.event_filter, ["playbook.*"])
        self.assertTrue(rec.active)
        self.assertEqual(rec.secret, b"shh")

        fetched = _run(self.store.get_outgoing(rec.id))
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.id, rec.id)
        self.assertEqual(fetched.url, rec.url)
        self.assertEqual(fetched.secret, b"shh")

    def test_create_outgoing_validates_inputs(self):
        with self.assertRaises(ValueError):
            _run(self.store.create_outgoing(name="", url="x", secret=b"s"))
        with self.assertRaises(ValueError):
            _run(self.store.create_outgoing(name="n", url="", secret=b"s"))
        with self.assertRaises(ValueError):
            _run(self.store.create_outgoing(name="n", url="x", secret=b""))

    def test_list_outgoing_includes_inactive_when_requested(self):
        a = _run(self.store.create_outgoing(name="a", url="https://a", secret=b"s"))
        _ = _run(self.store.create_outgoing(name="b", url="https://b", secret=b"s"))
        _run(self.store.deactivate_outgoing(a.id))

        active_only = _run(self.store.list_outgoing(include_inactive=False))
        self.assertEqual(len(active_only), 1)
        self.assertEqual(active_only[0].name, "b")

        all_rows = _run(self.store.list_outgoing(include_inactive=True))
        self.assertEqual(len(all_rows), 2)

    def test_patch_outgoing_updates_fields(self):
        rec = _run(
            self.store.create_outgoing(
                name="webhookone", url="https://one", secret=b"k"
            )
        )
        patched = _run(
            self.store.patch_outgoing(
                rec.id,
                {
                    "url": "https://two",
                    "name": "webhooktwo",
                    "active": False,
                    "event_filter": ["hil.*", "agent.created"],
                },
            )
        )
        self.assertIsNotNone(patched)
        assert patched is not None
        self.assertEqual(patched.url, "https://two")
        self.assertEqual(patched.name, "webhooktwo")
        self.assertFalse(patched.active)
        self.assertEqual(patched.event_filter, ["hil.*", "agent.created"])

    def test_patch_outgoing_returns_none_for_missing(self):
        out = _run(self.store.patch_outgoing("ohk_missing", {"active": False}))
        self.assertIsNone(out)

    def test_patch_outgoing_validates_event_filter_type(self):
        rec = _run(self.store.create_outgoing(name="n", url="https://x", secret=b"k"))
        with self.assertRaises(ValueError):
            _run(self.store.patch_outgoing(rec.id, {"event_filter": "playbook.*"}))

    def test_list_active_outgoing_for_matches_globs(self):
        _run(self.store.create_outgoing(
            name="all", url="https://all", secret=b"k", event_filter=["*"]
        ))
        _run(self.store.create_outgoing(
            name="pb", url="https://pb", secret=b"k", event_filter=["playbook.*"]
        ))
        _run(self.store.create_outgoing(
            name="hil", url="https://hil", secret=b"k", event_filter=["hil.requested"]
        ))
        inactive = _run(self.store.create_outgoing(
            name="off", url="https://off", secret=b"k", event_filter=["*"]
        ))
        _run(self.store.deactivate_outgoing(inactive.id))

        matched = _run(self.store.list_active_outgoing_for("playbook.started"))
        names = sorted(w.name for w in matched)
        self.assertEqual(names, ["all", "pb"])

        matched_hil = _run(self.store.list_active_outgoing_for("hil.requested"))
        names_hil = sorted(w.name for w in matched_hil)
        self.assertEqual(names_hil, ["all", "hil"])

        matched_misc = _run(self.store.list_active_outgoing_for("anchor.completed"))
        self.assertEqual([w.name for w in matched_misc], ["all"])

    def test_outgoing_matches_helper_respects_active_flag(self):
        w = OutgoingWebhook(
            id="ohk_x",
            name="x",
            url="https://x",
            secret=b"k",
            event_filter=["*"],
            active=False,
        )
        self.assertFalse(w.matches("anything"))
        w.active = True
        self.assertTrue(w.matches("anything"))


class TestIncomingCRUD(_IsolatedStoreCase):
    def test_create_incoming_mints_token(self):
        rec = _run(
            self.store.create_incoming(
                name="github-actions",
                trigger_playbook_id="pb_smoke",
            )
        )
        self.assertTrue(rec.id.startswith("ihk_"))
        self.assertGreater(len(rec.token), 16)
        self.assertEqual(rec.trigger_playbook_id, "pb_smoke")
        self.assertTrue(rec.active)

        fetched = _run(self.store.get_incoming(rec.id))
        assert fetched is not None
        self.assertEqual(fetched.token, rec.token)

    def test_create_incoming_accepts_explicit_token(self):
        token = new_token()
        rec = _run(
            self.store.create_incoming(name="n", token=token)
        )
        by_token = _run(self.store.get_incoming_by_token(token))
        assert by_token is not None
        self.assertEqual(by_token.id, rec.id)

    def test_create_incoming_validates_name(self):
        with self.assertRaises(ValueError):
            _run(self.store.create_incoming(name=""))

    def test_get_incoming_by_unknown_token_returns_none(self):
        out = _run(self.store.get_incoming_by_token("does-not-exist"))
        self.assertIsNone(out)

    def test_deactivate_incoming(self):
        rec = _run(self.store.create_incoming(name="n"))
        out = _run(self.store.deactivate_incoming(rec.id))
        assert out is not None
        self.assertFalse(out.active)
        # Token still matches but record is inactive.
        again = _run(self.store.get_incoming_by_token(rec.token))
        assert again is not None
        self.assertFalse(again.active)


class TestDeliveryStateMachine(_IsolatedStoreCase):
    def _make_webhook(self) -> OutgoingWebhook:
        return _run(
            self.store.create_outgoing(
                name="hook",
                url="https://example/hook",
                secret=b"k",
                event_filter=["playbook.*"],
            )
        )

    def test_create_delivery_starts_pending(self):
        hook = self._make_webhook()
        envelope = build_envelope("playbook.started", {"playbook_id": "p1"})
        delivery = _run(
            self.store.create_delivery(
                webhook_id=hook.id,
                event_id=envelope["id"],
                event_type=envelope["type"],
                payload_json='{"id":"x"}',
            )
        )
        self.assertEqual(delivery.status, DeliveryStatus.PENDING)
        self.assertEqual(delivery.attempts, 0)
        self.assertIsNotNone(delivery.next_attempt_at)

    def test_patch_delivery_walks_through_states(self):
        hook = self._make_webhook()
        delivery = _run(
            self.store.create_delivery(
                webhook_id=hook.id,
                event_id="evt_1",
                event_type="playbook.started",
                payload_json="{}",
            )
        )
        # Move to RETRY with attempt counter
        out = _run(
            self.store.patch_delivery(
                delivery.id,
                {
                    "status": DeliveryStatus.RETRY,
                    "attempts": 1,
                    "last_error": "HTTP 500",
                    "next_attempt_at": time.time() + 30.0,
                },
            )
        )
        assert out is not None
        self.assertEqual(out.status, DeliveryStatus.RETRY)
        self.assertEqual(out.attempts, 1)
        self.assertEqual(out.last_error, "HTTP 500")

        # Then SUCCESS
        out2 = _run(
            self.store.patch_delivery(
                delivery.id,
                {"status": DeliveryStatus.SUCCESS, "last_status_code": 200},
            )
        )
        assert out2 is not None
        self.assertEqual(out2.status, DeliveryStatus.SUCCESS)
        self.assertEqual(out2.last_status_code, 200)

    def test_patch_delivery_with_status_string(self):
        hook = self._make_webhook()
        delivery = _run(
            self.store.create_delivery(
                webhook_id=hook.id,
                event_id="evt_2",
                event_type="playbook.started",
                payload_json="{}",
            )
        )
        out = _run(
            self.store.patch_delivery(
                delivery.id, {"status": DeliveryStatus.FAILED.value}
            )
        )
        assert out is not None
        self.assertEqual(out.status, DeliveryStatus.FAILED)

    def test_list_due_deliveries_skips_success_and_failed(self):
        hook = self._make_webhook()
        d_pending = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e1", event_type="x", payload_json="{}"
        ))
        d_retry = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e2", event_type="x", payload_json="{}"
        ))
        _run(self.store.patch_delivery(
            d_retry.id,
            {"status": DeliveryStatus.RETRY, "next_attempt_at": time.time() - 1.0},
        ))
        d_future = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e3", event_type="x", payload_json="{}"
        ))
        _run(self.store.patch_delivery(
            d_future.id,
            {
                "status": DeliveryStatus.RETRY,
                "next_attempt_at": time.time() + 9999.0,
            },
        ))
        d_done = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e4", event_type="x", payload_json="{}"
        ))
        _run(self.store.patch_delivery(
            d_done.id, {"status": DeliveryStatus.SUCCESS}
        ))

        due = _run(self.store.list_due_deliveries())
        ids = sorted(d.id for d in due)
        self.assertIn(d_pending.id, ids)
        self.assertIn(d_retry.id, ids)
        self.assertNotIn(d_future.id, ids)
        self.assertNotIn(d_done.id, ids)

    def test_list_deliveries_for_webhook_orders_by_created_desc(self):
        hook = self._make_webhook()
        first = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e1", event_type="x", payload_json="{}"
        ))
        # Force a tiny ordering gap.
        time.sleep(0.005)
        second = _run(self.store.create_delivery(
            webhook_id=hook.id, event_id="e2", event_type="x", payload_json="{}"
        ))
        rows = _run(self.store.list_deliveries_for_webhook(hook.id, limit=10))
        self.assertEqual(rows[0].id, second.id)
        self.assertEqual(rows[1].id, first.id)


class TestEnvelopeAndIds(unittest.TestCase):
    def test_build_envelope_shape(self):
        env = build_envelope("playbook.finished", {"steps_run": 3})
        self.assertEqual(set(env.keys()), {"id", "type", "occurred_at", "data"})
        self.assertEqual(env["type"], "playbook.finished")
        self.assertTrue(env["id"].startswith("evt_"))
        self.assertEqual(env["data"], {"steps_run": 3})
        self.assertIsInstance(env["occurred_at"], float)

    def test_envelope_ids_are_unique(self):
        env_a = build_envelope("x", {})
        env_b = build_envelope("x", {})
        self.assertNotEqual(env_a["id"], env_b["id"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
