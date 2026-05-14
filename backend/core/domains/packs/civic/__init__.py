"""Civic domain pack — W204.

Free, no-auth public-records access for every TARS user, regardless of
subscription tier. The whole point: AI that helps people understand
what their government is actually doing should be a baseline utility,
not a paid upsell.

Three starter actions:

- ``lookup_legislator`` — by name or zip, via OpenStates' free key-less
  public endpoint
- ``recent_votes`` — pull a legislator's last N votes (also OpenStates)
- ``court_case_search`` — federal court records via courtlistener.com's
  free /api/rest/v3/search/ (no key, rate-limited but generous)

All adapters fail gracefully: network down → structured error, never a
500. Council can chain these into a "what's my state legislature voting
on this week" answer.
"""

from .pack import CivicPack  # noqa: F401

__all__ = ["CivicPack"]
