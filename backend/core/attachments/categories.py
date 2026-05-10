"""Wave 102 — file management categories.

Pre-built standard taxonomy + heuristic + LLM-driven auto
classification helpers. The catalogue is intentionally short
(eight slots) so the sidebar in /files stays scannable and
operators don't develop "category fatigue". Custom slugs are
allowed via the file management API; the sidebar shows them
underneath the standard list with a divider.

Public surface:

- :data:`STANDARD_CATEGORIES` — tuple of (slug, label, blurb)
  rendered by the FE sidebar.
- :func:`is_standard` — boolean check used by the router when
  deciding whether to allow rename / delete on a category.
- :func:`heuristic_category` — filename-extension based fallback
  used when the LLM autocategorise pipeline isn't enabled or
  returns an empty answer.
- :func:`auto_categorize` — async wrapper around the council
  LLM that returns one of the standard slugs given a filename
  and an extracted-text excerpt. Cost-gated by
  ``TARS_AUTO_CATEGORIZE_ENABLED=1`` so a desktop sidecar
  doesn't burn tokens by default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

DEFAULT_CATEGORY = "uncategorized"


@dataclass(frozen=True)
class CategoryDef:
    slug: str
    label: str
    blurb: str

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "label": self.label, "blurb": self.blurb}


# Order matters — the sidebar renders in this exact order so the
# operator's eye lands first on the buckets that B2B clients pile
# the most paper into (contracts, decks, reports).
STANDARD_CATEGORIES: tuple[CategoryDef, ...] = (
    CategoryDef("contracts",       "Contracts",       "LP agreements, term sheets, MSAs"),
    CategoryDef("decks",           "Decks",           "Pitch decks, board updates, all-hands"),
    CategoryDef("reports",         "Reports",         "Audit, KPI, monthly memos"),
    CategoryDef("research",        "Research",        "Papers, market data, briefings"),
    CategoryDef("legal",           "Legal",           "Privacy, ToS, NDAs, regulatory"),
    CategoryDef("correspondence",  "Correspondence",  "Emails saved as PDF, letters, memos"),
    CategoryDef("code",            "Code",            "Snippets, screenshots, diffs"),
    CategoryDef(DEFAULT_CATEGORY,  "Uncategorized",   "Files awaiting a home"),
)

_STANDARD_SLUGS: frozenset[str] = frozenset(c.slug for c in STANDARD_CATEGORIES)


def list_standard() -> list[dict[str, str]]:
    return [c.to_dict() for c in STANDARD_CATEGORIES]


def is_standard(slug: str | None) -> bool:
    if not slug:
        return False
    return slug in _STANDARD_SLUGS


# --- Heuristic ---------------------------------------------------------

# Extension → category. Conservative — anything not in the table
# falls back to ``uncategorized`` so the LLM auto-classifier gets a
# fair chance.
_EXTENSION_MAP: dict[str, str] = {
    # Contracts / signed paper
    "docx": "contracts",
    "doc":  "contracts",
    "rtf":  "contracts",
    # Reports / data dumps
    "csv":  "reports",
    "tsv":  "reports",
    "xlsx": "reports",
    "xls":  "reports",
    # Decks
    "pptx": "decks",
    "ppt":  "decks",
    "key":  "decks",
    # Research-ish
    "epub": "research",
    "mobi": "research",
    # Code
    "py":   "code",
    "ts":   "code",
    "tsx":  "code",
    "js":   "code",
    "jsx":  "code",
    "go":   "code",
    "rs":   "code",
    "java": "code",
    "rb":   "code",
    "c":    "code",
    "h":    "code",
    "cpp":  "code",
    "json": "code",
    "yml":  "code",
    "yaml": "code",
    "sh":   "code",
    "sql":  "code",
    "diff": "code",
    "patch": "code",
    "log":  "code",
    # Correspondence default
    "eml":  "correspondence",
    "msg":  "correspondence",
}


# Filename keyword → category. Cheap pre-LLM hints so even a
# .pdf or .md whose extension is ambiguous picks up a sensible
# bucket. First match wins; longest substrings checked first.
_KEYWORD_HINTS: tuple[tuple[str, str], ...] = (
    ("term-sheet",    "contracts"),
    ("term sheet",    "contracts"),
    ("agreement",     "contracts"),
    ("contract",      "contracts"),
    ("nda",           "legal"),
    ("privacy",       "legal"),
    ("compliance",    "legal"),
    ("regulatory",    "legal"),
    ("audit",         "reports"),
    ("monthly",       "reports"),
    ("quarterly",     "reports"),
    ("kpi",           "reports"),
    ("report",        "reports"),
    ("deck",          "decks"),
    ("pitch",         "decks"),
    ("board",         "decks"),
    ("memo",          "correspondence"),
    ("letter",        "correspondence"),
    ("email",         "correspondence"),
    ("research",      "research"),
    ("paper",         "research"),
    ("whitepaper",    "research"),
    ("snippet",       "code"),
    ("screenshot",    "code"),
)


def heuristic_category(filename: str | None, mime: str | None = None) -> str:
    """Pick a default category from filename + mime alone.

    Used by the upload pipeline when LLM auto-categorisation is
    disabled or returns nothing. Always returns one of the
    standard slugs so the sidebar bucket count stays consistent.
    """

    name = (filename or "").lower().strip()
    if name:
        # Keyword pass first — operator-meaningful labels beat extensions.
        for keyword, slug in _KEYWORD_HINTS:
            if keyword in name:
                return slug
        if "." in name:
            ext = name.rsplit(".", 1)[-1]
            slug = _EXTENSION_MAP.get(ext)
            if slug:
                return slug
    if mime:
        m = mime.lower()
        if m.startswith("image/"):
            return "code"  # screenshots / diagrams typically land here
        if m == "application/pdf":
            return DEFAULT_CATEGORY
        if m.startswith("text/"):
            return "research"
    return DEFAULT_CATEGORY


def is_auto_categorize_enabled() -> bool:
    return os.getenv("TARS_AUTO_CATEGORIZE_ENABLED", "0") in ("1", "true", "yes")


async def auto_categorize(
    *,
    filename: str | None,
    excerpt: str,
    mime: str | None = None,
) -> str:
    """Best-effort LLM classification.

    Returns one of :data:`STANDARD_CATEGORIES` slugs. Falls back to
    :func:`heuristic_category` when the council is unreachable or
    the gate is off — never raises so the file upload path stays
    resilient. Excerpt is truncated to 600 chars to keep token
    spend predictable.
    """

    if not is_auto_categorize_enabled():
        return heuristic_category(filename, mime)
    try:
        from backend.core.council.llm import classify_text  # type: ignore
    except Exception:
        return heuristic_category(filename, mime)
    excerpt_clip = (excerpt or "")[:600]
    try:
        slug = await classify_text(  # type: ignore[arg-type]
            text=excerpt_clip,
            filename=filename,
            mime=mime,
            allowed=tuple(c.slug for c in STANDARD_CATEGORIES),
        )
    except Exception:
        return heuristic_category(filename, mime)
    if isinstance(slug, str) and slug in _STANDARD_SLUGS:
        return slug
    return heuristic_category(filename, mime)


__all__ = [
    "DEFAULT_CATEGORY",
    "CategoryDef",
    "STANDARD_CATEGORIES",
    "list_standard",
    "is_standard",
    "heuristic_category",
    "auto_categorize",
    "is_auto_categorize_enabled",
]


def slugs() -> Iterable[str]:
    return _STANDARD_SLUGS
