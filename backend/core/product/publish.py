"""``python -m backend.core.product.publish`` — release publishing CLI.

Walks a build directory, picks up the artifacts that match a known
filename pattern, computes SHA256, and writes (or appends to) the
canonical ``releases.json`` consumed by
``GET /api/product/downloads``.

Usage:

    python -m backend.core.product.publish \\
        path/to/build/dir \\
        --version 1.0.0 \\
        [--channel stable] \\
        [--notes "First stable. Mac notarised, Windows AC-signed."] \\
        [--out ~/.tars/releases.json] \\
        [--base-url https://meeet.world/downloads/tars] \\
        [--copy-to dist/releases/1.0.0/]

Filename → artifact mapping (case-insensitive):

    *.dmg          → os=macos, kind=dmg
    *.pkg          → os=macos, kind=pkg
    *.app(.tar.gz) → os=macos, kind=app
    *Setup.exe     → os=windows, kind=exe
    *.msi          → os=windows, kind=msi
    *.appimage     → os=linux, kind=appimage
    *.deb          → os=linux, kind=deb
    *.ipa          → os=ios, kind=ipa
    *.apk          → os=android, kind=apk
    *.aab          → os=android, kind=aab

Architecture is sniffed from the filename:

    arm64 / aarch64 / apple-silicon  → arm64
    x64 / x86_64 / amd64             → x64
    universal                        → universal
    (anything else)                  → any
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .manifest import (
    CONTRACT_VERSION,
    ENV_DOWNLOAD_BASE,
    ENV_RELEASES_PATH,
)
from .updater import build_channel, write_channel_files


CHUNK = 1024 * 1024  # 1 MiB


@dataclass
class SniffedArtifact:
    os: str
    arch: str
    kind: str
    filename: str
    size_bytes: int
    sha256: str
    url: str


# ---------------------------------------------------------------------
# Sniffers
# ---------------------------------------------------------------------


def _sniff_kind_and_os(name: str) -> tuple[str, str] | None:
    lower = name.lower()
    if lower.endswith(".dmg"):
        return "macos", "dmg"
    if lower.endswith(".pkg"):
        return "macos", "pkg"
    if lower.endswith(".app.tar.gz") or lower.endswith(".app.zip"):
        return "macos", "app"
    if lower.endswith(".msi"):
        return "windows", "msi"
    if lower.endswith(".exe"):
        return "windows", "exe"
    if lower.endswith(".appimage"):
        return "linux", "appimage"
    if lower.endswith(".deb"):
        return "linux", "deb"
    if lower.endswith(".ipa"):
        return "ios", "ipa"
    if lower.endswith(".apk"):
        return "android", "apk"
    if lower.endswith(".aab"):
        return "android", "aab"
    return None


def _sniff_arch(name: str) -> str:
    lower = name.lower()
    if "arm64" in lower or "aarch64" in lower or "apple-silicon" in lower or "applesilicon" in lower:
        return "arm64"
    if "x86_64" in lower or "amd64" in lower or "x64" in lower:
        return "x64"
    if "universal" in lower:
        return "universal"
    if "x86" in lower or "i386" in lower:
        return "x86"
    return "any"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            buf = handle.read(CHUNK)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _resolve_url(filename: str, *, version: str, base_url: str | None) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        return f"/releases/{version}/{filename}"
    return f"{base}/{version}/{filename}"


def collect_artifacts(
    src: Path,
    *,
    version: str,
    base_url: str | None = None,
) -> list[SniffedArtifact]:
    """Walk ``src``, return sniffed artifacts (no I/O beyond hashing)."""

    if not src.is_dir():
        raise FileNotFoundError(f"build directory not found: {src}")

    out: list[SniffedArtifact] = []
    for entry in sorted(src.iterdir()):
        if not entry.is_file():
            continue
        sniffed = _sniff_kind_and_os(entry.name)
        if sniffed is None:
            continue
        os_id, kind = sniffed
        out.append(
            SniffedArtifact(
                os=os_id,
                arch=_sniff_arch(entry.name),
                kind=kind,
                filename=entry.name,
                size_bytes=entry.stat().st_size,
                sha256=_sha256_of(entry),
                url=_resolve_url(entry.name, version=version, base_url=base_url),
            )
        )
    return out


# ---------------------------------------------------------------------
# Manifest writers
# ---------------------------------------------------------------------


def _now_isoformat() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _existing_releases(out_path: Path) -> list[dict]:
    if not out_path.exists():
        return []
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("releases"), list):
        return [r for r in data["releases"] if isinstance(r, dict)]
    return []


def build_manifest(
    artifacts: Iterable[SniffedArtifact],
    *,
    version: str,
    channel: str,
    notes: str | None,
    out_path: Path,
    released_at: str | None = None,
) -> dict:
    arts = list(artifacts)
    released = released_at or _now_isoformat()

    # Drop any existing release with the same version+channel (re-publish).
    keep = [
        r
        for r in _existing_releases(out_path)
        if not (r.get("version") == version and (r.get("channel") or "stable") == channel)
    ]

    new_release = {
        "version": version,
        "channel": channel,
        "released_at": released,
        "notes": notes,
        "artifacts": [
            {
                "os": a.os,
                "arch": a.arch,
                "kind": a.kind,
                "filename": a.filename,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "url": a.url,
                "signature_url": None,
            }
            for a in arts
        ],
    }

    return {
        "product": "tars",
        "contract_version": CONTRACT_VERSION,
        "channel": channel,
        "released_at": released,
        "releases": [new_release, *keep],
    }


def write_manifest(manifest: dict, *, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def maybe_copy_artifacts(
    src: Path,
    artifacts: Iterable[SniffedArtifact],
    *,
    copy_to: Path | None,
) -> list[Path]:
    if copy_to is None:
        return []
    copy_to.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for art in artifacts:
        target = copy_to / art.filename
        if target.exists() and target.stat().st_size == art.size_bytes:
            copied.append(target)
            continue
        shutil.copy2(src / art.filename, target)
        copied.append(target)
    return copied


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="backend.core.product.publish",
        description="Publish a TARS release into ~/.tars/releases.json.",
    )
    p.add_argument("build_dir", type=Path, help="Directory containing built installers.")
    p.add_argument("--version", required=True, help="Semver, e.g. 1.0.0.")
    p.add_argument("--channel", default="stable", choices=["stable", "beta", "nightly"])
    p.add_argument("--notes", default=None)
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Path to releases.json (default: ${ENV_RELEASES_PATH} or ~/.tars/releases.json).",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help=f"URL prefix for artifacts (default: ${ENV_DOWNLOAD_BASE}).",
    )
    p.add_argument(
        "--copy-to",
        type=Path,
        default=None,
        help="Optional staging directory to mirror artifacts into.",
    )
    p.add_argument(
        "--released-at",
        default=None,
        help="Override timestamp (ISO 8601 UTC). Default: now().",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting manifest to stdout instead of writing.",
    )
    p.add_argument(
        "--updater-out",
        type=Path,
        default=None,
        help=(
            "Optional directory to write the Tauri updater channel JSON files "
            "(<target>/<version>.json). When omitted, no updater channel is "
            "produced."
        ),
    )
    p.add_argument(
        "--updater-alias",
        action="append",
        default=None,
        help=(
            "Extra alias filenames inside each updater target dir (e.g. 'latest'). "
            "Repeatable. Useful for stable URLs the marketing site can hard-link."
        ),
    )
    return p


def _resolve_out(out: Path | None) -> Path:
    if out is not None:
        return out.expanduser()
    raw = os.getenv(ENV_RELEASES_PATH) or "~/.tars/releases.json"
    return Path(os.path.expanduser(raw))


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    src = args.build_dir.expanduser().resolve()
    out = _resolve_out(args.out)
    base_url = args.base_url or os.getenv(ENV_DOWNLOAD_BASE)

    arts = collect_artifacts(src, version=args.version, base_url=base_url)
    if not arts:
        print(f"[publish] no recognisable artifacts in {src}", file=sys.stderr)
        return 1

    manifest = build_manifest(
        arts,
        version=args.version,
        channel=args.channel,
        notes=args.notes,
        out_path=out,
        released_at=args.released_at,
    )

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return 0

    write_manifest(manifest, out_path=out)
    copied = maybe_copy_artifacts(src, arts, copy_to=args.copy_to)

    updater_files: list[Path] = []
    if args.updater_out is not None:
        channel = build_channel(
            (
                {
                    "os": a.os,
                    "arch": a.arch,
                    "kind": a.kind,
                    "filename": a.filename,
                    "url": a.url,
                }
                for a in arts
            ),
            version=args.version,
            notes=args.notes,
            pub_date=args.released_at,
            artifacts_dir=src,
        )
        updater_files = write_channel_files(
            channel,
            out_dir=args.updater_out.expanduser(),
            current_versions=tuple(args.updater_alias or ()),
        )

    print(
        f"[publish] {args.version} ({args.channel}) → {out} · {len(arts)} artifact(s)"
        + (f" · copied {len(copied)} → {args.copy_to}" if copied else "")
        + (
            f" · updater {len(updater_files)} files → {args.updater_out}"
            if updater_files
            else ""
        )
    )
    for art in arts:
        print(f"  - {art.os:<7} {art.arch:<9} {art.kind:<8} {art.filename}  sha256={art.sha256[:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
