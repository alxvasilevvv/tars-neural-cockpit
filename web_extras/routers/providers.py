"""HTTP surface for the Cockpit "Models switcher" (W237).

Exposes the inline ``PRICING`` table from
``backend.core.metering.recorder`` as a list of switchable model
options, plus a one-click "set active" endpoint that persists to
``~/.tars/active_model``.

Endpoints:

- ``GET /api/providers/list`` — array of model rows
  (id, label, provider, in/out rates, context window, available,
  active, tags).
- ``GET /api/providers/active`` — current active ``{model_id, label}``.
- ``POST /api/providers/set_active`` — body ``{model_id}`` →
  persists + returns ``{ok, active}``.

Availability is computed from env: a model with provider
``anthropic`` is ``available`` iff ``ANTHROPIC_API_KEY`` is set,
etc. The active model defaults to env ``TARS_DEFAULT_MODEL`` (or
the first available row) and can be overridden by the persisted
file. This router never mutates env — the file is the single
source of truth for the active selection.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.metering.recorder import PRICING


router = APIRouter(prefix="/api/providers", tags=["providers"])


# -- persistence -------------------------------------------------------

def _active_model_path() -> Path:
    raw = os.environ.get("TARS_ACTIVE_MODEL_PATH") or "~/.tars/active_model"
    return Path(os.path.expanduser(raw))


def _read_persisted_active() -> str | None:
    p = _active_model_path()
    try:
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            return v or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _write_persisted_active(model_id: str) -> None:
    p = _active_model_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(model_id.strip(), encoding="utf-8")


# -- catalog -----------------------------------------------------------

# Per-model human label + curated tags. Wildcard entries
# (``openrouter:*``, ``local:*``) and pure ``tars-local-v1`` are
# filtered out of the public catalog; those are handled inline by
# the metering layer, not as a user-selectable row.
_CATALOG: dict[str, dict[str, Any]] = {
    "anthropic:claude-sonnet-4-6": {
        "label": "Claude Sonnet 4.6",
        "context_window": 200000,
        "tags": ["recommended", "smart", "balanced"],
    },
    "anthropic:claude-opus-4-6": {
        "label": "Claude Opus 4.6",
        "context_window": 200000,
        "tags": ["smart", "expensive"],
    },
    "anthropic:claude-3-5-sonnet": {
        "label": "Claude 3.5 Sonnet",
        "context_window": 200000,
        "tags": ["smart", "balanced"],
    },
    "anthropic:claude-3-5-haiku": {
        "label": "Claude 3.5 Haiku",
        "context_window": 200000,
        "tags": ["fast", "cheap"],
    },
    "openai:gpt-4o": {
        "label": "GPT-4o",
        "context_window": 128000,
        "tags": ["smart", "balanced"],
    },
    "openai:gpt-4o-mini": {
        "label": "GPT-4o mini",
        "context_window": 128000,
        "tags": ["fast", "cheap"],
    },
    "openai:gpt-4.1": {
        "label": "GPT-4.1",
        "context_window": 1000000,
        "tags": ["smart", "long-context"],
    },
    "google:gemini-1.5-pro": {
        "label": "Gemini 1.5 Pro",
        "context_window": 2000000,
        "tags": ["smart", "long-context"],
    },
    "google:gemini-1.5-flash": {
        "label": "Gemini 1.5 Flash",
        "context_window": 1000000,
        "tags": ["fast", "cheap"],
    },
}


_PROVIDER_ENV_KEY: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def _is_available(provider: str) -> bool:
    key = _PROVIDER_ENV_KEY.get(provider.lower())
    if not key:
        # local providers (``tars-local-v1`` etc.) are always available.
        return True
    return bool(os.environ.get(key, "").strip())


def _build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model_id, meta in _CATALOG.items():
        price = PRICING.get(model_id)
        if not price:
            continue
        if "in_per_1k" not in price or "out_per_1k" not in price:
            continue
        provider = model_id.split(":", 1)[0] if ":" in model_id else "local"
        rows.append(
            {
                "id": model_id,
                "label": meta.get("label", model_id),
                "provider": provider,
                "in_per_1k_usd": float(price["in_per_1k"]),
                "out_per_1k_usd": float(price["out_per_1k"]),
                "context_window": int(meta.get("context_window") or 0),
                "available": _is_available(provider),
                "active": False,
                "tags": list(meta.get("tags") or []),
            }
        )
    return rows


def _resolve_active(rows: list[dict[str, Any]]) -> str:
    """Pick the active model id.

    Order:
        1. Persisted ``~/.tars/active_model`` if id is in catalog.
        2. ``TARS_DEFAULT_MODEL`` env if in catalog.
        3. First ``available`` row.
        4. First row, regardless of availability.
        5. Empty string (no catalog rows -- defensive).
    """

    catalog_ids = {r["id"] for r in rows}
    persisted = _read_persisted_active()
    if persisted and persisted in catalog_ids:
        return persisted
    env_default = (os.environ.get("TARS_DEFAULT_MODEL") or "").strip()
    if env_default and env_default in catalog_ids:
        return env_default
    for r in rows:
        if r.get("available"):
            return r["id"]
    return rows[0]["id"] if rows else ""


# -- endpoints ---------------------------------------------------------

@router.get("/list")
async def list_models() -> dict[str, Any]:
    """Return all switchable models + pricing + availability + active flag."""

    rows = _build_rows()
    active = _resolve_active(rows)
    for r in rows:
        r["active"] = r["id"] == active
    return {"ok": True, "active": active, "models": rows}


@router.get("/active")
async def get_active() -> dict[str, Any]:
    """Return the currently-active model id + human label."""

    rows = _build_rows()
    active = _resolve_active(rows)
    label = active
    for r in rows:
        if r["id"] == active:
            label = r["label"]
            break
    return {"ok": True, "model_id": active, "label": label}


class _SetActiveBody(BaseModel):
    model_id: str


@router.post("/set_active")
async def set_active(body: _SetActiveBody) -> dict[str, Any]:
    """Persist the new active model id to ``~/.tars/active_model``.

    Rejects unknown ids with 400. The router never validates
    availability -- operators may want to pre-set a model before
    pasting the API key, and the chat orchestrator already errors
    cleanly when the provider has no credentials.
    """

    rows = _build_rows()
    catalog_ids = {r["id"] for r in rows}
    model_id = (body.model_id or "").strip()
    if not model_id or model_id not in catalog_ids:
        raise HTTPException(
            status_code=400,
            detail=f"unknown model_id: {model_id!r}",
        )
    try:
        _write_persisted_active(model_id)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"persist failed: {exc!r}",
        )
    return {"ok": True, "active": model_id}
