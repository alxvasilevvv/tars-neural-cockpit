"""Drift smoke test — guards ``apps/cockpit/src/styles/tokens.css``
against the design contract in ``design-system/tars/MASTER.md``.

W308 step 0 scaffolds the new cockpit surface with a real source of
truth for design tokens. Two files now have to agree on every hex
and font value:

* ``design-system/tars/MASTER.md`` §3 (Palette) and §4 (Typography)
  — the prose contract, what humans review.
* ``apps/cockpit/src/styles/tokens.css`` — what the build pipeline
  actually ships.

When Claude (W307) or the operator edits one, the other must be
updated in the same commit. This test fails loudly if they diverge.

The test is intentionally tolerant about formatting (hex casing,
rgba whitespace) but strict about values.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = REPO_ROOT / "design-system" / "tars" / "MASTER.md"
TOKENS_CSS_PATH = REPO_ROOT / "apps" / "cockpit" / "src" / "styles" / "tokens.css"

# Token → expected canonical value. Values are normalised (lowercase
# hex, no whitespace inside rgba()) before comparison so reformatting
# doesn't trigger a false positive.
#
# W308 step 1 updates (W307 verdict applied):
#   * --color-ink-3 promoted #5c5a52 → #8a867b (WCAG AA on bg-1).
#   * --cta-text-on-accent added (#000000) — hard rule, 9.62:1 AAA.
EXPECTED_TOKENS: dict[str, str] = {
    "--color-bg-0": "#000000",
    "--color-bg-1": "#0b0b10",
    "--color-bg-2": "#14141b",
    "--color-ink": "#f5f5f0",
    "--color-ink-2": "#a09e96",
    "--color-ink-3": "#8a867b",
    "--color-line": "rgba(245,245,240,0.06)",
    "--color-line-strong": "rgba(245,245,240,0.12)",
    "--color-line-hot": "rgba(202,138,4,0.32)",
    "--color-accent": "#ca8a04",
    "--color-accent-soft": "rgba(202,138,4,0.55)",
    "--color-accent-deep": "rgba(202,138,4,0.12)",
    "--cta-text-on-accent": "#000000",
    "--color-hud": "#00ffff",
    "--color-hud-soft": "rgba(0,255,255,0.32)",
    "--color-alert": "#ef4444",
    "--color-success": "#34d399",
}

# Font families that must appear in both files (case-insensitive).
EXPECTED_FONTS: tuple[str, ...] = ("Share Tech Mono", "Fira Code")

# W308 step 1: MASTER §6/§7 must document the cockpit motion budget
# explicitly. The smoke test enforces the presence of the token in
# both files (value is operator-tunable later).
MOTION_BUDGET_TOKEN = "--motion-budget-max"


def _normalise(value: str) -> str:
    """Lowercase hex, strip whitespace inside ``rgba()``."""
    value = value.strip().lower()
    value = re.sub(r"\s+", "", value)
    return value


def _read(path: Path) -> str:
    if not path.exists():
        pytest.fail(f"missing file: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def _extract_css_token(css: str, token: str) -> str | None:
    """Return the normalised value assigned to ``--token`` in *css*.

    Picks the **first** declaration (the ``:root`` block); media-query
    overrides (e.g. ``prefers-reduced-motion``) live below it and are
    ignored on purpose.
    """
    match = re.search(
        rf"^\s*{re.escape(token)}\s*:\s*([^;]+);",
        css,
        flags=re.MULTILINE,
    )
    if not match:
        return None
    return _normalise(match.group(1))


def _extract_master_token(md: str, token: str) -> str | None:
    """Pull a token value out of MASTER.md.

    MASTER lists palette tokens in a markdown table where the first
    column wraps the token in single backticks and the second column
    holds the value (also backticked). The value may be a hex literal
    or an ``rgba(...)`` expression.
    """
    pattern = (
        rf"\|\s*`{re.escape(token)}`\s*\|\s*`([^`]+)`"
    )
    match = re.search(pattern, md)
    if not match:
        return None
    return _normalise(match.group(1))


def test_palette_tokens_match_master() -> None:
    """Every palette token in tokens.css matches MASTER.md and the
    canonical value in :data:`EXPECTED_TOKENS`."""
    css = _read(TOKENS_CSS_PATH)
    md = _read(MASTER_PATH)

    mismatches: list[str] = []
    for token, canonical in EXPECTED_TOKENS.items():
        canonical_norm = _normalise(canonical)
        css_value = _extract_css_token(css, token)
        md_value = _extract_master_token(md, token)

        if css_value is None:
            mismatches.append(f"  {token}: missing in tokens.css")
            continue
        if md_value is None:
            mismatches.append(f"  {token}: missing in MASTER.md")
            continue
        if css_value != canonical_norm:
            mismatches.append(
                f"  {token}: tokens.css={css_value!r} "
                f"!= canonical={canonical_norm!r}"
            )
        if md_value != canonical_norm:
            mismatches.append(
                f"  {token}: MASTER.md={md_value!r} "
                f"!= canonical={canonical_norm!r}"
            )

    assert not mismatches, (
        "Cockpit design tokens drifted from MASTER.md. Update both "
        "files in the same commit and re-run.\n"
        + "\n".join(mismatches)
    )


def test_typography_families_present() -> None:
    """Both font families from MASTER §4 must be referenced in
    tokens.css (so the Vite bundle knows which fonts to pull)."""
    css = _read(TOKENS_CSS_PATH).lower()
    md = _read(MASTER_PATH).lower()

    missing: list[str] = []
    for family in EXPECTED_FONTS:
        needle = family.lower()
        if needle not in css:
            missing.append(f"  {family!r} missing from tokens.css")
        if needle not in md:
            missing.append(f"  {family!r} missing from MASTER.md")

    assert not missing, (
        "Required typography families are not in both files.\n"
        + "\n".join(missing)
    )


def test_tokens_css_has_reduced_motion_block() -> None:
    """MASTER §6 mandates a ``prefers-reduced-motion`` opt-out. The
    smoke test enforces that the override block exists; we don't try
    to validate every duration value, just that the contract is wired
    up."""
    css = _read(TOKENS_CSS_PATH)
    assert "prefers-reduced-motion: reduce" in css, (
        "tokens.css must include a @media (prefers-reduced-motion: "
        "reduce) override block — see MASTER §6/§7."
    )


def test_master_documents_motion_budget() -> None:
    """W308 step 1: ``--motion-budget-max`` is the codified version of
    MASTER §7's "1-2 key elements per view max" rule. Both files must
    reference it so future surfaces don't drift back to advisory-only
    language."""
    css = _read(TOKENS_CSS_PATH)
    md = _read(MASTER_PATH)
    missing: list[str] = []
    if MOTION_BUDGET_TOKEN not in css:
        missing.append(f"  {MOTION_BUDGET_TOKEN} missing from tokens.css")
    if MOTION_BUDGET_TOKEN not in md:
        missing.append(f"  {MOTION_BUDGET_TOKEN} missing from MASTER.md §7")
    assert not missing, "\n".join(missing)


def test_master_codifies_cta_text_on_accent_rule() -> None:
    """W308 step 1 (W307 verdict): the hard rule that text on
    ``--color-accent`` must be black is enforced by both the token
    (``--cta-text-on-accent``) and prose in MASTER §3 anti-patterns.
    The smoke test makes sure the prose stays there — a future editor
    cannot quietly delete the rule without breaking the build."""
    md = _read(MASTER_PATH)
    assert "--cta-text-on-accent" in md, (
        "MASTER §3 must document --cta-text-on-accent in the palette "
        "table (W307 verdict, hard rule)."
    )
    needle = (
        "never set `color: var(--color-ink)` on a background of "
        "`var(--color-accent)`"
    )
    assert needle in md, (
        "MASTER §3 anti-patterns must include the hand-rolled-gold-button "
        "warning (W307 verdict, hard rule)."
    )


def test_master_documents_hud_alpha_cap() -> None:
    """W308 step 1: usage cap for ``--color-hud`` raw must be documented
    in MASTER §3 — otherwise nothing stops a future surface from using
    raw `#00FFFF` at 1.0 alpha and turning the cockpit into a Tron arcade."""
    md = _read(MASTER_PATH)
    assert "--color-hud-alpha-cap" in md, (
        "MASTER §3 must reference --color-hud-alpha-cap (W308 step 1 docs)."
    )


def test_surface_marketing_motion_override_declared() -> None:
    """W307 verdict resolution (6231b34) — gap-fill after W308 step 2+3.

    Marketing-class surfaces (landing hero, brand pages, share cards)
    lift ``--motion-budget-max`` from the default 2 to 4 because the
    rotating-core hero scene IS the value prop. The override lives in
    ``apps/cockpit/src/styles/tokens.css`` as a ``.surface-marketing``
    selector and is documented in MASTER §7.

    Without enforcement, future agents will quietly drop the override
    when refactoring tokens.css; the marketing/cockpit split would be
    re-litigated at every wave."""
    css = _read(TOKENS_CSS_PATH)
    css_norm = re.sub(r"\s+", "", css)
    needles_css = (
        ".surface-marketing",
        "--motion-budget-max:4",
    )
    missing_css = [n for n in needles_css if n not in css_norm]
    assert not missing_css, (
        "tokens.css must declare `.surface-marketing { "
        "--motion-budget-max: 4; }` (W307 verdict resolution). "
        f"Missing: {missing_css}"
    )

    md = _read(MASTER_PATH)
    assert "surface-marketing" in md, (
        "MASTER §7 must document the .surface-marketing motion-budget "
        "override (W307 verdict resolution, gap-fill after step 2)."
    )


# ---------------------------------------------------------------------------
# W308 step 4 — post-Claude-review enforcement (PR #185)
# ---------------------------------------------------------------------------

HERO_HTML_PATH = REPO_ROOT / "apps" / "cockpit" / "hero.html"
COCKPIT_HTML_PATH = REPO_ROOT / "apps" / "cockpit" / "cockpit.html"


def test_hero_html_applies_surface_marketing_class() -> None:
    """W308 step 4 (Claude code review of PR #185).

    ``.surface-marketing { --motion-budget-max: 4; }`` is *declared* in
    tokens.css and *documented* in MASTER §7 — but the previous test
    only enforced authorship. If no surface ever applies the class, the
    override does nothing and the smoke test passes vacuously.

    The hero is the canonical marketing surface (live rail + rotating
    core + integrity score = several simultaneous motions). It MUST
    opt into the `.surface-marketing` budget; without the class, the
    `--motion-budget-max: 2` default applies via the cascade and the
    page silently overshoots the cockpit motion contract."""
    html = _read(HERO_HTML_PATH)
    # Apply at <html>, <body>, or <main> — any of the three is fine.
    if "surface-marketing" not in html:
        pytest.fail(
            "apps/cockpit/hero.html must apply the `.surface-marketing` "
            "class to <html>, <body>, or <main> so the W307 motion-budget "
            "override actually takes effect (Claude review of W308 step 3)."
        )


def test_phase_bar_size_token_declared_and_applied() -> None:
    """W308 step 4 (W307 verdict — Token diff row).

    ``--font-size-phase-bar: 11px`` token must:

    1. Be declared in tokens.css (not hardcoded into a single HTML).
    2. Be documented in MASTER §4 typography table.
    3. Be referenced by ``.phase-bar`` in cockpit.html (so the
       Share Tech Mono caps stay readable on Retina).

    The bar previously ran at 10px hardcoded; the W307 verdict
    explicitly called this out as a readability fail."""
    css = _read(TOKENS_CSS_PATH)
    md = _read(MASTER_PATH)
    cockpit = _read(COCKPIT_HTML_PATH)

    assert "--font-size-phase-bar" in css, (
        "tokens.css must declare --font-size-phase-bar (W307 verdict)."
    )
    # Token value sits within ~60 chars of the declaration name.
    css_window = css.split("--font-size-phase-bar", 1)[1][:60]
    assert "11px" in css_window, (
        "tokens.css --font-size-phase-bar must resolve to 11px "
        "(W307 verdict — Share Tech Mono falls apart at 10px)."
    )
    assert "--font-size-phase-bar" in md, (
        "MASTER §4 typography table must reference --font-size-phase-bar."
    )
    assert "var(--font-size-phase-bar)" in cockpit, (
        "apps/cockpit/cockpit.html .phase-bar must use "
        "var(--font-size-phase-bar) instead of a hardcoded 10px."
    )


def test_brief_item_stagger_animation_declared() -> None:
    """W308 step 4 (W307 verdict — Motion).

    The verdict reads: "Add transition-delay: calc(var(--i) * 60ms)
    so the four items cascade in." The cockpit's briefing card lists
    four actionable items that should reveal in sequence on enter;
    without the stagger they all hit at once and the visual hierarchy
    the verdict asks for collapses.

    Implementation accepts either the literal ``transition-delay``
    wording from the verdict or the equivalent ``animation-delay`` —
    transitions need a state change to fire, animations don't.
    Either path must reference ``var(--i)`` and a ``60ms`` cadence to
    demonstrate the per-item stagger is actually wired."""
    cockpit = _read(COCKPIT_HTML_PATH)
    cockpit_norm = re.sub(r"\s+", "", cockpit).lower()

    has_var_i = "var(--i" in cockpit_norm
    has_60ms = "60ms" in cockpit_norm
    has_delay = (
        "transition-delay:" in cockpit_norm
        or "animation-delay:" in cockpit_norm
        or "animation:briefin" in cockpit_norm
    )

    if not (has_var_i and has_60ms and has_delay):
        pytest.fail(
            "apps/cockpit/cockpit.html must implement the brief-item "
            "stagger via calc(var(--i) * 60ms) on transition-delay or "
            "animation-delay (W307 verdict — Motion). "
            f"present: var(--i)={has_var_i}, 60ms={has_60ms}, "
            f"delay-or-anim={has_delay}."
        )
