"""Public product surface — release manifest for direct-download distribution.

Phase **L9** ships TARS as signed `.dmg` / `.exe` artifacts hosted on
the official site (HTTPS, SHA256-checksum, `tauri-plugin-updater`).
The marketing site (and `meeet.world`) consume this manifest instead of
scraping HTML so download links never go stale.

Stdlib-only — no extra deps, no DB. Source of truth is JSON on disk
under ``$TARS_RELEASES_PATH`` (default
``~/.tars/releases.json``); falls back to a ``defaults`` block bundled
with the source so the API never returns an empty list.
"""

from .manifest import (
    DEFAULT_MANIFEST,
    DownloadManifest,
    ReleaseArtifact,
    ReleaseEntry,
    load_manifest,
    resolve_url,
)

__all__ = [
    "DEFAULT_MANIFEST",
    "DownloadManifest",
    "ReleaseArtifact",
    "ReleaseEntry",
    "load_manifest",
    "resolve_url",
]
