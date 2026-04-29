"""Tests for ``python -m backend.core.product.publish``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.product import load_manifest
from backend.core.product.manifest import ENV_DOWNLOAD_BASE, ENV_RELEASES_PATH
from backend.core.product.publish import (
    build_manifest,
    collect_artifacts,
    main as publish_main,
)


def _make_fake_artifact(path: Path, *, size: int = 1024) -> None:
    path.write_bytes(b"x" * size)


# ---------------------------------------------------------------------
# Sniffers
# ---------------------------------------------------------------------


def test_collect_recognises_dmg_and_exe(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg", size=2048)
    _make_fake_artifact(src / "TARS-1.0.0-x64.dmg", size=4096)
    _make_fake_artifact(src / "TARS_1.0.0_x64-setup.exe", size=8192)
    _make_fake_artifact(src / "ignore-me.txt", size=10)

    arts = collect_artifacts(src, version="1.0.0", base_url=None)
    assert len(arts) == 3

    by_os = {a.os: a for a in arts}
    assert "macos" in by_os and "windows" in by_os

    arm = next(a for a in arts if a.filename.endswith("arm64.dmg"))
    assert arm.arch == "arm64"
    assert arm.kind == "dmg"
    assert arm.size_bytes == 2048
    assert len(arm.sha256) == 64

    win = next(a for a in arts if a.filename.endswith("setup.exe"))
    assert win.os == "windows"
    assert win.arch == "x64"
    assert win.kind == "exe"

    # urls become relative when no base
    assert all(a.url.startswith("/releases/1.0.0/") for a in arts)


def test_collect_uses_base_url(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg")
    arts = collect_artifacts(
        src,
        version="1.0.0",
        base_url="https://meeet.world/downloads/tars",
    )
    assert arts[0].url == (
        "https://meeet.world/downloads/tars/1.0.0/TARS-1.0.0-arm64.dmg"
    )


def test_collect_skips_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        collect_artifacts(tmp_path / "nope", version="1.0.0")


# ---------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------


def test_build_manifest_replaces_same_version(tmp_path: Path) -> None:
    out = tmp_path / "releases.json"

    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg", size=1024)
    arts1 = collect_artifacts(src, version="1.0.0", base_url=None)
    m1 = build_manifest(arts1, version="1.0.0", channel="stable", notes="first", out_path=out)
    out.write_text(json.dumps(m1), encoding="utf-8")

    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg", size=2048)  # different bytes
    arts2 = collect_artifacts(src, version="1.0.0", base_url=None)
    m2 = build_manifest(arts2, version="1.0.0", channel="stable", notes="re-pub", out_path=out)

    assert len(m2["releases"]) == 1
    assert m2["releases"][0]["notes"] == "re-pub"
    assert m2["releases"][0]["artifacts"][0]["size_bytes"] == 2048


def test_build_manifest_keeps_other_versions(tmp_path: Path) -> None:
    out = tmp_path / "releases.json"
    out.write_text(
        json.dumps(
            {
                "product": "tars",
                "contract_version": "1.0.0",
                "channel": "stable",
                "released_at": "2026-04-01T00:00:00Z",
                "releases": [
                    {
                        "version": "0.9.0",
                        "channel": "stable",
                        "released_at": "2026-04-01T00:00:00Z",
                        "artifacts": [
                            {
                                "os": "macos",
                                "arch": "arm64",
                                "kind": "dmg",
                                "filename": "TARS-0.9.0-arm64.dmg",
                                "url": "/x.dmg",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg")
    arts = collect_artifacts(src, version="1.0.0", base_url=None)
    m = build_manifest(arts, version="1.0.0", channel="stable", notes=None, out_path=out)

    versions = [r["version"] for r in m["releases"]]
    assert versions == ["1.0.0", "0.9.0"]


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def test_cli_writes_manifest_and_loader_picks_it_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg", size=2048)
    _make_fake_artifact(src / "TARS_1.0.0_x64-setup.exe", size=4096)

    out = tmp_path / "out" / "releases.json"
    monkeypatch.setenv(ENV_RELEASES_PATH, str(out))
    monkeypatch.setenv(ENV_DOWNLOAD_BASE, "https://meeet.world/downloads/tars")

    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--channel",
            "stable",
            "--notes",
            "first stable",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()

    loaded = load_manifest()
    assert loaded.source.startswith("file:")
    assert len(loaded.releases) == 1
    rel = loaded.releases[0]
    assert rel.version == "1.0.0"
    assert rel.notes == "first stable"
    osses = {a.os for a in rel.artifacts}
    assert {"macos", "windows"}.issubset(osses)
    arm = next(a for a in rel.artifacts if a.filename.endswith("arm64.dmg"))
    assert arm.url.startswith("https://meeet.world/downloads/tars/")
    assert arm.sha256 and len(arm.sha256) == 64


def test_cli_dry_run_prints_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg")
    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--out",
            str(tmp_path / "ignored.json"),
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["releases"][0]["version"] == "1.0.0"
    assert not (tmp_path / "ignored.json").exists()


def test_cli_returns_1_when_no_artifacts(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    (src / "readme.txt").write_text("nothing to publish", encoding="utf-8")
    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--out",
            str(tmp_path / "out.json"),
        ]
    )
    assert rc == 1


def test_cli_copy_to_mirrors_artifacts(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    _make_fake_artifact(src / "TARS-1.0.0-arm64.dmg", size=512)

    staging = tmp_path / "staging"
    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--out",
            str(tmp_path / "out.json"),
            "--copy-to",
            str(staging),
        ]
    )
    assert rc == 0
    assert (staging / "TARS-1.0.0-arm64.dmg").exists()
    assert (staging / "TARS-1.0.0-arm64.dmg").stat().st_size == 512
