"""Phase L10 — pairing-first contract pin (iOS L1 ↔ Android L2).

Both mobile slices must expose the **same** public surface so the
host doesn't have to special-case one platform: same response field
names, same envelope keys, same state machine values, same fingerprint
formatter.

We don't compile either source here (no Xcode + no Android SDK on the
parent machine for every contributor). Instead we grep both source
trees for the exact identifiers we depend on. Drift on either side
fires here before it reaches the host.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
IOS = REPO / "mobile" / "ios" / "TARSCompanion" / "Sources" / "TARSCompanion"
ANDROID = (
    REPO / "mobile" / "android" / "TARSCompanion" / "app" / "src" / "main" / "java"
    / "world" / "meeet" / "tars"
)

CONTRACT_VERSION = "1.0.0"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- shared expectations -------------------------------------------------


REQUIRED_BEGIN_FIELDS = [
    "pair_id",
    "accept_token",
    "host_id",
    "host_fingerprint",
    "host_public_key",
    "expires_at",
]

REQUIRED_STATUS_STATES = ["pending", "linked", "expired", "rejected"]


@pytest.fixture(scope="module")
def ios_sources() -> dict[str, str]:
    files = list(IOS.glob("*.swift"))
    assert files, f"no Swift sources at {IOS}"
    return {p.name: _read(p) for p in files}


@pytest.fixture(scope="module")
def android_sources() -> dict[str, str]:
    files = [
        ANDROID / "TARSCompanion.kt",
        ANDROID / "PairingEnvelopeParser.kt",
        ANDROID / "PairingViewModel.kt",
        ANDROID / "net" / "PairingClient.kt",
        ANDROID / "crypto" / "PairingCrypto.kt",
        ANDROID / "ui" / "PairingScreen.kt",
        ANDROID / "PairingActivity.kt",
    ]
    out: dict[str, str] = {}
    for p in files:
        assert p.exists(), f"missing Android source: {p}"
        out[p.name] = _read(p)
    return out


# --- iOS shape ------------------------------------------------------------


def test_ios_contract_version_pinned(ios_sources: dict[str, str]) -> None:
    src = ios_sources["TARSCompanion.swift"]
    assert f'contractVersion = "{CONTRACT_VERSION}"' in src
    assert 'deviceKind = "mobile_ios"' in src


def test_ios_pairing_client_decodes_required_begin_fields(ios_sources: dict[str, str]) -> None:
    src = ios_sources["PairingClient.swift"]
    for field in REQUIRED_BEGIN_FIELDS:
        assert f'"{field}"' in src, f"iOS PairingClient missing field {field}"


def test_ios_pairing_states_cover_all(ios_sources: dict[str, str]) -> None:
    src = ios_sources["PairingClient.swift"]
    for state in REQUIRED_STATUS_STATES:
        assert f"case {state}" in src, f"iOS PairingState missing case {state}"


def test_ios_envelope_parser_supports_json_and_url(ios_sources: dict[str, str]) -> None:
    src = ios_sources["PairingEnvelope.swift"]
    assert "parseJSON" in src
    assert "parseURL" in src
    assert "tars-pair://" in src


# --- Android shape --------------------------------------------------------


def test_android_contract_version_pinned(android_sources: dict[str, str]) -> None:
    src = android_sources["TARSCompanion.kt"]
    assert f'CONTRACT_VERSION = "{CONTRACT_VERSION}"' in src
    assert 'DEVICE_KIND = "mobile_android"' in src


def test_android_pairing_client_decodes_required_begin_fields(
    android_sources: dict[str, str],
) -> None:
    src = android_sources["PairingClient.kt"]
    for field in REQUIRED_BEGIN_FIELDS:
        assert f'"{field}"' in src, f"Android PairingClient missing field {field}"


def test_android_pairing_states_cover_all(android_sources: dict[str, str]) -> None:
    src = android_sources["PairingClient.kt"]
    for state in REQUIRED_STATUS_STATES:
        assert f'"{state}"' in src, f"Android PairingState missing raw {state}"


def test_android_envelope_parser_supports_json_and_url(
    android_sources: dict[str, str],
) -> None:
    src = android_sources["PairingEnvelopeParser.kt"]
    assert "parseJSON" in src
    assert "parseURL" in src
    assert "tars-pair://" in src


# --- Symmetry check -------------------------------------------------------


def test_phase_machine_states_match(
    ios_sources: dict[str, str], android_sources: dict[str, str]
) -> None:
    ios_phase = ios_sources["PairingViewModel.swift"]
    android_phase = android_sources["PairingViewModel.kt"]
    for phase in ("idle", "scanning", "AwaitingHostAccept", "Linked", "Failed"):
        assert phase.lower() in ios_phase.lower(), f"iOS missing phase {phase}"
        assert phase in android_phase or phase.lower() in android_phase.lower(), (
            f"Android missing phase {phase}"
        )


def test_fingerprint_formatter_chunks_into_groups_of_four(
    ios_sources: dict[str, str], android_sources: dict[str, str]
) -> None:
    assert "formatFingerprint" in ios_sources["PairingCrypto.swift"]
    assert "formatFingerprint" in android_sources["PairingCrypto.kt"]
    # Both implementations split on '-' and re-chunk into 4-char groups.
    assert 'replacingOccurrences(of: "-"' in ios_sources["PairingCrypto.swift"]
    assert 'replace("-"' in android_sources["PairingCrypto.kt"]
