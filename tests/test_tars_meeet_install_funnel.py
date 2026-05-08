"""Pin the install-funnel contract for tars.meeet.world (B-017).

Three regressions guarded:

1. **Static `install.sh` is served direct, not redirected.** The
   `_redirects` rule that previously rewrote `/install.sh` to
   `raw.githubusercontent.com/...` returned the SPA HTML in production
   (the source repo went private and the raw URL 404s). Pages serves
   `public/install.sh` straight as a static file when no redirect
   matches — guard that the rule is gone.

2. **`functions/dl/[file].ts` proxy exists with a strict allowlist.**
   The Function gates downloads on `GITHUB_RELEASE_TOKEN` and an
   ALLOWED_FILENAMES set so we never become an open relay for the
   private repo.

3. **`install.sh` + `install-tars.sh` use same-origin URLs.**
   Both must hit `tars.meeet.world/api/product/version` for the
   manifest and `tars.meeet.world/dl/<file>` for binaries — direct
   `github.com/.../releases/download/...` URLs would 404 anonymously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SHOWCASE = REPO / "experiments" / "neural-showcase-v3"
REDIRECTS = SHOWCASE / "public" / "_redirects"
PUBLIC_INSTALL = SHOWCASE / "public" / "install.sh"
DL_FN = SHOWCASE / "functions" / "dl" / "[file].ts"
DOWNLOADS_FN = SHOWCASE / "functions" / "api" / "product" / "downloads.ts"
SCRIPTS_INSTALL = REPO / "scripts" / "install-tars.sh"


@pytest.fixture(scope="module")
def redirects() -> str:
    return REDIRECTS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def public_install() -> str:
    return PUBLIC_INSTALL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dl_fn() -> str:
    return DL_FN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def downloads_fn() -> str:
    return DOWNLOADS_FN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def install_tars() -> str:
    return SCRIPTS_INSTALL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. _redirects no longer hijacks /install.sh
# ---------------------------------------------------------------------------
def test_redirects_does_not_rewrite_install_sh(redirects: str) -> None:
    """The legacy `/install.sh → raw.githubusercontent.com/...` rule
    used to win over the static file in `public/install.sh`, and the
    raw URL 404s now that the repo is private. Removing the rule lets
    Pages serve the static file directly (B-017)."""
    for line in redirects.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # Active (non-comment) rules must not start with "/install.sh "
        # AND target raw.githubusercontent.com.
        if stripped.startswith("/install.sh") and "raw.githubusercontent.com" in stripped:
            pytest.fail(
                "Found active /install.sh → raw.githubusercontent.com rule in "
                "_redirects. This shadows public/install.sh and 404s on a "
                "private repo. Remove the rule and let Pages serve the static "
                "file directly. Offending line:\n  " + line
            )


def test_redirects_does_not_rewrite_dl(redirects: str) -> None:
    """`functions/dl/[file].ts` is the canonical handler for `/dl/*`.
    A bare 302 in `_redirects` would either bypass the auth proxy
    (and 404 anonymously) or, if it matches first, defeat the whole
    point of the Function. Keep `/dl/*` rules out of `_redirects`."""
    for line in redirects.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("/dl/"):
            pytest.fail(
                "Found active /dl/* rule in _redirects. The Pages Function "
                "at functions/dl/[file].ts must own that path. Move the rule "
                "into the Function or delete it. Offending line:\n  " + line
            )


# ---------------------------------------------------------------------------
# 2. Pages Function dl/[file].ts contract
# ---------------------------------------------------------------------------
def test_dl_fn_exists() -> None:
    assert DL_FN.exists(), (
        "functions/dl/[file].ts is missing — the install funnel cannot "
        "serve binaries while the source repo is private without it."
    )


def test_dl_fn_has_allowlist(dl_fn: str) -> None:
    assert "ALLOWED_FILENAMES" in dl_fn, (
        "dl Function must define an ALLOWED_FILENAMES allowlist so it "
        "doesn't proxy arbitrary paths in the private repo."
    )


@pytest.mark.parametrize(
    "filename",
    [
        "TARS_9.1.0_aarch64.dmg",
        "TARS_9.1.0_x64.dmg",
        "TARS_9.1.0_x64-setup.exe",
        "TARS_9.1.0_amd64.AppImage",
        "TARS_9.1.0_amd64.deb",
        "latest.json",
    ],
)
def test_dl_fn_allowlist_contains_canonical_v9_assets(
    dl_fn: str, filename: str
) -> None:
    assert filename in dl_fn, (
        f"Allowlist must include {filename!r} so the v9.1.0 install "
        "funnel resolves. Add it to ALLOWED_FILENAMES inside "
        "functions/dl/[file].ts."
    )


def test_dl_fn_requires_release_token(dl_fn: str) -> None:
    """Without the env var the Function MUST 503 with a clear hint —
    otherwise operators see opaque 500s and have no path to recovery."""
    assert "GITHUB_RELEASE_TOKEN" in dl_fn
    assert "operator_action_required" in dl_fn
    assert "503" in dl_fn


def test_dl_fn_uses_authenticated_github_api(dl_fn: str) -> None:
    """Using `Bearer ${TOKEN}` against api.github.com is what makes
    private-repo asset downloads possible (B-017)."""
    assert "api.github.com" in dl_fn
    assert "Bearer ${env.GITHUB_RELEASE_TOKEN}" in dl_fn or (
        "Bearer ${" in dl_fn and "GITHUB_RELEASE_TOKEN" in dl_fn
    )
    assert "x-github-api-version" in dl_fn


# ---------------------------------------------------------------------------
# 3. installer scripts route through tars.meeet.world
# ---------------------------------------------------------------------------
def _strip_shell_comments(src: str) -> str:
    """Drop comment-only lines and trailing comments so the test only
    inspects executable shell. Keeps shebangs (the `#!` is meaningful
    metadata, but it never contains URLs)."""
    out: list[str] = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#!"):
            out.append(line)
            continue
        if stripped.startswith("#") or not stripped:
            continue
        # Drop trailing `# comment` segments without breaking quoted strings —
        # we only care about URL substrings, so a naive split is fine here.
        if "#" in line and not (line.lstrip().startswith("\"") or line.lstrip().startswith("'")):
            line = line.split("#", 1)[0]
        out.append(line)
    return "\n".join(out)


def test_public_install_uses_same_origin(public_install: str) -> None:
    """`tars.meeet.world` is the canonical install funnel post-B-017.
    Direct github.com or api.github.com URLs would 404 anonymously."""
    assert "tars.meeet.world" in public_install
    assert "/api/product/version" in public_install
    assert "/dl/" in public_install
    code = _strip_shell_comments(public_install)
    assert "api.github.com" not in code, (
        "public/install.sh must not call api.github.com directly — the repo "
        "is private (B-017). Resolve the version via the same-origin "
        "/api/product/version Pages Function instead."
    )
    assert "github.com/" not in code, (
        "public/install.sh must not download from github.com/.../releases — "
        "use the /dl/<filename> proxy."
    )


def test_install_tars_uses_same_origin(install_tars: str) -> None:
    assert "tars.meeet.world" in install_tars
    assert "/dl/" in install_tars
    code = _strip_shell_comments(install_tars)
    assert "github.com/" not in code, (
        "scripts/install-tars.sh must route downloads through "
        "tars.meeet.world/dl/* — direct github.com URLs 404 on a "
        "private repo (B-017)."
    )


def test_install_tars_default_version_is_v910(install_tars: str) -> None:
    """Default version pinned at the same v9.1.0 the Pages Functions
    serve, so an offline-friendly fallback resolves the right asset."""
    assert "9.1.0" in install_tars


# ---------------------------------------------------------------------------
# 4. downloads.ts manifest also uses the proxy
# ---------------------------------------------------------------------------
def test_downloads_manifest_uses_dl_proxy(downloads_fn: str) -> None:
    assert "tars.meeet.world/dl" in downloads_fn, (
        "downloads.ts manifest must point artifact URLs at "
        "tars.meeet.world/dl/<filename> — github.com/.../releases URLs "
        "404 anonymously while the repo is private (B-017)."
    )


def test_downloads_manifest_lists_v910(downloads_fn: str) -> None:
    assert '"9.1.0"' in downloads_fn, (
        "downloads.ts manifest must surface v9.1.0 as a release entry; "
        "version.ts already advertises it."
    )
