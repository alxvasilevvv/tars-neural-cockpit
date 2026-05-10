"""TARS marketplace v0 (Wave 106).

In-process registry + browse + install for community-published
playbooks, skills, templates and report templates. Source-of-truth
is a JSON manifest fetched from a public GitHub raw URL (or a
bundled seed when the URL is unreachable -- which is the common
case during local dev / offline demos).

Persistence:
- Registry cache: ``~/.tars/marketplace/registry.json``
- Installed items: ``~/.tars/marketplace/installed.sqlite``
- Local ratings: ``~/.tars/marketplace/ratings.sqlite``

No payouts in v0 -- ratings are local-only and the listings are
tagged with a ``price`` field for forward-compat with v9.3.

Public surface:

- :mod:`.models`     -- :class:`Listing`, :class:`InstalledItem`,
  :class:`Rating` dataclasses + ID helpers.
- :mod:`.registry`   -- ``fetch_registry`` (with 1h cache) +
  bundled seed fallback.
- :mod:`.installer`  -- ``install`` / ``uninstall`` /
  ``list_installed``.
- :mod:`.ratings`    -- local-only ``submit_rating`` /
  ``get_aggregate``.
- :mod:`.seed`       -- 12 starter listings rebadged from
  ``playbooks/_workshop/*``.

Contract version: 1.0 (see ``docs/contracts/MARKETPLACE.md``).
"""

from __future__ import annotations

from .models import (
    CONTRACT_VERSION,
    KIND_PLAYBOOK,
    KIND_REPORT_TEMPLATE,
    KIND_SKILL,
    KIND_TEMPLATE,
    LISTING_KINDS,
    PRICE_FREE,
    PRICE_ONE_TIME,
    PRICE_SUBSCRIPTION,
    InstalledItem,
    Listing,
    Rating,
    anonymise_rater,
    new_install_id,
    new_listing_id,
    new_rating_id,
)

__all__ = [
    "CONTRACT_VERSION",
    "InstalledItem",
    "KIND_PLAYBOOK",
    "KIND_REPORT_TEMPLATE",
    "KIND_SKILL",
    "KIND_TEMPLATE",
    "LISTING_KINDS",
    "Listing",
    "PRICE_FREE",
    "PRICE_ONE_TIME",
    "PRICE_SUBSCRIPTION",
    "Rating",
    "anonymise_rater",
    "new_install_id",
    "new_listing_id",
    "new_rating_id",
]
