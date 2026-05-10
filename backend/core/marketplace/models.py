"""Dataclasses + ID helpers for the marketplace module (Wave 106).

Three records:

- :class:`Listing` -- one entry in the public registry. Carries the
  ``install_payload`` (URL or inline JSON) and discovery metadata
  (tags, category, price, ratings aggregate).
- :class:`InstalledItem` -- a Listing that the operator pulled into
  ``~/.tars/marketplace/installed/<id>/``. The path is recorded so
  uninstall can clean it up.
- :class:`Rating` -- one operator vote (1..5) + optional comment.
  The rater identity is an anonymous SHA-256 hash of the operator
  email so a single operator cannot game the aggregate by spamming
  votes (the store enforces uniqueness on ``(listing_id, rater)``).

All vocab strings (``LISTING_KINDS``, price constants) live at
module level so the registry / installer / ratings modules + the
HTTP router agree on the lexicon.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CONTRACT_VERSION = "1.0"


# Listing-kind enum -- picks the install pipeline.
KIND_PLAYBOOK = "playbook"
KIND_SKILL = "skill"
KIND_TEMPLATE = "template"
KIND_REPORT_TEMPLATE = "report_template"
LISTING_KINDS: tuple[str, ...] = (
    KIND_PLAYBOOK,
    KIND_SKILL,
    KIND_TEMPLATE,
    KIND_REPORT_TEMPLATE,
)


# Price tiers -- v0 only honours "free" but the field is on the wire
# for forward-compat with the v9.3 payouts work.
PRICE_FREE = "free"
PRICE_ONE_TIME = "one-time"
PRICE_SUBSCRIPTION = "subscription"
PRICE_TIERS: tuple[str, ...] = (PRICE_FREE, PRICE_ONE_TIME, PRICE_SUBSCRIPTION)


# ---------- ID helpers ------------------------------------------------------


def _short_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def new_listing_id() -> str:
    return _short_id("mlst")


def new_install_id() -> str:
    return _short_id("mins")


def new_rating_id() -> str:
    return _short_id("mrtg")


def anonymise_rater(email: str) -> str:
    """Return a stable anonymous rater hash from an email.

    SHA-256 with a fixed salt so the value can't be reverse-mapped
    without seeing the salt + the raw email together. Empty / None
    inputs collapse to ``"anonymous"`` so callers don't have to
    handle the unauthenticated case.
    """

    norm = (email or "").strip().lower()
    if not norm:
        return "anonymous"
    salted = f"tars-marketplace-v0:{norm}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()[:32]


# ---------- Listing ---------------------------------------------------------


@dataclass
class Listing:
    """One entry in the marketplace registry.

    ``install_payload`` is either a URL pointing at a JSON / zip
    artefact, or an inline JSON dict (for tiny things like a single
    playbook recipe). The installer normalises both.
    """

    id: str
    kind: str  # one of LISTING_KINDS
    name: str
    slug: str
    description: str = ""
    author_handle: str = ""
    author_url: str = ""
    version: str = "0.1.0"
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    install_payload: Any = None  # str (URL) or dict (inline)
    preview_url: str = ""
    ratings_count: int = 0
    ratings_avg: float = 0.0
    price: str = PRICE_FREE
    license: str = "MIT"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "author": {
                "handle": self.author_handle,
                "url": self.author_url or None,
            },
            "version": self.version,
            "tags": list(self.tags),
            "category": self.category,
            "install_payload": self.install_payload,
            "preview_url": self.preview_url or None,
            "ratings": {
                "count": self.ratings_count,
                "avg": round(float(self.ratings_avg or 0.0), 2),
            },
            "price": self.price,
            "license": self.license,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Listing":
        author = data.get("author") or {}
        if not isinstance(author, dict):
            author = {}
        ratings = data.get("ratings") or {}
        if not isinstance(ratings, dict):
            ratings = {}
        return cls(
            id=str(data.get("id") or new_listing_id()),
            kind=str(data.get("kind") or KIND_PLAYBOOK),
            name=str(data.get("name") or ""),
            slug=str(data.get("slug") or ""),
            description=str(data.get("description") or ""),
            author_handle=str(author.get("handle") or ""),
            author_url=str(author.get("url") or ""),
            version=str(data.get("version") or "0.1.0"),
            tags=list(data.get("tags") or []),
            category=str(data.get("category") or "general"),
            install_payload=data.get("install_payload"),
            preview_url=str(data.get("preview_url") or ""),
            ratings_count=int(ratings.get("count") or 0),
            ratings_avg=float(ratings.get("avg") or 0.0),
            price=str(data.get("price") or PRICE_FREE),
            license=str(data.get("license") or "MIT"),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
        )


# ---------- InstalledItem ---------------------------------------------------


@dataclass
class InstalledItem:
    """A Listing that has been pulled into the local install dir."""

    listing_id: str
    version: str
    installed_at: float = field(default_factory=time.time)
    installed_path: str = ""
    target: str = "personal"  # personal | workspace
    listing_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "version": self.version,
            "installed_at": self.installed_at,
            "installed_path": self.installed_path,
            "target": self.target,
            "listing_snapshot": dict(self.listing_snapshot),
        }


# ---------- Rating ----------------------------------------------------------


@dataclass
class Rating:
    """One operator rating for a listing."""

    id: str
    listing_id: str
    rater: str  # anonymised hash from anonymise_rater()
    score: int  # 1..5
    comment: str = ""
    rated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "listing_id": self.listing_id,
            "rater": self.rater,
            "score": self.score,
            "comment": self.comment,
            "rated_at": self.rated_at,
        }
