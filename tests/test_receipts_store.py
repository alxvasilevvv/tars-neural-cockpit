"""Append + query + day-rotation + last-receipt continuity tests for
the receipt ledger SQLite + NDJSON store (Wave 95).

Stdlib unittest only. Each test isolates its own NDJSON dir + SQLite
file via tempfile.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import tempfile
import unittest

from backend.core.receipts import compute_root, reset_store, verify_chain
from backend.core.receipts.store import ReceiptStore


def _run(coro):
    return asyncio.run(coro)


class _IsolatedStoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.ndjson_dir = os.path.join(self.tmpdir, "nd")
        self.db_path = os.path.join(self.tmpdir, "r.sqlite")
        self.key_path = os.path.join(self.tmpdir, "k.json")
        os.environ["TARS_RECEIPT_DIR"] = self.ndjson_dir
        os.environ["TARS_RECEIPT_DB_PATH"] = self.db_path
        os.environ["TARS_RECEIPT_HOST_KEY_PATH"] = self.key_path
        os.environ.pop("TARS_RECEIPT_STORE", None)
        reset_store()
        self.store = ReceiptStore(
            ndjson_dir=self.ndjson_dir,
            db_path=self.db_path,
            host_key_path=self.key_path,
        )

    def tearDown(self) -> None:
        for path in (
            self.db_path,
            self.db_path + "-shm",
            self.db_path + "-wal",
            self.db_path + "-journal",
        ):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        for var in (
            "TARS_RECEIPT_DIR",
            "TARS_RECEIPT_DB_PATH",
            "TARS_RECEIPT_HOST_KEY_PATH",
        ):
            os.environ.pop(var, None)
        reset_store()


def _utc_day(ts: float) -> str:
    return datetime.datetime.fromtimestamp(
        ts, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d")


class TestAppend(_IsolatedStoreCase):
    def test_first_receipt_has_empty_prev_hash(self):
        r = _run(self.store.append("test.event", "op:alice", None, {}))
        self.assertEqual(r.prev_hash, "")
        self.assertEqual(len(r.hash), 64)
        self.assertTrue(r.signature)

    def test_second_receipt_links_to_first(self):
        r1 = _run(self.store.append("test.event", "op:alice", None, {"i": 1}))
        r2 = _run(self.store.append("test.event", "op:alice", None, {"i": 2}))
        self.assertEqual(r2.prev_hash, r1.hash)
        self.assertNotEqual(r1.hash, r2.hash)

    def test_append_writes_ndjson(self):
        r = _run(self.store.append("test.event", "op:bob", "obj-1", {"k": "v"}))
        path = os.path.join(self.ndjson_dir, _utc_day(r.ts) + ".ndjson")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as fh:
            line = fh.readline().strip()
        body = json.loads(line)
        self.assertEqual(body["id"], r.id)
        self.assertEqual(body["actor"], "op:bob")
        self.assertEqual(body["payload"]["k"], "v")

    def test_append_persists_to_sqlite(self):
        r = _run(self.store.append("test.x", "op:a", None, {"x": 1}))
        rows = _run(self.store.query(actor="op:a"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, r.id)


class TestLastReceipt(_IsolatedStoreCase):
    def test_none_when_empty(self):
        self.assertIsNone(_run(self.store.last_receipt()))

    def test_returns_most_recent(self):
        r1 = _run(self.store.append("a.b", "x", None, {}, ts=100.0))
        r2 = _run(self.store.append("a.b", "x", None, {}, ts=200.0))
        last = _run(self.store.last_receipt())
        assert last is not None
        self.assertEqual(last.id, r2.id)


class TestQuery(_IsolatedStoreCase):
    def test_filter_by_type(self):
        _run(self.store.append("type.a", "x", None, {}))
        _run(self.store.append("type.b", "x", None, {}))
        a = _run(self.store.query(type="type.a"))
        b = _run(self.store.query(type="type.b"))
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertEqual(a[0].type, "type.a")

    def test_filter_by_time_range(self):
        _run(self.store.append("e", "x", None, {}, ts=100.0))
        _run(self.store.append("e", "x", None, {}, ts=200.0))
        _run(self.store.append("e", "x", None, {}, ts=300.0))
        rows = _run(self.store.query(since=150.0, until=250.0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ts, 200.0)

    def test_limit_caps_results(self):
        for _ in range(5):
            _run(self.store.append("e", "x", None, {}))
        rows = _run(self.store.query(limit=2))
        self.assertEqual(len(rows), 2)


class TestDayRotation(_IsolatedStoreCase):
    def test_appends_split_by_utc_day(self):
        # Two timestamps definitely on different UTC days.
        ts_day1 = 1_700_000_000.0  # 2023-11-14 22:13:20 UTC
        ts_day2 = ts_day1 + 86_400  # +1 day
        r1 = _run(
            self.store.append("e", "x", None, {"d": 1}, ts=ts_day1)
        )
        r2 = _run(
            self.store.append("e", "x", None, {"d": 2}, ts=ts_day2)
        )
        path1 = os.path.join(self.ndjson_dir, _utc_day(ts_day1) + ".ndjson")
        path2 = os.path.join(self.ndjson_dir, _utc_day(ts_day2) + ".ndjson")
        self.assertTrue(os.path.exists(path1))
        self.assertTrue(os.path.exists(path2))
        self.assertNotEqual(path1, path2)
        # Continuity: r2.prev_hash == r1.hash even across the day boundary.
        self.assertEqual(r2.prev_hash, r1.hash)


class TestReplayChain(_IsolatedStoreCase):
    def test_replay_returns_full_day_in_order(self):
        ts = 1_700_000_000.0
        receipts = [
            _run(self.store.append("e", "x", None, {"i": i}, ts=ts + i))
            for i in range(4)
        ]
        rs = _run(self.store.replay_chain_for_day(_utc_day(ts)))
        self.assertEqual(len(rs), 4)
        self.assertEqual(rs[0].id, receipts[0].id)
        self.assertEqual(verify_chain(rs), {"ok": True, "count": 4})

    def test_root_matches_replay(self):
        ts = 1_700_000_000.0
        for i in range(3):
            _run(self.store.append("e", "x", None, {"i": i}, ts=ts + i))
        rs = _run(self.store.replay_chain_for_day(_utc_day(ts)))
        root = compute_root([r.hash for r in rs])
        self.assertEqual(len(root), 64)


class TestMerkleRow(_IsolatedStoreCase):
    def test_upsert_and_read(self):
        out = _run(
            self.store.upsert_merkle_root(
                day_iso="2026-05-09", root_hex="ab" * 32, leaf_count=42
            )
        )
        self.assertEqual(out.day_iso, "2026-05-09")
        self.assertEqual(out.leaf_count, 42)
        self.assertIsNone(out.anchored_at)
        # Read back.
        row = _run(self.store.get_merkle_root("2026-05-09"))
        assert row is not None
        self.assertEqual(row.root_hex, "ab" * 32)


if __name__ == "__main__":
    unittest.main()
