"""Pin the desktop sidecar event contract (Phase L9 A1).

Tauri emits exactly three lifecycle events around the FastAPI sidecar:
``desktop.sidecar.started``, ``desktop.sidecar.failed``,
``desktop.sidecar.exited``.

The shape is mirrored on the Rust side
(``desktop/src-tauri/src/sidecar.rs``) and the cockpit listener; the
JSON schema lives at ``desktop/src-tauri/sidecar-events.schema.json``
and is the single source of truth.

This test ensures:

1. The schema declares exactly those three events.
2. Each declared event has a matching ``app.emit("desktop.sidecar.<id>", …)``
   call in the Rust source.
3. Required JSON keys for each event appear at least once in the
   serde_json::json! literal that builds its payload.

We do **not** parse Rust into AST — a coarse string match is enough to
catch silent contract drift; a real Rust toolchain run on CI does the
strict shape check.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "desktop" / "src-tauri" / "sidecar-events.schema.json"
SIDECAR_RS = REPO / "desktop" / "src-tauri" / "src" / "sidecar.rs"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA.read_text())


@pytest.fixture(scope="module")
def rust_source() -> str:
    return SIDECAR_RS.read_text()


def test_schema_lists_exactly_three_events(schema: dict) -> None:
    assert set(schema["events"]) == {
        "desktop.sidecar.started",
        "desktop.sidecar.failed",
        "desktop.sidecar.exited",
    }
    assert schema["version"] == "1.0.0"


def test_each_event_is_emitted_from_rust(schema: dict, rust_source: str) -> None:
    for event_name in schema["events"]:
        needle = f'"{event_name}"'
        assert needle in rust_source, (
            f"event {event_name!r} declared in schema but not emitted from "
            f"sidecar.rs (looked for literal {needle})"
        )


def test_required_payload_keys_present_in_rust(schema: dict, rust_source: str) -> None:
    """Each schema-required key must appear as a json! key for that event.

    We slice the rust source between the emit() call and the next emit
    call so payload keys for one event don't bleed into another. This
    is approximate but tight enough to flag missing fields.
    """

    for event_name, spec in schema["events"].items():
        needle = f'"{event_name}"'
        idx = rust_source.find(needle)
        assert idx != -1, f"missing emit for {event_name}"

        # Search backwards for the json!{ literal that immediately
        # precedes this emit call within ~600 chars.
        window_start = max(0, idx - 600)
        window = rust_source[window_start:idx + len(needle)]
        json_block = re.search(r"json!\((.*?)\);?", window, re.DOTALL)
        if json_block is None:
            json_block = re.search(r'json!\((.*?)\)\s*;?\s*$', window, re.DOTALL)
        assert json_block is not None, (
            f"could not locate json!() literal for {event_name} near offset {idx}"
        )
        block = json_block.group(1)
        for key in spec["required"]:
            assert f'"{key}"' in block, (
                f"required key {key!r} missing in json! literal for "
                f"{event_name}; got block: {block!r}"
            )


def test_schema_declares_no_unknown_top_level_fields(schema: dict) -> None:
    expected = {"$schema", "$id", "title", "description", "version", "events"}
    assert set(schema) == expected
