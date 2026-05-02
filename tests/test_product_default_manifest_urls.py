"""Bug #9 contract — DEFAULT_MANIFEST resolves to GitHub Releases.

Pre-2026-05-02 audit, the default URL base was
``https://meeet.world/downloads/tars/...`` which 404s — the
marketing CDN never hosted the artefacts. CI publishes them
straight to GitHub Releases, so the defaults must point there.

This test pins the new contract:

- No artefact in ``DEFAULT_MANIFEST`` references ``meeet.world``.
- Every artefact in ``DEFAULT_MANIFEST`` resolves to the
  ``github.com/<owner>/<repo>/releases/download/v<version>/<file>``
  pattern, which never 404s as long as the release exists.
- ``TARS_DOWNLOAD_BASE_URL`` env override still takes precedence
  for self-hosted CDNs (backward-compat preserved).
"""

from __future__ import annotations

import importlib

import pytest


def _reload_manifest_module():
    """Reload the module so default URLs pick up env changes."""
    import backend.core.product.manifest as mod

    importlib.reload(mod)
    return mod


def test_default_manifest_has_no_legacy_meeet_urls() -> None:
    mod = _reload_manifest_module()
    bad = []
    for entry in mod.DEFAULT_MANIFEST.releases:
        for art in entry.artifacts:
            if "meeet.world/downloads" in art.url:
                bad.append(art.url)
    assert not bad, (
        "DEFAULT_MANIFEST still points to the legacy meeet.world/downloads "
        f"CDN that 404s; offending URLs:\n  - "
        + "\n  - ".join(bad)
    )


def test_default_manifest_resolves_to_github_releases() -> None:
    mod = _reload_manifest_module()
    for entry in mod.DEFAULT_MANIFEST.releases:
        for art in entry.artifacts:
            assert art.url.startswith(
                "https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/"
            ), (
                f"DEFAULT_MANIFEST artefact URL must point to GitHub Releases; "
                f"got: {art.url}"
            )
            assert f"/v{entry.version}/" in art.url, (
                f"GitHub Releases URLs must include the v-prefixed version "
                f"path; got: {art.url}"
            )


def test_download_base_url_env_override_still_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Self-hosters that set ``TARS_DOWNLOAD_BASE_URL`` keep working."""
    monkeypatch.setenv("TARS_DOWNLOAD_BASE_URL", "https://my-cdn.example.com/tars")
    mod = _reload_manifest_module()
    art = mod.DEFAULT_MANIFEST.releases[0].artifacts[0]
    assert art.url.startswith("https://my-cdn.example.com/tars/"), (
        f"override ignored: {art.url}"
    )


def test_tauri_updater_endpoint_points_to_github_releases() -> None:
    """``tauri.conf.json`` updater endpoint MUST resolve via GitHub
    Releases (the only host that publishes ``latest.json`` from CI).
    Pinning here so it doesn't drift back to the 404'ing
    ``meeet.world/updates`` URL while no one's looking."""

    import json
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    cfg = json.loads(
        (repo / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )
    endpoints = cfg["plugins"]["updater"]["endpoints"]
    assert endpoints, "updater.endpoints empty — auto-update will never poll"
    for ep in endpoints:
        assert "meeet.world/updates" not in ep, (
            "updater endpoint still points to the legacy meeet.world/updates "
            f"CDN that 404s: {ep}"
        )
    assert any(
        "github.com" in ep and "releases/latest/download/latest.json" in ep
        for ep in endpoints
    ), (
        "at least one updater endpoint must use the GitHub Releases "
        "latest-tag pattern so CI-published latest.json is always served"
    )
