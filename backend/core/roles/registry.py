"""Role registry: built-in roles + custom-role persistence + active selection.

Storage shape (JSON, single-tenant — desktop is single-user):

    {
      "active_slug": "founder",
      "custom_roles": [
        {
          "slug": "custom-3a7c",
          "name": "Clinical psychologist",
          "description": "...",
          "backing_packs": ["business"],
          "overlay": "...",
          "color": "#22D3EE",
          "icon": "Stethoscope"
        }
      ]
    }

Default roles are *not* persisted; they're read from
``DEFAULT_ROLES``. The store only carries the operator's active
choice + their custom additions.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Iterable, Iterator

from .models import Role, RoleSlug
from .synthesis import synthesise_overlay


def _default_path() -> Path:
    env = os.getenv("TARS_ROLES_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".tars" / "roles.json"


# ─── built-in roles ───────────────────────────────────────────────────


def _founder_overlay() -> str:
    return synthesise_overlay(
        name="Founder",
        description=(
            "I run a startup. Daily brief from KPI + deals + calendar. "
            "I value momentum, focus, and shipping. I never want to be "
            "spammed with commentary; surface decisions, not opinions. "
            "Council on every send to a partner or investor."
        ),
        backing_packs=("entrepreneur", "business"),
    )


def _trader_overlay() -> str:
    return synthesise_overlay(
        name="Trader",
        description=(
            "I trade markets across exchanges. I prioritise risk over "
            "upside. I never want to act on stale data. I must see "
            "dispersion + contradictions across council voices before "
            "any size-up call."
        ),
        backing_packs=("traders",),
    )


def _researcher_overlay() -> str:
    return synthesise_overlay(
        name="Researcher",
        description=(
            "I'm a researcher. I value citation hygiene above speed. "
            "Every claim must trace to a source the operator can open. "
            "When summarising, name the strongest counter-paper."
        ),
        backing_packs=("science",),
    )


def _engineer_overlay() -> str:
    return synthesise_overlay(
        name="Engineer",
        description=(
            "I build software. I prioritise correctness, clarity, and "
            "tests. Repos are indexed; PR review queue is a priority. "
            "I never want generated code that ignores the surrounding "
            "stack — match the existing patterns first."
        ),
        backing_packs=("science",),
    )


def _marketer_overlay() -> str:
    return synthesise_overlay(
        name="Marketer",
        description=(
            "I run growth + outreach. Voice + cadence matter. I never "
            "want spam. I value qualified outreach over volume. "
            "Engagement signals across channels feed the next move."
        ),
        backing_packs=("entrepreneur",),
    )


def _operator_overlay() -> str:
    return synthesise_overlay(
        name="Operator",
        description=(
            "I'm a generalist with a full cockpit. I value coverage "
            "over depth. I want one cross-domain brief per day with "
            "the most consequential signal from each pack."
        ),
        backing_packs=("traders", "entrepreneur", "science", "business"),
    )


DEFAULT_ROLES: tuple[Role, ...] = (
    Role(
        slug="founder",
        name="Founder / CEO",
        description="Daily brief from KPI + deals + calendar. Council on every send.",
        backing_packs=("entrepreneur", "business"),
        overlay=_founder_overlay(),
        color="#6366F1",
        icon="Crown",
    ),
    Role(
        slug="trader",
        name="Trader",
        description="Markets, signals, risk. Live across exchanges.",
        backing_packs=("traders",),
        overlay=_trader_overlay(),
        color="#8B5CF6",
        icon="TrendingUp",
    ),
    Role(
        slug="researcher",
        name="Researcher",
        description="arXiv-aware. Citation-graph across your projects.",
        backing_packs=("science",),
        overlay=_researcher_overlay(),
        color="#06B6D4",
        icon="FlaskConical",
    ),
    Role(
        slug="marketer",
        name="Marketer",
        description="Outreach drafts in your voice. Engagement signals across channels.",
        backing_packs=("entrepreneur",),
        overlay=_marketer_overlay(),
        color="#A78BFA",
        icon="Megaphone",
    ),
    Role(
        slug="engineer",
        name="Engineer",
        description="Repos indexed. PR review queue. Code RAG over your stack.",
        backing_packs=("science",),
        overlay=_engineer_overlay(),
        color="#34D399",
        icon="Code",
    ),
    Role(
        slug="operator",
        name="Operator",
        description="Generalist — full cockpit, all packs. Default if you skip.",
        backing_packs=("traders", "entrepreneur", "science", "business"),
        overlay=_operator_overlay(),
        color="#F59E0B",
        icon="Briefcase",
    ),
)


_DEFAULT_BY_SLUG: dict[RoleSlug, Role] = {r.slug: r for r in DEFAULT_ROLES}


def default_roles() -> tuple[Role, ...]:
    return DEFAULT_ROLES


# ─── persistent store ─────────────────────────────────────────────────


class _RoleStore:
    """Thread-safe single-file JSON store."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or _default_path()).resolve()
        self._lock = threading.RLock()

    def _read_raw(self) -> dict[str, object]:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_raw(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)

    # state accessors -------------------------------------------------

    def active_slug(self) -> RoleSlug | None:
        with self._lock:
            data = self._read_raw()
            slug = data.get("active_slug")
            return slug if isinstance(slug, str) and slug else None

    def set_active(self, slug: RoleSlug) -> None:
        with self._lock:
            data = self._read_raw()
            data["active_slug"] = slug
            data["active_at"] = time.time()
            self._write_raw(data)

    def custom_records(self) -> list[dict[str, object]]:
        with self._lock:
            data = self._read_raw()
            raw = data.get("custom_roles") or []
            if not isinstance(raw, list):
                return []
            return [r for r in raw if isinstance(r, dict)]

    def add_custom(self, record: dict[str, object]) -> None:
        with self._lock:
            data = self._read_raw()
            customs = data.get("custom_roles")
            if not isinstance(customs, list):
                customs = []
            customs = [r for r in customs if r.get("slug") != record.get("slug")]
            customs.append(record)
            data["custom_roles"] = customs
            self._write_raw(data)

    def remove_custom(self, slug: RoleSlug) -> bool:
        with self._lock:
            data = self._read_raw()
            customs = data.get("custom_roles")
            if not isinstance(customs, list):
                return False
            before = len(customs)
            after = [r for r in customs if r.get("slug") != slug]
            if len(after) == before:
                return False
            data["custom_roles"] = after
            # If we removed the active slug, fall back to None.
            if data.get("active_slug") == slug:
                data["active_slug"] = None
            self._write_raw(data)
            return True


_singleton: _RoleStore | None = None
_singleton_lock = threading.Lock()


def _store() -> _RoleStore:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = _RoleStore()
        return _singleton


def reset_store_for_tests(path: Path | None = None) -> _RoleStore:
    global _singleton
    with _singleton_lock:
        _singleton = _RoleStore(path=path)
    return _singleton


# ─── public API ───────────────────────────────────────────────────────


def list_roles() -> list[Role]:
    """Default + persisted custom roles (custom roles last)."""

    out: list[Role] = list(DEFAULT_ROLES)
    for rec in _store().custom_records():
        try:
            out.append(_record_to_role(rec))
        except (KeyError, TypeError):
            # Skip malformed records rather than crashing the registry.
            continue
    return out


def get_role(slug: RoleSlug) -> Role | None:
    if slug in _DEFAULT_BY_SLUG:
        return _DEFAULT_BY_SLUG[slug]
    for rec in _store().custom_records():
        if rec.get("slug") == slug:
            try:
                return _record_to_role(rec)
            except (KeyError, TypeError):
                return None
    return None


def get_active_role() -> Role | None:
    slug = _store().active_slug()
    if not slug:
        return None
    return get_role(slug)


def set_active_role(slug: RoleSlug) -> Role:
    """Activate ``slug``. Raises ``KeyError`` if unknown."""

    role = get_role(slug)
    if role is None:
        raise KeyError(f"unknown role: {slug!r}")
    _store().set_active(slug)
    return role


def create_custom_role(
    *,
    name: str,
    description: str,
    backing_packs: Iterable[str] = (),
    samples: Iterable[str] | None = None,
    color: str = "#22D3EE",
    icon: str = "Sparkles",
) -> Role:
    """Synthesise + persist a custom role. Returns the resolved :class:`Role`.

    The slug is ``custom-<8 hex chars>``; collisions are extraordinarily
    unlikely but we still re-try on the off chance.
    """

    if not name.strip():
        raise ValueError("role name must be non-empty")
    overlay = synthesise_overlay(
        name=name,
        description=description,
        backing_packs=tuple(backing_packs),
        samples=tuple(samples or ()),
    )
    slug = _mint_custom_slug()
    record = {
        "slug": slug,
        "name": name.strip(),
        "description": description.strip(),
        "backing_packs": list(backing_packs),
        "overlay": overlay,
        "custom": True,
        "color": color,
        "icon": icon,
    }
    _store().add_custom(record)
    return _record_to_role(record)


def delete_custom_role(slug: RoleSlug) -> bool:
    """Remove a custom role. Default roles cannot be deleted."""

    if slug in _DEFAULT_BY_SLUG:
        raise ValueError(f"cannot delete built-in role {slug!r}")
    return _store().remove_custom(slug)


# ─── helpers ──────────────────────────────────────────────────────────


def _record_to_role(rec: dict[str, object]) -> Role:
    return Role(
        slug=str(rec["slug"]),
        name=str(rec["name"]),
        description=str(rec.get("description", "")),
        backing_packs=tuple(str(p) for p in (rec.get("backing_packs") or [])),
        overlay=str(rec.get("overlay", "")),
        custom=bool(rec.get("custom", True)),
        color=str(rec.get("color", "#22D3EE")),
        icon=str(rec.get("icon", "Sparkles")),
    )


def _mint_custom_slug() -> str:
    for _ in range(8):
        candidate = "custom-" + secrets.token_hex(4)
        if get_role(candidate) is None:
            return candidate
    # Astronomically unlikely to land here; fall back to a longer slug.
    return "custom-" + secrets.token_hex(12)


def _iter_role_slugs() -> Iterator[RoleSlug]:
    for r in DEFAULT_ROLES:
        yield r.slug
    for rec in _store().custom_records():
        slug = rec.get("slug")
        if isinstance(slug, str):
            yield slug
