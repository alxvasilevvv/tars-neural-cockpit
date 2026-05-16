"""Public download manifest — loader + HTTP surface tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.product import (
    DEFAULT_MANIFEST,
    load_manifest,
    resolve_url,
)
from backend.core.product.manifest import (
    CONTRACT_VERSION,
    ENV_DOWNLOAD_BASE,
    ENV_RELEASES_PATH,
)
from backend.core.domains import packs as _packs  # noqa: F401  (registers)
from web_extras.app import app


# ----------------------------------------------------------------------
# Loader
# ----------------------------------------------------------------------


def test_default_manifest_has_contract_and_artifacts() -> None:
    assert DEFAULT_MANIFEST.contract_version == CONTRACT_VERSION
    assert DEFAULT_MANIFEST.product == "tars"
    assert DEFAULT_MANIFEST.releases, "default manifest has no releases"
    arts = DEFAULT_MANIFEST.releases[0].artifacts
    os_set = {a.os for a in arts}
    # macOS is the launch target; Windows/Linux re-enter the default
    # manifest once pyoxidizer cross-compilation lands (see notes in
    # backend/core/product/manifest.py::_DEFAULT_NOTES).
    assert "macos" in os_set
    for art in arts:
        assert art.url.startswith("http")
        assert art.filename


def test_load_returns_defaults_when_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_RELEASES_PATH, str(tmp_path / "missing.json"))
    out = load_manifest()
    assert out.source == "defaults"
    assert out.releases[0].version


def test_load_returns_defaults_when_file_malformed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "broken.json"
    p.write_text("not-json{", encoding="utf-8")
    monkeypatch.setenv(ENV_RELEASES_PATH, str(p))
    out = load_manifest()
    assert out.source == "defaults"


def test_load_parses_real_manifest_with_relative_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
                                "size_bytes": 65000000,
                                "sha256": "deadbeef" * 8,
                                "url": "/releases/1.0.0/TARS-1.0.0-arm64.dmg",
                            },
                            {
                                "os": "windows",
                                "arch": "x64",
                                "kind": "exe",
                                "filename": "TARS-1.0.0-Setup.exe",
                                "url": "/releases/1.0.0/TARS-1.0.0-Setup.exe",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_RELEASES_PATH, str(p))
    monkeypatch.setenv(ENV_DOWNLOAD_BASE, "https://meeet.world/downloads/tars")

    out = load_manifest()
    assert out.source.startswith("file:")
    assert len(out.releases) == 1
    rel = out.releases[0]
    assert rel.version == "1.0.0"
    arts = {a.os: a for a in rel.artifacts}
    assert arts["macos"].url.startswith("https://meeet.world/downloads/tars/")
    assert arts["macos"].sha256 == "deadbeef" * 8
    assert arts["windows"].url.endswith("Setup.exe")


def test_load_skips_invalid_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
                        "version": "0.9.0",
                        "channel": "stable",
                        "released_at": "2026-05-01T00:00:00Z",
                        "artifacts": [
                            {"os": "weirdos", "arch": "arm64", "kind": "dmg",
                             "filename": "x.dmg", "url": "https://x/x.dmg"},
                            {"os": "macos", "arch": "arm64", "kind": "dmg",
                             "filename": "ok.dmg", "url": "https://x/ok.dmg"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_RELEASES_PATH, str(p))
    out = load_manifest()
    assert len(out.releases) == 1
    assert {a.os for a in out.releases[0].artifacts} == {"macos"}


def test_resolve_url_handles_absolute_relative_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DOWNLOAD_BASE, "https://x.example/downloads")
    assert resolve_url("https://elsewhere/path") == "https://elsewhere/path"
    assert resolve_url("/releases/1/x.dmg") == "https://x.example/downloads/releases/1/x.dmg"
    assert resolve_url(None) is None
    assert resolve_url("") is None
    monkeypatch.delenv(ENV_DOWNLOAD_BASE)
    assert resolve_url("/x") == "/x"  # base unset → return as-is


# ----------------------------------------------------------------------
# HTTP surface
# ----------------------------------------------------------------------


def test_get_downloads_returns_default_when_no_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_RELEASES_PATH, "/nonexistent/.tars/releases.json")
    client = TestClient(app)
    res = client.get("/api/product/downloads")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["product"] == "tars"
    assert body["contract_version"] == CONTRACT_VERSION
    assert body["releases"]
    assert res.headers.get("X-Tars-Contract") == CONTRACT_VERSION
    assert "max-age" in (res.headers.get("Cache-Control") or "")


def test_get_latest_with_os_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_RELEASES_PATH, str(tmp_path / "missing.json"))
    client = TestClient(app)
    res = client.get("/api/product/downloads/latest?os=macos")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["release"]["artifacts"]
    osses = {a["os"] for a in body["release"]["artifacts"]}
    assert "macos" in osses


def test_get_latest_rejects_invalid_os() -> None:
    client = TestClient(app)
    res = client.get("/api/product/downloads/latest?os=symbian")
    assert res.status_code == 400


def test_get_version_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/api/product/version")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["product"] == "tars"
    assert body["contract_version"] == CONTRACT_VERSION
    assert body["version"]
