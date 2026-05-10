"""Download manifest loader.

The manifest is a small, stable JSON document the marketing site and
``meeet.world`` consume to render download buttons and feed
``tauri-plugin-updater`` once L9 ships installers.

**Wire shape** (versioned via ``contract_version``):

```json
{
  "product": "tars",
  "contract_version": "1.0.0",
  "channel": "stable",
  "released_at": "2026-04-29T00:00:00Z",
  "releases": [
    {
      "version": "0.1.0-alpha.2",
      "channel": "stable",
      "released_at": "2026-04-29T00:00:00Z",
      "notes": "Phase M backbone — see release notes.",
      "artifacts": [
        {
          "os": "macos",
          "arch": "arm64",
          "kind": "dmg",
          "filename": "TARS-0.1.0-alpha.2-arm64.dmg",
          "size_bytes": null,
          "sha256": null,
          "url": "https://meeet.world/downloads/tars/0.1.0-alpha.2/TARS-0.1.0-alpha.2-arm64.dmg",
          "signature_url": null
        }
      ]
    }
  ]
}
```

Why stdlib only / dataclasses-only:

- avoids forcing pydantic on the public surface;
- the manifest is tiny (≪ 100 KB);
- callers (cockpit, meeet.world SSR) get plain JSON they can cache.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


log = logging.getLogger("tars.product.manifest")


# Bumped when the wire shape changes. Consumers should refuse manifests
# whose contract_version major doesn't match.
CONTRACT_VERSION = "1.0.0"

DEFAULT_RELEASES_PATH = "~/.tars/releases.json"
ENV_RELEASES_PATH = "TARS_RELEASES_PATH"
ENV_DOWNLOAD_BASE = "TARS_DOWNLOAD_BASE_URL"

# Bug #9 fix from docs/SYSTEM_AUDIT_2026-05-02.md — the legacy
# default base ``https://meeet.world/downloads/tars`` 404s because
# the marketing CDN never hosted the artefacts; CI publishes them
# straight to GitHub Releases instead. Override via
# ``TARS_DOWNLOAD_BASE_URL`` if you self-host.
GITHUB_RELEASES_BASE = (
    "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download"
)

VALID_OS = {"macos", "windows", "linux", "ios", "android"}
VALID_ARCH = {"arm64", "x64", "x86", "universal", "any"}
VALID_KIND = {"dmg", "pkg", "app", "exe", "msi", "appimage", "deb", "ipa", "apk", "aab"}


@dataclass(frozen=True)
class ReleaseArtifact:
    os: str
    arch: str
    kind: str
    filename: str
    url: str
    size_bytes: int | None = None
    sha256: str | None = None
    signature_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "os": self.os,
            "arch": self.arch,
            "kind": self.kind,
            "filename": self.filename,
            "url": self.url,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "signature_url": self.signature_url,
        }


@dataclass(frozen=True)
class ReleaseEntry:
    version: str
    channel: str
    released_at: str
    notes: str | None
    artifacts: tuple[ReleaseArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "channel": self.channel,
            "released_at": self.released_at,
            "notes": self.notes,
            "artifacts": [a.to_dict() for a in self.artifacts],
        }


@dataclass(frozen=True)
class DownloadManifest:
    product: str
    contract_version: str
    channel: str
    released_at: str
    releases: tuple[ReleaseEntry, ...]
    source: str  # "defaults" | "file:<path>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "product": self.product,
            "contract_version": self.contract_version,
            "channel": self.channel,
            "released_at": self.released_at,
            "source": self.source,
            "releases": [r.to_dict() for r in self.releases],
        }

    def latest(self, *, os_id: str | None = None, channel: str | None = None) -> ReleaseEntry | None:
        for entry in self.releases:
            if channel and entry.channel != channel:
                continue
            if os_id is None:
                return entry
            for art in entry.artifacts:
                if art.os == os_id:
                    return entry
        return None


# ---------------------------------------------------------------------
# Defaults — what the API returns when no releases.json is on disk.
# Treat this as a tiny "we exist" payload so the marketing site
# doesn't break before the first real release lands.
# ---------------------------------------------------------------------


def _placeholder_url(version: str, filename: str) -> str:
    """Build a download URL for the manifest defaults.

    Resolution order:

    1. ``TARS_DOWNLOAD_BASE_URL`` env override → ``{base}/{version}/{filename}``
       (preserves backward compatibility for self-hosted CDNs).
    2. Otherwise fall through to the canonical GitHub Releases URL
       pattern: ``{GITHUB_RELEASES_BASE}/v{version}/{filename}``. GitHub
       hosts the artefacts forever as long as the release isn't deleted,
       and the URL never 404s the way ``meeet.world/downloads`` did
       before Bug #9 was fixed.
    """

    override = (os.getenv(ENV_DOWNLOAD_BASE) or "").strip().rstrip("/")
    if override:
        return f"{override}/{version}/{filename}"
    # GitHub Releases tag is conventionally ``v<version>`` (CI uses
    # ``${{ github.ref_name }}`` directly).
    return f"{GITHUB_RELEASES_BASE}/v{version}/{filename}"


# Wave 71-C — cross-target install funnel. v9.1.0 advertises macOS
# (.dmg, both archs), Windows (NSIS .exe), and Linux (.AppImage +
# .deb). The pyoxidizer cross-target pipeline (`desktop/pyoxidizer.bzl`
# + `release-desktop-tagged.yml`) builds these from the same matrix,
# the `/dl/<file>` Cloudflare proxy allowlist accepts them, and the
# install funnel (`tars.meeet.world/install.sh`) routes by `uname`.
# If a release is missing one target the proxy returns
# `asset_not_found_in_release` (404) instead of an opaque 500 — keeps
# the funnel honest without dropping the entry from the manifest.
_DEFAULT_VERSION = "9.1.0"
_DEFAULT_NOTES = (
    "v9.1.0 — desktop release across macOS / Windows / Linux. "
    "Wallets, council agents, entitlements/roles, OCR vision, "
    "Entrepreneur pack. Cross-target installers built from the "
    "pyoxidizer matrix (Wave 71-C)."
)
# CI artifact filenames are `TARS_<version>_<arch>.<ext>` (underscore
# + raw arch like `aarch64` / `x64` / `amd64`). Mirror exactly so
# /dl/<file> redirects + `release-desktop-tagged.yml` upload paths
# match byte-for-byte.
_DEFAULT_ARTIFACTS: tuple[ReleaseArtifact, ...] = (
    ReleaseArtifact(
        os="macos",
        arch="arm64",
        kind="dmg",
        filename=f"TARS_{_DEFAULT_VERSION}_aarch64.dmg",
        url=_placeholder_url(_DEFAULT_VERSION, f"TARS_{_DEFAULT_VERSION}_aarch64.dmg"),
    ),
    ReleaseArtifact(
        os="macos",
        arch="x64",
        kind="dmg",
        filename=f"TARS_{_DEFAULT_VERSION}_x64.dmg",
        url=_placeholder_url(_DEFAULT_VERSION, f"TARS_{_DEFAULT_VERSION}_x64.dmg"),
    ),
    ReleaseArtifact(
        os="windows",
        arch="x64",
        kind="exe",
        filename=f"TARS_{_DEFAULT_VERSION}_x64-setup.exe",
        url=_placeholder_url(
            _DEFAULT_VERSION, f"TARS_{_DEFAULT_VERSION}_x64-setup.exe"
        ),
    ),
    ReleaseArtifact(
        os="linux",
        arch="x64",
        kind="appimage",
        filename=f"TARS_{_DEFAULT_VERSION}_amd64.AppImage",
        url=_placeholder_url(
            _DEFAULT_VERSION, f"TARS_{_DEFAULT_VERSION}_amd64.AppImage"
        ),
    ),
    ReleaseArtifact(
        os="linux",
        arch="x64",
        kind="deb",
        filename=f"TARS_{_DEFAULT_VERSION}_amd64.deb",
        url=_placeholder_url(
            _DEFAULT_VERSION, f"TARS_{_DEFAULT_VERSION}_amd64.deb"
        ),
    ),
)


DEFAULT_MANIFEST = DownloadManifest(
    product="tars",
    contract_version=CONTRACT_VERSION,
    channel="stable",
    released_at="2026-05-09T00:00:00Z",
    releases=(
        ReleaseEntry(
            version=_DEFAULT_VERSION,
            channel="stable",
            released_at="2026-05-09T00:00:00Z",
            notes=_DEFAULT_NOTES,
            artifacts=_DEFAULT_ARTIFACTS,
        ),
    ),
    source="defaults",
)


# ---------------------------------------------------------------------
# Loading + URL resolution
# ---------------------------------------------------------------------


def _resolve_path() -> Path:
    raw = os.getenv(ENV_RELEASES_PATH) or DEFAULT_RELEASES_PATH
    return Path(os.path.expanduser(raw))


def resolve_url(url: str | None, *, base: str | None = None) -> str | None:
    """Resolve a manifest URL against ``TARS_DOWNLOAD_BASE_URL``.

    - Absolute URLs (``http(s)://...``) are returned unchanged.
    - Empty or ``None`` returns ``None``.
    - Anything else is treated as a path under the base.
    """

    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    base_url = (base or os.getenv(ENV_DOWNLOAD_BASE) or "").rstrip("/")
    if not base_url:
        return url
    return f"{base_url}/{url.lstrip('/')}"


def _coerce_artifact(raw: Mapping[str, Any]) -> ReleaseArtifact | None:
    try:
        os_id = str(raw["os"]).lower()
        arch = str(raw.get("arch") or "any").lower()
        kind = str(raw["kind"]).lower()
        filename = str(raw["filename"])
        url = resolve_url(str(raw["url"])) or str(raw["url"])
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("manifest.skip_artifact: %s · %s", exc, raw)
        return None
    if os_id not in VALID_OS:
        log.warning("manifest.skip_artifact: unknown os=%s", os_id)
        return None
    if arch not in VALID_ARCH:
        log.warning("manifest.skip_artifact: unknown arch=%s", arch)
        return None
    if kind not in VALID_KIND:
        log.warning("manifest.skip_artifact: unknown kind=%s", kind)
        return None
    size = raw.get("size_bytes")
    sha = raw.get("sha256")
    sig = raw.get("signature_url")
    return ReleaseArtifact(
        os=os_id,
        arch=arch,
        kind=kind,
        filename=filename,
        url=url,
        size_bytes=int(size) if size is not None else None,
        sha256=str(sha) if sha else None,
        signature_url=resolve_url(str(sig)) if sig else None,
    )


def _coerce_release(raw: Mapping[str, Any]) -> ReleaseEntry | None:
    try:
        version = str(raw["version"])
        channel = str(raw.get("channel") or "stable")
        released = str(raw.get("released_at") or "")
    except (KeyError, TypeError) as exc:
        log.warning("manifest.skip_release: %s · %s", exc, raw)
        return None
    arts: list[ReleaseArtifact] = []
    for raw_art in raw.get("artifacts") or []:
        if isinstance(raw_art, Mapping):
            art = _coerce_artifact(raw_art)
            if art is not None:
                arts.append(art)
    if not arts:
        log.warning("manifest.skip_release: no valid artifacts for version=%s", version)
        return None
    return ReleaseEntry(
        version=version,
        channel=channel,
        released_at=released,
        notes=str(raw["notes"]) if raw.get("notes") else None,
        artifacts=tuple(arts),
    )


def load_manifest(path: str | os.PathLike[str] | None = None) -> DownloadManifest:
    """Load the download manifest from disk, falling back to defaults.

    Soft-failure semantics: if the file is missing, malformed, or empty
    of valid releases, we return ``DEFAULT_MANIFEST`` so the marketing
    site never hard-fails on a 5xx.
    """

    target = Path(os.path.expanduser(str(path))) if path else _resolve_path()
    try:
        raw_text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DEFAULT_MANIFEST
    except OSError as exc:
        log.warning("manifest.read_failed: %s · %s", target, exc)
        return DEFAULT_MANIFEST

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        log.warning("manifest.parse_failed: %s · %s", target, exc)
        return DEFAULT_MANIFEST

    if not isinstance(raw, Mapping):
        return DEFAULT_MANIFEST

    contract = str(raw.get("contract_version") or CONTRACT_VERSION)
    if not contract.startswith(CONTRACT_VERSION.split(".")[0] + "."):
        log.warning(
            "manifest.contract_drift: file=%s expected_major=%s",
            contract,
            CONTRACT_VERSION,
        )

    releases: list[ReleaseEntry] = []
    for raw_release in raw.get("releases") or []:
        if isinstance(raw_release, Mapping):
            entry = _coerce_release(raw_release)
            if entry is not None:
                releases.append(entry)

    if not releases:
        return DEFAULT_MANIFEST

    return DownloadManifest(
        product=str(raw.get("product") or "tars"),
        contract_version=contract,
        channel=str(raw.get("channel") or "stable"),
        released_at=str(raw.get("released_at") or ""),
        releases=tuple(releases),
        source=f"file:{target}",
    )
