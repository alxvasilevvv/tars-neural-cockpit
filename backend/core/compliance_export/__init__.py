"""Audit-grade compliance export bundles (Wave 104).

Single-command export tarball every B2B accountant / auditor will
accept. Bundles the complete TARS data trail across receipts,
cohorts, connectors, HIL, outreach, files, wallet, org, playbooks,
agents, and webhooks — with cryptographic chain verification proof
and ed25519 signature over the manifest.

Public surface:

- :mod:`.bundler`  — :func:`build_bundle` -> tar.gz at
  ``~/.tars/exports/audit-<timestamp>.tar.gz``.
- :mod:`.verifier` — :func:`verify_bundle` (auditors run independently).
- :mod:`.gdpr`     — :func:`export_user_data` (Article 15 right of access).
- :mod:`.redaction`— optional PII redaction layer for external auditors.

Contract version: 1.0 (see ``docs/contracts/COMPLIANCE_EXPORT.md``).
"""

from __future__ import annotations

from .bundler import (
    Bundle,
    DEFAULT_SCOPE,
    SCOPE_CATEGORIES,
    build_bundle,
    list_bundles,
)
from .gdpr import export_user_data
from .redaction import redact_pii
from .verifier import verify_bundle


CONTRACT_VERSION = "1.0"


__all__ = [
    "Bundle",
    "CONTRACT_VERSION",
    "DEFAULT_SCOPE",
    "SCOPE_CATEGORIES",
    "build_bundle",
    "export_user_data",
    "list_bundles",
    "redact_pii",
    "verify_bundle",
]
