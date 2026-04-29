"""Validate that the JSON Schema in docs/contracts/ matches the runtime manifest.

If this test fails, either the loader (`backend/core/product/manifest.py`)
or the schema (`docs/contracts/download_manifest.schema.json`) drifted.
Pick the one that's correct, update the other, and bump the contract
version if it's a breaking change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from backend.core.product import DEFAULT_MANIFEST


SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "contracts"
    / "download_manifest.schema.json"
)


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"missing schema at {SCHEMA_PATH}"


def test_default_manifest_validates_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load_schema()
    payload = DEFAULT_MANIFEST.to_dict()
    payload.setdefault("ok", True)
    jsonschema.validate(payload, schema)


def test_loaded_manifest_validates_against_schema(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    from backend.core.product import load_manifest
    from backend.core.product.manifest import ENV_RELEASES_PATH

    p = tmp_path / "releases.json"
    p.write_text(
        json.dumps(
            {
                "product": "tars",
                "contract_version": "1.0.0",
                "channel": "stable",
                "released_at": "2026-05-01T00:00:00Z",
                "releases": [
                    {
                        "version": "1.0.0",
                        "channel": "stable",
                        "released_at": "2026-05-01T00:00:00Z",
                        "notes": "first stable",
                        "artifacts": [
                            {
                                "os": "macos",
                                "arch": "arm64",
                                "kind": "dmg",
                                "filename": "TARS-1.0.0-arm64.dmg",
                                "size_bytes": 92321312,
                                "sha256": "a" * 64,
                                "url": "https://meeet.world/downloads/tars/1.0.0/TARS-1.0.0-arm64.dmg",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_RELEASES_PATH, str(p))
    out = load_manifest()
    payload = {"ok": True, **out.to_dict()}
    jsonschema.validate(payload, _load_schema())


def test_schema_rejects_unknown_os_in_artifact() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load_schema()
    bad = DEFAULT_MANIFEST.to_dict()
    bad["releases"][0]["artifacts"][0]["os"] = "symbian"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
