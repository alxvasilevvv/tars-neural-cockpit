"""Tauri updater channel JSON publisher (Phase L9 K2).

The Tauri ``updater`` plugin (v2) consumes a per-target JSON file at
``https://meeet.world/updates/<target>/<current_version>.json`` (the
shape used by ``tauri-plugin-updater``). The channel file is
**separate** from ``releases.json`` (which is human / cockpit
oriented) — it has a different shape and lives at a different URL,
so we generate it as a sibling artefact.

Wire shape (per the v2 plugin docs):

```jsonc
{
  "version":   "1.0.0",
  "notes":     "Release notes (Markdown allowed).",
  "pub_date":  "2026-04-29T12:00:00Z",
  "platforms": {
    "darwin-aarch64": { "signature": "<minisign base64>", "url": "https://…" },
    "darwin-x86_64":  { "signature": "<…>",                "url": "https://…" },
    "darwin-universal": { "signature": "<…>",              "url": "https://…" },
    "windows-x86_64": { "signature": "<…>",                "url": "https://…" },
    "linux-x86_64":   { "signature": "<…>",                "url": "https://…" }
  }
}
```

Signatures are produced by ``tauri signer sign`` against a private
``minisign``/Ed25519 key the project keeps in CI. Locally we read
sidecar ``<filename>.sig`` files when present and leave the field as
an empty string otherwise — the Tauri client will refuse such an
update unless ``pubkey`` is also empty in ``tauri.conf.json``, which
is exactly the safe default for a dev environment.

This module is **stdlib-only** so it can run in any pipeline.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


# Mapping (os, arch, kind) -> Tauri target slug. ``kind`` matters only
# for macOS (``app`` archives are what the updater downloads, while
# ``dmg``/``pkg`` are first-install installers).
_TARGET_BY_OS_ARCH: dict[tuple[str, str], str] = {
    ("macos", "arm64"): "darwin-aarch64",
    ("macos", "x64"): "darwin-x86_64",
    ("macos", "universal"): "darwin-universal",
    ("windows", "x64"): "windows-x86_64",
    ("windows", "arm64"): "windows-aarch64",
    ("windows", "x86"): "windows-i686",
    ("linux", "x64"): "linux-x86_64",
    ("linux", "arm64"): "linux-aarch64",
}

# When an artifact's kind isn't one the Tauri updater can install
# in-place, drop it from the channel manifest. The first-install
# installers (``dmg``, ``msi``, ``exe``) stay in ``releases.json`` so
# the website still surfaces them; the updater itself wants the
# self-contained ``app.tar.gz`` / ``msi`` / ``AppImage`` flavour.
_UPDATER_KINDS_BY_OS: dict[str, set[str]] = {
    "macos": {"app", "dmg"},   # dmg is fine when an app.tar.gz isn't present
    "windows": {"msi", "nsis", "exe"},
    "linux": {"appimage", "deb"},
}


@dataclass(frozen=True)
class TauriPlatformEntry:
    target: str
    signature: str
    url: str


@dataclass(frozen=True)
class TauriChannel:
    version: str
    notes: str
    pub_date: str
    platforms: tuple[TauriPlatformEntry, ...]

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "notes": self.notes,
            "pub_date": self.pub_date,
            "platforms": {
                p.target: {"signature": p.signature, "url": p.url}
                for p in self.platforms
            },
        }


def _now_isoformat() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_sidecar_signature(art_path: Path | None) -> str:
    """Return the contents of ``<artifact>.sig`` if present.

    Tauri's signer writes a single-line minisign-style signature into a
    ``.sig`` sidecar; we simply pass it through. When no sidecar is
    present we return an empty string so the client side decides how
    to handle the missing signature (the safe default in dev is for
    ``pubkey`` to be empty too, which makes Tauri skip verification).
    """

    if art_path is None:
        return ""
    sig_path = art_path.with_suffix(art_path.suffix + ".sig")
    if not sig_path.exists():
        return ""
    try:
        return sig_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def build_channel(
    artifacts: Iterable[Mapping],
    *,
    version: str,
    notes: str | None,
    pub_date: str | None = None,
    artifacts_dir: Path | None = None,
) -> TauriChannel:
    """Build a :class:`TauriChannel` from sniffed artifact dicts.

    ``artifacts`` accepts plain dicts (so the publish CLI can pass
    SniffedArtifact-as-dict, and tests can pass fixtures directly)
    with the keys ``os``, ``arch``, ``kind``, ``filename``, ``url``.
    Architectures / kinds that don't map to a Tauri target are
    skipped silently — releases.json still carries them.
    """

    platforms: dict[str, TauriPlatformEntry] = {}
    for art in artifacts:
        os_id = str(art.get("os") or "")
        arch = str(art.get("arch") or "")
        kind = str(art.get("kind") or "")
        target = _TARGET_BY_OS_ARCH.get((os_id, arch))
        if target is None:
            continue
        if kind not in _UPDATER_KINDS_BY_OS.get(os_id, set()):
            continue

        filename = str(art.get("filename") or "")
        url = str(art.get("url") or "")
        sig_path = artifacts_dir / filename if (artifacts_dir and filename) else None
        signature = _read_sidecar_signature(sig_path)

        # When two artifacts target the same Tauri slug (e.g. ``app`` and
        # ``dmg`` for macOS arm64) prefer the first one we encounter
        # that has a signature; fall back to the first overall.
        existing = platforms.get(target)
        if existing and existing.signature and not signature:
            continue
        if existing and not existing.signature and not signature:
            # Nothing better available — keep the first.
            continue
        platforms[target] = TauriPlatformEntry(
            target=target,
            signature=signature,
            url=url,
        )

    return TauriChannel(
        version=version,
        notes=notes or "",
        pub_date=pub_date or _now_isoformat(),
        platforms=tuple(platforms[k] for k in sorted(platforms)),
    )


def write_channel_files(
    channel: TauriChannel,
    *,
    out_dir: Path,
    current_versions: Iterable[str] | None = None,
) -> list[Path]:
    """Write the per-target ``<target>/<version>.json`` files.

    The Tauri updater hits ``…/<target>/<current_version>.json`` to
    decide whether a newer release is available, so we write the same
    blob into one file per target slug. Optionally also write under
    ``current_versions`` (e.g. ``["latest"]``) so the marketing site
    can hard-link a stable URL.
    """

    payload = channel.to_dict()
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for plat in channel.platforms:
        target_dir = out_dir / plat.target
        target_dir.mkdir(parents=True, exist_ok=True)
        # Primary file: <target>/<version>.json
        primary = target_dir / f"{channel.version}.json"
        primary.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        written.append(primary)
        for alias in current_versions or ():
            alias_path = target_dir / f"{alias}.json"
            alias_path.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            written.append(alias_path)
    return written
