"""Civic pack awareness sources — config-only.

The civic pack is read-only/pull-only: every action is an explicit
operator request. No background polling, no webhooks, no scheduled
fetch. This file exists so the pack matches the DomainPack ABC and
the cockpit knows there's nothing to subscribe to.
"""

from __future__ import annotations

from ...base import AwarenessSource

SOURCES: tuple[AwarenessSource, ...] = ()
