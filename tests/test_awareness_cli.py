"""Contract tests for the awareness CLI (`backend.core.domains.awareness_cli`).

The CLI mirrors the HTTP surface in
``web_extras/routers/domains.py`` (``GET /api/domains``,
``GET /api/domains/{slug}/awareness``,
``GET /api/domains/{slug}/awareness/{source_id}/snapshot``) so an
operator can shell into the same code path the cockpit uses,
without spinning the FastAPI app.

What we pin here:

1. **List subcommand** — both no-slug (catalogue every pack) and
   one-slug (filter to one pack) shapes.
2. **Snapshot subcommand** — happy path for a fetcher-backed
   source, ``fetcher_unavailable`` for config-only sources,
   404 envelopes for unknown slug / source.
3. **Snapshot-all subcommand** — fetched + skipped split, overall
   ``ok`` only when every fetched source returned ``ok=true``.
4. **Argparse plumbing** — required positionals enforce
   ``SystemExit(2)`` (cron-friendly), ``--quiet`` produces
   single-line JSON, exit codes follow the standard 0-on-ok
   convention.

We use the ``backend.core.domains`` registry directly (not a
mock) so the test catches real drift in pack manifests.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

import backend.core.domains.packs  # noqa: F401  (registers built-in packs)
from backend.core.domains import base as _base
from backend.core.domains.awareness_cli import _build_arg_parser, _run, main
from backend.core.domains.registry import register, _REGISTRY  # type: ignore


# ---------------------------------------------------------------------------
# Test helpers — register an isolated probe pack for predictable results
# ---------------------------------------------------------------------------


@pytest.fixture
def probe_pack():
    """Register a fully-controlled probe pack for the duration of one
    test; tear it down afterwards.

    The probe has three awareness sources covering every fetcher
    branch the CLI cares about: a working fetcher, a fetcher that
    raises, and a config-only source (no fetcher).
    """

    class _ProbeAwarenessPack(_base.DomainPack):
        manifest = _base.DomainManifest(
            slug="awcli_probe",
            name="Awareness CLI Probe",
            short="probe pack",
            description="Probe pack for awareness CLI tests.",
            color="#000000",
            capabilities=("probe",),
            audience="test",
        )

        def actions(self):
            return ()

        def awareness(self):
            async def _ok_fetcher(_cfg):
                return {"ok": True, "items": [{"x": 1}, {"x": 2}]}

            async def _boom_fetcher(_cfg):
                raise RuntimeError("synthetic fetcher failure")

            return (
                _base.AwarenessSource(
                    id="ok_source",
                    name="OK source",
                    description="Always returns 2 items.",
                    kind="poll",
                    config={"hint": "fixture"},
                    fetcher=_ok_fetcher,
                ),
                _base.AwarenessSource(
                    id="boom_source",
                    name="Boom source",
                    description="Always raises.",
                    kind="poll",
                    config={},
                    fetcher=_boom_fetcher,
                ),
                _base.AwarenessSource(
                    id="webhook_source",
                    name="Webhook receiver",
                    description="No fetcher (config-only).",
                    kind="webhook",
                    config={},
                    fetcher=None,
                ),
            )

        def system_prompt(self) -> str:
            return "probe"

    pack = _ProbeAwarenessPack()
    register(pack)
    yield pack
    # Tear down: drop the probe so it doesn't leak into other tests.
    _REGISTRY.pop("awcli_probe", None)


def _new_args(**overrides):
    parser = _build_arg_parser()
    # Argparse requires a subcommand; use ``list`` (no slug) by default.
    args = parser.parse_args(["list"])
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _capture_json(capsys: pytest.CaptureFixture, rc: int) -> dict[str, Any]:
    """Read stdout, parse JSON envelope, sanity-check rc."""

    out = capsys.readouterr().out
    payload = json.loads(out)
    if payload.get("ok"):
        assert rc == 0
    else:
        assert rc == 1
    return payload


# ---------------------------------------------------------------------------
# `list` subcommand
# ---------------------------------------------------------------------------


def test_list_without_slug_returns_every_pack(
    probe_pack, capsys: pytest.CaptureFixture
):
    args = _new_args(slug=None)
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    slugs = {p["slug"] for p in payload["packs"]}
    assert "awcli_probe" in slugs, (
        "the probe pack must show up in the catalogue listing"
    )
    # Every pack row has the expected keys.
    for row in payload["packs"]:
        assert {"slug", "name", "count", "live_count", "awareness"} <= set(
            row.keys()
        )


def test_list_with_slug_returns_one_packs_sources(
    probe_pack, capsys: pytest.CaptureFixture
):
    args = _new_args(slug="awcli_probe")
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["slug"] == "awcli_probe"
    assert payload["count"] == 3, "probe pack has 3 awareness sources"
    assert payload["live_count"] == 2, (
        "two have fetchers; the webhook source is config-only"
    )
    ids = {s["id"] for s in payload["awareness"]}
    assert ids == {"ok_source", "boom_source", "webhook_source"}
    # `live` flag is correctly set per source.
    by_id = {s["id"]: s for s in payload["awareness"]}
    assert by_id["ok_source"]["live"] is True
    assert by_id["webhook_source"]["live"] is False


def test_list_with_unknown_slug_returns_error_envelope(
    capsys: pytest.CaptureFixture,
):
    args = _new_args(slug="totally_not_a_pack")
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "domain_not_found"
    assert payload["slug"] == "totally_not_a_pack"


# ---------------------------------------------------------------------------
# `snapshot` subcommand
# ---------------------------------------------------------------------------


def test_snapshot_happy_path_returns_ok_with_data(
    probe_pack, capsys: pytest.CaptureFixture
):
    parser = _build_arg_parser()
    args = parser.parse_args(["snapshot", "awcli_probe", "ok_source"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is True
    assert payload["slug"] == "awcli_probe"
    assert payload["source_id"] == "ok_source"
    assert payload["data"] == {"ok": True, "items": [{"x": 1}, {"x": 2}]}
    # Per-snapshot trace_id is allocated by the meeet trace_scope.
    assert payload["trace_id"], "snapshot must mint a trace_id"
    assert isinstance(payload["took_ms"], (int, float))


def test_snapshot_fetcher_failure_returns_error_envelope(
    probe_pack, capsys: pytest.CaptureFixture
):
    parser = _build_arg_parser()
    args = parser.parse_args(["snapshot", "awcli_probe", "boom_source"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["slug"] == "awcli_probe"
    assert payload["source_id"] == "boom_source"
    assert payload["error"] == "synthetic fetcher failure"
    # We still surface the trace_id so the operator can grep
    # the meeet store for the matching `awareness.snapshot.failed`.
    assert payload["trace_id"]


def test_snapshot_config_only_source_returns_fetcher_unavailable(
    probe_pack, capsys: pytest.CaptureFixture
):
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["snapshot", "awcli_probe", "webhook_source"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["error"] == "fetcher_unavailable"
    assert payload["kind"] == "webhook"
    assert "hint" in payload, (
        "the operator should see a human hint explaining why "
        "no snapshot is available"
    )


def test_snapshot_unknown_slug_returns_404_envelope(
    capsys: pytest.CaptureFixture,
):
    parser = _build_arg_parser()
    args = parser.parse_args(["snapshot", "no_such_pack", "any_source"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "domain_not_found"


def test_snapshot_unknown_source_returns_404_envelope(
    probe_pack, capsys: pytest.CaptureFixture
):
    parser = _build_arg_parser()
    args = parser.parse_args(
        ["snapshot", "awcli_probe", "no_such_source"]
    )
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "awareness_not_found"
    assert payload["source_id"] == "no_such_source"


# ---------------------------------------------------------------------------
# `snapshot-all` subcommand
# ---------------------------------------------------------------------------


def test_snapshot_all_splits_fetched_and_skipped(
    probe_pack, capsys: pytest.CaptureFixture
):
    """All-snapshot run on the probe pack:

    - ``ok_source`` ⇒ fetched, ok=true.
    - ``boom_source`` ⇒ fetched, ok=false.
    - ``webhook_source`` ⇒ skipped (no fetcher).

    Overall ``ok`` is false because boom_source failed.
    """

    parser = _build_arg_parser()
    args = parser.parse_args(["snapshot-all", "awcli_probe"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False, (
        "any failed fetched source must flip overall ok to false"
    )
    assert payload["fetched_count"] == 2
    assert payload["skipped_count"] == 1
    fetched_ids = {f["source_id"] for f in payload["fetched"]}
    assert fetched_ids == {"ok_source", "boom_source"}
    assert payload["skipped"][0]["source_id"] == "webhook_source"
    assert payload["skipped"][0]["reason"] == "fetcher_unavailable"


def test_snapshot_all_returns_overall_ok_when_every_fetcher_succeeds(
    capsys: pytest.CaptureFixture,
):
    """Variant of the probe pack that has only ok_source — overall
    envelope ``ok`` should be true."""

    class _AllOkPack(_base.DomainPack):
        manifest = _base.DomainManifest(
            slug="awcli_allok",
            name="All OK",
            short="all-ok",
            description="every source ok",
            color="#fff",
            capabilities=(),
            audience="test",
        )

        def actions(self):
            return ()

        def awareness(self):
            async def _ok(_):
                return {"ok": True}

            return (
                _base.AwarenessSource(
                    id="a",
                    name="A",
                    description="",
                    kind="poll",
                    config={},
                    fetcher=_ok,
                ),
                _base.AwarenessSource(
                    id="b",
                    name="B",
                    description="",
                    kind="poll",
                    config={},
                    fetcher=_ok,
                ),
            )

        def system_prompt(self) -> str:
            return ""

    register(_AllOkPack())
    try:
        parser = _build_arg_parser()
        args = parser.parse_args(["snapshot-all", "awcli_allok"])
        rc = asyncio.run(_run(args))
        payload = _capture_json(capsys, rc)
        assert payload["ok"] is True
        assert payload["fetched_count"] == 2
        assert payload["skipped_count"] == 0
    finally:
        _REGISTRY.pop("awcli_allok", None)


def test_snapshot_all_unknown_slug_returns_404_envelope(
    capsys: pytest.CaptureFixture,
):
    parser = _build_arg_parser()
    args = parser.parse_args(["snapshot-all", "no_such_pack"])
    rc = asyncio.run(_run(args))
    payload = _capture_json(capsys, rc)
    assert payload["ok"] is False
    assert payload["reason"] == "domain_not_found"


# ---------------------------------------------------------------------------
# Argparse plumbing
# ---------------------------------------------------------------------------


def test_subcommand_required_else_systemexit():
    """Argparse should reject invocation without a subcommand. cron
    scripts running ``set -e`` rely on the SystemExit so a typo
    halts the pipeline instead of silently succeeding.
    """

    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([])
    assert exc_info.value.code == 2


def test_snapshot_requires_both_positionals():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["snapshot", "only_one_arg"])
    assert exc_info.value.code == 2


def test_snapshot_all_requires_slug():
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["snapshot-all"])
    assert exc_info.value.code == 2


def test_quiet_flag_emits_compact_json(
    probe_pack, capsys: pytest.CaptureFixture
):
    """``--quiet`` is the global pre-subcommand option; it must
    produce single-line JSON for shell-friendly piping into ``jq``.
    """

    parser = _build_arg_parser()
    args = parser.parse_args(["--quiet", "list", "awcli_probe"])
    rc = asyncio.run(_run(args))
    out = capsys.readouterr().out
    # Single-line JSON ends with one trailing newline → exactly one
    # newline char total.
    assert out.count("\n") == 1, (
        "--quiet must produce one-line JSON for jq piping"
    )
    assert rc == 0


def test_main_entrypoint_dispatches_to_run(
    probe_pack, capsys: pytest.CaptureFixture
):
    """End-to-end smoke through ``main([...])`` so the
    ``asyncio.run`` glue is exercised once (the rest of the suite
    drives ``_run`` directly to keep tests fast).
    """

    rc = main(["--quiet", "list", "awcli_probe"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["slug"] == "awcli_probe"
