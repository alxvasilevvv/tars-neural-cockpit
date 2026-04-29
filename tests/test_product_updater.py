"""Phase L9 K2 — tauri-plugin-updater channel publisher tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.product.publish import main as publish_main
from backend.core.product.updater import (
    TauriChannel,
    build_channel,
    write_channel_files,
)


# ---------------------------------------------------------------------
# build_channel
# ---------------------------------------------------------------------


def _art(os: str, arch: str, kind: str, filename: str = "x", url: str = "https://x") -> dict:
    return {"os": os, "arch": arch, "kind": kind, "filename": filename, "url": url}


def test_build_channel_picks_known_targets() -> None:
    channel = build_channel(
        [
            _art("macos", "arm64", "dmg", "TARS-1.0.0-arm64.dmg", "https://e/m1.dmg"),
            _art("macos", "x64", "dmg", "TARS-1.0.0-x64.dmg", "https://e/mi.dmg"),
            _art("windows", "x64", "msi", "TARS-1.0.0.msi", "https://e/w.msi"),
            _art("windows", "x64", "exe", "TARS-1.0.0-Setup.exe", "https://e/w.exe"),
            _art("linux", "x64", "appimage", "TARS-1.0.0.AppImage", "https://e/l.app"),
        ],
        version="1.0.0",
        notes="hello",
    )
    targets = {p.target for p in channel.platforms}
    assert "darwin-aarch64" in targets
    assert "darwin-x86_64" in targets
    assert "windows-x86_64" in targets
    assert "linux-x86_64" in targets


def test_build_channel_drops_unknown_targets() -> None:
    channel = build_channel(
        [
            _art("ios", "arm64", "ipa"),
            _art("android", "arm64", "apk"),
            _art("freebsd", "x64", "tar.gz"),
        ],
        version="1.0.0",
        notes="",
    )
    assert channel.platforms == ()


def test_build_channel_payload_shape() -> None:
    channel = build_channel(
        [_art("macos", "arm64", "dmg", "F.dmg", "https://x/F.dmg")],
        version="1.2.3",
        notes="hi",
        pub_date="2026-04-29T12:00:00Z",
    )
    payload = channel.to_dict()
    assert payload["version"] == "1.2.3"
    assert payload["notes"] == "hi"
    assert payload["pub_date"] == "2026-04-29T12:00:00Z"
    assert payload["platforms"]["darwin-aarch64"] == {
        "signature": "",
        "url": "https://x/F.dmg",
    }


def test_build_channel_picks_up_sidecar_signature(tmp_path: Path) -> None:
    art_path = tmp_path / "TARS-1.0.0.app.tar.gz"
    art_path.write_bytes(b"fake")
    sig_path = tmp_path / "TARS-1.0.0.app.tar.gz.sig"
    sig_path.write_text("MINISIGN_BASE64_FAKE_SIGNATURE_HERE\n", encoding="utf-8")

    channel = build_channel(
        [
            _art(
                "macos",
                "arm64",
                "app",
                filename=art_path.name,
                url="https://x/" + art_path.name,
            )
        ],
        version="1.0.0",
        notes="",
        artifacts_dir=tmp_path,
    )
    plat = channel.platforms[0]
    assert plat.target == "darwin-aarch64"
    assert plat.signature == "MINISIGN_BASE64_FAKE_SIGNATURE_HERE"


def test_build_channel_prefers_signed_over_unsigned(tmp_path: Path) -> None:
    """If we have both an .app.tar.gz with .sig AND a .dmg without one for
    the same target, the signed one wins."""

    app_path = tmp_path / "TARS.app.tar.gz"
    app_path.write_bytes(b"fake")
    (tmp_path / "TARS.app.tar.gz.sig").write_text("SIGNED\n")
    dmg_path = tmp_path / "TARS-arm64.dmg"
    dmg_path.write_bytes(b"fake")

    arts = [
        _art("macos", "arm64", "dmg", dmg_path.name, "https://x/" + dmg_path.name),
        _art("macos", "arm64", "app", app_path.name, "https://x/" + app_path.name),
    ]
    channel = build_channel(arts, version="1.0.0", notes="", artifacts_dir=tmp_path)
    plat = next(p for p in channel.platforms if p.target == "darwin-aarch64")
    assert plat.signature == "SIGNED"
    assert plat.url.endswith(".app.tar.gz")


# ---------------------------------------------------------------------
# write_channel_files
# ---------------------------------------------------------------------


def test_write_channel_files_creates_target_subdirs(tmp_path: Path) -> None:
    channel = build_channel(
        [
            _art("macos", "arm64", "dmg", "M.dmg", "https://x/M.dmg"),
            _art("windows", "x64", "msi", "W.msi", "https://x/W.msi"),
        ],
        version="1.0.0",
        notes="release",
        pub_date="2026-04-29T12:00:00Z",
    )
    out_dir = tmp_path / "updates"
    written = write_channel_files(channel, out_dir=out_dir, current_versions=("latest",))

    assert (out_dir / "darwin-aarch64" / "1.0.0.json").exists()
    assert (out_dir / "darwin-aarch64" / "latest.json").exists()
    assert (out_dir / "windows-x86_64" / "1.0.0.json").exists()
    assert (out_dir / "windows-x86_64" / "latest.json").exists()
    assert len(written) == 4

    payload = json.loads((out_dir / "darwin-aarch64" / "1.0.0.json").read_text())
    assert payload["version"] == "1.0.0"
    assert payload["pub_date"] == "2026-04-29T12:00:00Z"
    assert payload["platforms"]["darwin-aarch64"]["url"] == "https://x/M.dmg"


# ---------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------


def test_publish_cli_emits_updater_when_flag_given(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    (src / "TARS-1.0.0-arm64.dmg").write_bytes(b"fake-dmg")
    (src / "TARS-1.0.0_x64-setup.exe").write_bytes(b"fake-exe")

    out = tmp_path / "releases.json"
    updater_dir = tmp_path / "updates"

    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--channel",
            "stable",
            "--notes",
            "First release.",
            "--out",
            str(out),
            "--base-url",
            "https://meeet.world/downloads/tars",
            "--updater-out",
            str(updater_dir),
            "--updater-alias",
            "latest",
        ]
    )
    assert rc == 0

    # Both manifests landed.
    assert (out).exists()
    assert (updater_dir / "darwin-aarch64" / "1.0.0.json").exists()
    assert (updater_dir / "darwin-aarch64" / "latest.json").exists()
    assert (updater_dir / "windows-x86_64" / "1.0.0.json").exists()

    payload = json.loads((updater_dir / "windows-x86_64" / "latest.json").read_text())
    assert payload["version"] == "1.0.0"
    assert payload["platforms"]["windows-x86_64"]["url"].endswith("setup.exe")
    # No sig file shipped → empty signature is the safe default.
    assert payload["platforms"]["windows-x86_64"]["signature"] == ""


def test_publish_cli_without_updater_flag_skips_channel(tmp_path: Path) -> None:
    src = tmp_path / "build"
    src.mkdir()
    (src / "TARS-1.0.0-arm64.dmg").write_bytes(b"fake")

    out = tmp_path / "releases.json"
    updater_dir = tmp_path / "updates"

    rc = publish_main(
        [
            str(src),
            "--version",
            "1.0.0",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()
    assert not updater_dir.exists()
