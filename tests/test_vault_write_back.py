"""Vault write-back: ``set_secret`` / ``delete_secret``.

These were added so the OAuth consent flow can persist a freshly-minted
refresh token without going through "copy this string into your env"
operator gymnastics. The Keychain branch only runs on Darwin (we mock
the ``security`` CLI at the ``_to_keychain`` / ``_delete_keychain``
seam, identical pattern to the existing read-side tests in
``test_vault_and_llm_voice.py``).
"""

from __future__ import annotations

import os

import pytest

from backend.core.vault import (
    SecretRef,
    delete_secret,
    get_secret,
    set_secret,
)
from backend.core.vault import keychain as kc_module


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    """Wipe the test key from env so each case starts clean."""

    monkeypatch.delenv("TARS_TEST_VAULT_KEY", raising=False)
    yield
    monkeypatch.delenv("TARS_TEST_VAULT_KEY", raising=False)


# ============================================================ set_secret


def test_set_secret_writes_to_keychain_when_security_cli_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: Keychain available → SecretRef.source == 'keychain'."""

    captured: dict[str, object] = {}

    def fake_to_keychain(key, value, *, service, timeout_s):
        captured["key"] = key
        captured["value"] = value
        captured["service"] = service
        return True

    monkeypatch.setattr(kc_module, "_to_keychain", fake_to_keychain)

    ref = set_secret("TARS_TEST_VAULT_KEY", "my-refresh-token")
    assert isinstance(ref, SecretRef)
    assert ref.key == "TARS_TEST_VAULT_KEY"
    assert ref.source == "keychain"
    assert ref.available is True
    assert captured == {
        "key": "TARS_TEST_VAULT_KEY",
        "value": "my-refresh-token",
        "service": "tars",
    }


def test_set_secret_falls_back_to_env_when_keychain_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linux / Windows / Keychain-disabled → env fallback so the value
    is at least process-lifetime available."""

    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)

    ref = set_secret("TARS_TEST_VAULT_KEY", "my-token")
    assert ref.source == "env"
    assert ref.available is True
    assert os.environ.get("TARS_TEST_VAULT_KEY") == "my-token"


def test_set_secret_value_visible_via_get_secret_after_env_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: write through env fallback → read via get_secret
    sees the same value (env wins over Keychain on the read side)."""

    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)
    monkeypatch.setattr(kc_module, "_from_keychain", lambda *a, **k: None)

    set_secret("TARS_TEST_VAULT_KEY", "abc-123")
    assert get_secret("TARS_TEST_VAULT_KEY") == "abc-123"


def test_set_secret_strips_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OAuth providers occasionally hand back tokens with trailing
    newlines; the persistence layer normalises so reads are clean."""

    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: False)

    ref = set_secret("  TARS_TEST_VAULT_KEY  ", "  my-token  \n")
    assert ref.key == "TARS_TEST_VAULT_KEY"
    assert os.environ["TARS_TEST_VAULT_KEY"] == "my-token"


def test_set_secret_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="empty value"):
        set_secret("TARS_TEST_VAULT_KEY", "")
    with pytest.raises(ValueError, match="empty value"):
        set_secret("TARS_TEST_VAULT_KEY", "   ")


def test_set_secret_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        set_secret("", "value")
    with pytest.raises(ValueError, match="non-empty"):
        set_secret("   ", "value")


def test_set_secret_returns_keychain_even_when_env_value_already_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the operator had the value in env AND Keychain accepts the
    write, we report keychain — that's the durable destination."""

    monkeypatch.setenv("TARS_TEST_VAULT_KEY", "old-value")
    monkeypatch.setattr(kc_module, "_to_keychain", lambda *a, **k: True)

    ref = set_secret("TARS_TEST_VAULT_KEY", "new-value")
    assert ref.source == "keychain"


# ========================================================= delete_secret


def test_delete_secret_clears_env_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TARS_TEST_VAULT_KEY", "v")
    monkeypatch.setattr(kc_module, "_delete_keychain", lambda *a, **k: False)

    cleared = delete_secret("TARS_TEST_VAULT_KEY")
    assert cleared is True
    assert "TARS_TEST_VAULT_KEY" not in os.environ


def test_delete_secret_clears_keychain_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TARS_TEST_VAULT_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_delete_keychain", lambda *a, **k: True)

    assert delete_secret("TARS_TEST_VAULT_KEY") is True


def test_delete_secret_returns_false_when_key_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TARS_TEST_VAULT_KEY", raising=False)
    monkeypatch.setattr(kc_module, "_delete_keychain", lambda *a, **k: False)

    assert delete_secret("TARS_TEST_VAULT_KEY") is False


def test_delete_secret_clears_both_storages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A key set in BOTH env and Keychain gets cleared from both
    places — important so a later get_secret correctly returns None."""

    monkeypatch.setenv("TARS_TEST_VAULT_KEY", "v")
    monkeypatch.setattr(kc_module, "_delete_keychain", lambda *a, **k: True)

    assert delete_secret("TARS_TEST_VAULT_KEY") is True
    assert "TARS_TEST_VAULT_KEY" not in os.environ


def test_delete_secret_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        delete_secret("")


# ============================================== keychain CLI shape (no-op)


def test_to_keychain_returns_false_on_non_darwin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual ``security`` CLI is macOS-only; on other platforms
    the function returns False so the env fallback kicks in."""

    monkeypatch.setattr(kc_module.sys, "platform", "linux")
    assert kc_module._to_keychain("k", "v") is False


def test_delete_keychain_returns_false_on_non_darwin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kc_module.sys, "platform", "linux")
    assert kc_module._delete_keychain("k") is False
