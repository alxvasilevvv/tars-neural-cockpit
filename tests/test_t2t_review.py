"""W260 -- T2T code-review handoff tests.

Each test is hermetic: temp SQLite for the t2t_reviews DB, temp
SQLite for the composer DB, temp NDJSON dir for receipts, and a
fresh host-key.json so envelopes get signed by a per-test key. We
exercise the inbox/outbox stores + protocol envelope directly, and
also drive the full router through a FastAPI ``TestClient`` so the
"approve -> auto-apply" hand-off is covered end-to-end.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.composer import reset_store as reset_composer_store
from backend.core.composer.storage import get_store as get_composer_store
from backend.core.composer.types import ComposerPlan, EditOp
from backend.core.receipts.store import reset_store as reset_receipt_store
from backend.core.t2t_review.protocol import (
    REQUEST_TYPE,
    RESPONSE_TYPE,
    ReviewRequest,
    canonical_bytes,
    new_review_id,
    sign_envelope,
    tars_id_from_pubkey,
    verify_envelope,
)
from backend.core.t2t_review.inbox import get_inbox, reset_inbox
from backend.core.t2t_review.outbox import get_outbox, reset_outbox


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    home = tmp_path / "tars-home"
    home.mkdir()
    monkeypatch.setenv("TARS_HOME", str(home))
    monkeypatch.setenv("TARS_COMPOSER_DB", str(home / "composer.sqlite"))
    monkeypatch.setenv("TARS_COMPOSER_BACKUP_DIR", str(home / "backups"))
    monkeypatch.setenv("TARS_T2T_REVIEW_DB_PATH", str(home / "t2t_reviews.sqlite"))
    monkeypatch.setenv("TARS_RECEIPT_HOST_KEY_PATH", str(home / "host-key.json"))
    monkeypatch.setenv("TARS_RECEIPT_DIR", str(home / "receipts"))
    monkeypatch.setenv("TARS_RECEIPT_DB_PATH", str(home / "receipts.sqlite"))
    # Belt-and-braces -- ensure nothing inherits a "disabled" flag from CI.
    monkeypatch.delenv("TARS_T2T_REVIEW_DB", raising=False)
    monkeypatch.delenv("TARS_COMPOSER_STORE", raising=False)
    monkeypatch.delenv("TARS_RECEIPT_STORE", raising=False)
    monkeypatch.delenv("TARS_T2T_DEFAULT_PEER", raising=False)

    reset_composer_store()
    reset_inbox()
    reset_outbox()
    reset_receipt_store()
    yield
    reset_composer_store()
    reset_inbox()
    reset_outbox()
    reset_receipt_store()


@pytest.fixture
def project(tmp_path):
    """A minimal repo we can mutate via the composer executor."""

    root = tmp_path / "proj"
    root.mkdir()
    (root / "models.py").write_text(
        "class Customer:\n    pass\n", encoding="utf-8"
    )
    return root


def _make_plan(project_root: Path, plan_id: str = "cmp_test01") -> ComposerPlan:
    """Build a minimal composer plan + persist it through the real store."""

    op = EditOp(
        op="modify",
        path="models.py",
        old_content="class Customer:\n    pass\n",
        new_content="class Account:\n    pass\n",
        diff_unified=(
            "--- models.py\n+++ models.py\n"
            "@@ -1,1 +1,1 @@\n-class Customer:\n+class Account:\n"
        ),
    )
    plan = ComposerPlan(
        plan_id=plan_id,
        transcript="rename Customer to Account",
        intent_summary="rename across project",
        ops=[op],
        project_root=str(project_root),
    )
    store = get_composer_store()
    assert store is not None
    store.save_plan(plan)
    return plan


def _make_app() -> FastAPI:
    """Build a tiny FastAPI app with only the t2t_review router on it.

    Keeps the test surface small so an unrelated router import error
    in ``web_extras.app`` doesn't blow up these tests.
    """

    from web_extras.routers import t2t_review as t2t_review_router

    app = FastAPI()
    app.include_router(t2t_review_router.router)
    return app


# ---------------------------------------------------------------------------
# 1 -- send creates outbox row + signed envelope
# ---------------------------------------------------------------------------


def test_send_creates_outbox_row(project):
    plan = _make_plan(project)
    app = _make_app()
    client = TestClient(app)

    r = client.post(
        "/api/t2t/review/send",
        json={
            "plan_id": plan.plan_id,
            "recipient_tars_id": "peer123",
            "comment": "please review",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["review_id"].startswith("rev_")
    env = data["envelope"]
    # Signed envelope should verify against its embedded pubkey.
    assert env["type"] == REQUEST_TYPE
    assert verify_envelope(env) is True
    # No peer URL was configured -> stays pending, not delivered.
    assert data["delivered"] is False
    assert data["state"] == "pending"

    # Outbox row exists and references the plan.
    outbox = get_outbox()
    assert outbox is not None
    row = outbox.get_outbox(data["review_id"])
    assert row is not None
    assert row["plan_id"] == plan.plan_id
    assert row["recipient_tars_id"] == "peer123"
    assert row["state"] == "pending"
    assert row["comment"] == "please review"


# ---------------------------------------------------------------------------
# 2 -- receive stores inbox row + verifies envelope
# ---------------------------------------------------------------------------


def test_receive_stores_inbox(project):
    plan = _make_plan(project, plan_id="cmp_rcv01")
    app = _make_app()
    client = TestClient(app)

    # Build a signed envelope by hand using a fresh test key so we
    # don't need a second TARS instance.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    import base64

    sk = Ed25519PrivateKey.generate()
    priv_seed = sk.private_bytes_raw()
    pub_b64 = base64.b64encode(sk.public_key().public_bytes_raw()).decode("ascii")
    sender_id = tars_id_from_pubkey(pub_b64)

    review_id = new_review_id()
    req = ReviewRequest(
        review_id=review_id,
        sender_tars_id=sender_id,
        recipient_tars_id="self",
        plan=plan.to_dict(),
        comment="lgtm?",
    )
    envelope = sign_envelope(
        envelope_type=REQUEST_TYPE,
        body=req.to_dict(),
        sender_tars_id=sender_id,
        sender_priv_seed=priv_seed,
    )

    r = client.post("/api/t2t/review/receive", json={"envelope": envelope})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["review_id"] == review_id

    # Inbox row exists in pending state.
    inbox = get_inbox()
    assert inbox is not None
    rows = inbox.list_inbox(state="pending")
    assert any(row["review_id"] == review_id for row in rows)

    # GET /inbox surfaces it.
    r2 = client.get("/api/t2t/review/inbox")
    items = r2.json()["items"]
    assert any(item["review_id"] == review_id for item in items)


def test_receive_rejects_bad_signature(project):
    """A tampered envelope must be refused with a 400."""

    plan = _make_plan(project, plan_id="cmp_bad01")
    app = _make_app()
    client = TestClient(app)

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    sk = Ed25519PrivateKey.generate()
    priv_seed = sk.private_bytes_raw()
    review_id = new_review_id()
    req = ReviewRequest(
        review_id=review_id,
        sender_tars_id="bogus",
        recipient_tars_id="self",
        plan=plan.to_dict(),
    )
    envelope = sign_envelope(
        envelope_type=REQUEST_TYPE,
        body=req.to_dict(),
        sender_tars_id="bogus",
        sender_priv_seed=priv_seed,
    )
    # Tamper with the body after signing.
    envelope["body"]["comment"] = "injected"

    r = client.post("/api/t2t/review/receive", json={"envelope": envelope})
    assert r.status_code == 400
    assert "signature" in r.text.lower()


# ---------------------------------------------------------------------------
# 3 -- approve returns a signed receipt envelope
# ---------------------------------------------------------------------------


def test_approve_returns_signed_response(project):
    plan = _make_plan(project, plan_id="cmp_apr01")
    app = _make_app()
    client = TestClient(app)

    # 1) Send our own plan into our own inbox via /receive so the
    #    test runs single-process.
    sent = client.post(
        "/api/t2t/review/send",
        json={"plan_id": plan.plan_id, "recipient_tars_id": "self"},
    ).json()
    envelope = sent["envelope"]
    review_id = sent["review_id"]

    r = client.post("/api/t2t/review/receive", json={"envelope": envelope})
    assert r.status_code == 200, r.text

    # 2) Approve from the recipient side.
    r2 = client.post(
        f"/api/t2t/review/{review_id}/approve",
        json={"comment": "looks clean"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["ok"] is True
    assert body["decision"] == "approve"
    resp_env = body["envelope"]
    assert resp_env["type"] == RESPONSE_TYPE
    assert verify_envelope(resp_env) is True
    assert resp_env["body"]["decision"] == "approve"
    assert resp_env["body"]["review_id"] == review_id

    # Inbox row transitions to approved.
    inbox = get_inbox()
    row = inbox.get_inbox(review_id)
    assert row is not None
    assert row["state"] == "approved"
    assert row["reviewer_comment"] == "looks clean"


# ---------------------------------------------------------------------------
# 4 -- reject preserves the reason on both sides
# ---------------------------------------------------------------------------


def test_reject_preserves_reason(project):
    plan = _make_plan(project, plan_id="cmp_rej01")
    app = _make_app()
    client = TestClient(app)

    sent = client.post(
        "/api/t2t/review/send",
        json={"plan_id": plan.plan_id, "recipient_tars_id": "self"},
    ).json()
    client.post("/api/t2t/review/receive", json={"envelope": sent["envelope"]})

    # Reject requires a reason.
    r_missing = client.post(
        f"/api/t2t/review/{sent['review_id']}/reject", json={}
    )
    assert r_missing.status_code == 400

    r = client.post(
        f"/api/t2t/review/{sent['review_id']}/reject",
        json={"reason": "uses forbidden API"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "reject"
    resp_env = body["envelope"]
    assert verify_envelope(resp_env) is True
    assert resp_env["body"]["reason"] == "uses forbidden API"

    inbox = get_inbox()
    row = inbox.get_inbox(sent["review_id"])
    assert row["state"] == "rejected"
    # Signed response envelope is persisted so we can re-verify later.
    assert row["response_envelope"] is not None
    assert row["response_envelope"]["body"]["reason"] == "uses forbidden API"


# ---------------------------------------------------------------------------
# 5 -- approval auto-applies the plan locally on the sender's side
# ---------------------------------------------------------------------------


def test_apply_on_approval(project):
    plan = _make_plan(project, plan_id="cmp_app01")
    app = _make_app()
    client = TestClient(app)

    # Send + receive in-process.
    sent = client.post(
        "/api/t2t/review/send",
        json={"plan_id": plan.plan_id, "recipient_tars_id": "self"},
    ).json()
    review_id = sent["review_id"]
    client.post("/api/t2t/review/receive", json={"envelope": sent["envelope"]})

    # Approve -> signed response envelope.
    approve = client.post(
        f"/api/t2t/review/{review_id}/approve", json={}
    ).json()
    response_env = approve["envelope"]

    # Pipe the signed response back into the sender callback.
    r = client.post(
        "/api/t2t/review/response", json={"envelope": response_env}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["decision"] == "approve"
    apply_result = data["apply_result"]
    assert apply_result is not None
    assert apply_result["ok"] is True

    # File on disk should now reflect the modification.
    new_content = (project / "models.py").read_text(encoding="utf-8")
    assert "class Account" in new_content
    assert "class Customer" not in new_content

    # Outbox transitions to "applied".
    outbox = get_outbox()
    row = outbox.get_outbox(review_id)
    assert row is not None
    assert row["state"] == "applied"
    assert row["response"] is not None
    assert row["response"]["decision"] == "approve"
