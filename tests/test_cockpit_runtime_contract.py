"""Runtime contract smoke tests for the W309 step 1 cockpit modules.

W309 step 1 wires the four MVP behaviors back into the cockpit shell
that W308 step 3 left static (mic + WebSocket + chat + TTS). The
runtime lives at ``apps/cockpit/src/runtime/`` as vanilla TypeScript
modules — no framework, no external dependencies beyond the browser
globals and what ``apps/cockpit/`` already pulls.

This file pins the **architecture contract** of those modules: which
imports each file is allowed to use, which backend endpoints each
file must reference, and that the shared boundary (api / ws) is
respected so a regression in one module can't silently leak
dependencies into another.

Why static-only and not e2e:
    * The end-to-end behavior needs a live ``tars-daemon`` + mic
      permission + ElevenLabs key — covered by the manual harness
      in ``docs/handoff/W309_FUNCTIONAL_RESTORE_BRIEF.md`` §4.
    * CI runs without those, but the shape of the modules is
      cheap to assert and catches the most common regression
      ("dev imported something from the wrong layer").

Pairs with ``tests/test_cockpit_tokens_sync.py`` (design drift) —
together they fence off both the visual and behavioral contracts
of the cockpit. Both must stay green for ``/qa`` to clear ship.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "apps" / "cockpit" / "src" / "runtime"
ENTRY_PATH = REPO_ROOT / "apps" / "cockpit" / "src" / "pages" / "cockpit-entry.ts"


# ----------------------------------------------------------------------
# Module presence
# ----------------------------------------------------------------------


def test_runtime_modules_present() -> None:
    """All five runtime modules brief §2.2 enumerates must exist."""

    expected = {"api.ts", "tauri.ts", "ws.ts", "voice.ts", "chat.ts"}
    actual = {p.name for p in RUNTIME_DIR.glob("*.ts")}
    missing = expected - actual
    assert not missing, (
        f"runtime/ missing files: {sorted(missing)} "
        f"(have: {sorted(actual)})"
    )


# ----------------------------------------------------------------------
# Per-module shape contracts
# ----------------------------------------------------------------------


def test_api_module_shape() -> None:
    """api.ts is the dependency root — exports DEFAULT_API_BASE and
    must not import anything else from runtime/."""

    src = (RUNTIME_DIR / "api.ts").read_text()
    assert "DEFAULT_API_BASE" in src, (
        "api.ts must export DEFAULT_API_BASE (the sidecar URL contract)"
    )
    assert "127.0.0.1:8765" in src, (
        "api.ts default must match the sidecar bind from serve.py"
    )
    assert "export class ApiError" in src, (
        "api.ts must export the ApiError class so callers can branch"
    )
    assert "export async function api" in src, (
        "api.ts must export the api() wrapper"
    )
    assert "export async function apiBinary" in src, (
        "api.ts must export apiBinary() for /api/voice/speak audio"
    )
    assert "vaultStatus" in src and "/api/vault/status" in src, (
        "api.ts must include the vault status hook (brief §3.5)"
    )
    # Independence: api.ts is the root of the runtime DAG.
    for sibling in ("ws", "voice", "chat", "tauri"):
        assert f'from "./{sibling}"' not in src, (
            f"api.ts must not import ./{sibling} (would invert the DAG)"
        )


def test_tauri_module_shape() -> None:
    """tauri.ts must guard __TAURI__ presence and stay no-op in browser."""

    src = (RUNTIME_DIR / "tauri.ts").read_text()
    assert "__TAURI__" in src, (
        "tauri.ts must detect the Tauri global"
    )
    assert "export function isTauri" in src, (
        "tauri.ts must export isTauri() so callers can branch"
    )
    assert "export async function invokeTauri" in src, (
        "tauri.ts must export invokeTauri() IPC wrapper"
    )
    # No SDK import — keeps bundle lean. Allow the name in comments;
    # ban only real `import ... from "@tauri-apps/..."` statements.
    assert 'from "@tauri-apps/' not in src and "from '@tauri-apps/" not in src, (
        "tauri.ts must not import the @tauri-apps SDK (bundle bloat)"
    )


def test_ws_module_shape() -> None:
    """ws.ts must implement reconnect, status bus, and target the
    correct sidecar endpoint."""

    src = (RUNTIME_DIR / "ws.ts").read_text()
    assert "/api/realtime" in src, (
        "ws.ts must target /api/realtime (web_extras/routers/realtime.py)"
    )
    assert "WebSocket" in src, "ws.ts must use the browser WebSocket"
    # Exponential backoff knobs.
    assert "BACKOFF_MIN_MS" in src and "BACKOFF_MAX_MS" in src, (
        "ws.ts must declare backoff bounds (brief §3.2)"
    )
    assert "30_000" in src or "30000" in src, (
        "ws.ts backoff cap must be 30s per brief §3.2"
    )
    # Status bus.
    assert "export type WsStatus" in src or "WsStatus" in src, (
        "ws.ts must export the WsStatus union for badge consumers"
    )
    assert "onStatus" in src, (
        "ws.ts must expose onStatus() for status badge subscribers"
    )
    # Operator override.
    assert "TARS_WS_URL" in src, (
        "ws.ts must honour the localStorage TARS_WS_URL override "
        "(brief §3.2)"
    )
    # Authority on close codes.
    assert "1000" in src and "4001" in src, (
        "ws.ts must distinguish clean (1000) from auth-fail (4001) closes"
    )


def test_voice_module_shape() -> None:
    """voice.ts must reference all three concerns: mic capture, TTS
    playback, persona state."""

    src = (RUNTIME_DIR / "voice.ts").read_text()
    # Mic.
    assert "navigator.mediaDevices" in src, (
        "voice.ts must reference navigator.mediaDevices (mic capture)"
    )
    assert "getUserMedia" in src, "voice.ts must call getUserMedia"
    # TTS.
    assert "/api/voice/speak" in src, (
        "voice.ts must POST /api/voice/speak for TTS"
    )
    assert "new Audio" in src, (
        "voice.ts must play TTS via new Audio() (single-track queue)"
    )
    assert "createObjectURL" in src and "revokeObjectURL" in src, (
        "voice.ts must use blob: URLs for audio and revoke them"
    )
    # Persona / health.
    assert "/api/voice/personas" in src, (
        "voice.ts must fetch /api/voice/personas on setup"
    )
    assert "/api/voice/health" in src, (
        "voice.ts must fetch /api/voice/health on setup"
    )
    # Boundary — voice depends on api only.
    assert 'from "./api"' in src, (
        "voice.ts must route HTTP through api.ts (no raw fetch())"
    )
    for sibling in ("ws", "chat", "tauri"):
        assert f'from "./{sibling}"' not in src, (
            f"voice.ts must not import ./{sibling} (keep modules narrow)"
        )


def test_chat_module_shape() -> None:
    """chat.ts must hit the three thread endpoints and parse SSE."""

    src = (RUNTIME_DIR / "chat.ts").read_text()
    # Endpoints.
    assert "/api/chat/threads" in src, (
        "chat.ts must call /api/chat/threads (create + list-via-id)"
    )
    # SSE parser markers.
    assert "text/event-stream" in src, (
        "chat.ts must accept text/event-stream (POST messages returns SSE)"
    )
    assert "getReader" in src and "TextDecoder" in src, (
        "chat.ts must stream-parse the SSE response body"
    )
    # Optimistic UI markers.
    assert '"sending"' in src and '"delivered"' in src and '"failed"' in src, (
        "chat.ts must carry the three message statuses (brief §3.4)"
    )
    # Boundary — chat depends on api only (SSE uses raw fetch but the
    # base URL still routes through getApiBase from api.ts).
    assert 'from "./api"' in src, (
        "chat.ts must route HTTP through api.ts"
    )
    for sibling in ("ws", "voice", "tauri"):
        assert f'from "./{sibling}"' not in src, (
            f"chat.ts must not import ./{sibling}"
        )


# ----------------------------------------------------------------------
# Entry wiring
# ----------------------------------------------------------------------


def test_cockpit_entry_wires_all_runtime_modules() -> None:
    """cockpit-entry.ts must import all 4 behavior modules and the
    vault hook, plus set up + tear down on the right events."""

    src = ENTRY_PATH.read_text()
    # Imports from runtime.
    for mod in ("api", "ws", "voice", "chat"):
        assert f'from "../runtime/{mod}"' in src, (
            f"cockpit-entry.ts must import ../runtime/{mod}"
        )
    # Setup + teardown lifecycle.
    assert "voice.setup" in src and "chat.setup" in src and ".setup(" in src, (
        "cockpit-entry.ts must invoke setup() on each runtime module"
    )
    assert "teardown" in src, (
        "cockpit-entry.ts must invoke teardown on unload"
    )
    assert "beforeunload" in src or "pagehide" in src, (
        "cockpit-entry.ts must register an unload listener"
    )
    # No innerHTML — defends against XSS via untrusted server content.
    assert ".innerHTML" not in src, (
        "cockpit-entry.ts must not assign innerHTML "
        "(use createElement + textContent for any server-derived content)"
    )


# ----------------------------------------------------------------------
# Bundle size budget (soft — only fires when the bundle exists locally)
# ----------------------------------------------------------------------


def _bundle_dir() -> Path:
    return REPO_ROOT / "apps" / "cockpit" / "dist" / "assets"


@pytest.mark.skipif(
    not (REPO_ROOT / "apps" / "cockpit" / "dist").exists(),
    reason="apps/cockpit/dist/ not built — run `pnpm --filter @tars/cockpit build` first",
)
def test_bundle_size_within_w309_cap() -> None:
    """Bundle stays under the brief §5 rollback cap (80 KB raw)."""

    assets = _bundle_dir()
    total = sum(p.stat().st_size for p in assets.glob("cockpit-*.js"))
    cap = 80 * 1024
    assert total <= cap, (
        f"cockpit bundle size {total} bytes exceeds W309 step-1 "
        f"rollback cap of {cap} bytes (brief §5)"
    )


@pytest.mark.skipif(
    not (REPO_ROOT / "apps" / "cockpit" / "dist").exists(),
    reason="apps/cockpit/dist/ not built — run `pnpm --filter @tars/cockpit build` first",
)
def test_bundle_size_gzipped_within_w309_cap() -> None:
    """Gzipped bundle stays under the brief §5 wire-cap (25 KB gz).

    Tightens the regression guard: the raw-byte cap is 3.5× the actual
    bundle, so a 2× regression there would still pass. The gzip cap is
    1.5× current usage — far more sensitive without being flaky.
    """

    import gzip

    assets = _bundle_dir()
    total_gz = 0
    for p in assets.glob("cockpit-*.js"):
        total_gz += len(gzip.compress(p.read_bytes(), compresslevel=9))
    cap = 25 * 1024
    assert total_gz <= cap, (
        f"cockpit gzipped bundle size {total_gz} bytes exceeds the "
        f"W309 step-1 wire-cap of {cap} bytes (brief §5)"
    )


# ----------------------------------------------------------------------
# Behavioural pin-ups added in response to Claude PR #187 review
# (READY_TO_MERGE_WITH_FOLLOWUPS) — each test maps 1:1 to a finding so
# a future agent who deletes the fix gets a red test that points
# straight at the bug-class.
# ----------------------------------------------------------------------


def test_ws_setup_is_idempotent() -> None:
    """setup() must guard against a second call leaking the prior
    WebSocket (Claude review #187 high-sev #1)."""

    src = (RUNTIME_DIR / "ws.ts").read_text()
    # The guard reads either the cached socket or a pending retry
    # timer before deciding to skip; if both are inspected, the
    # idempotency check is in place.
    assert "this.ws !== null" in src or "this.ws !==null" in src, (
        "ws.setup() must check this.ws before issuing a fresh connect "
        "(idempotency guard — Claude review #187)"
    )
    assert "this.retryTimer !== null" in src or "this.retryTimer !==null" in src, (
        "ws.setup() must also short-circuit while a retry is pending"
    )


def test_ws_open_handler_checks_wantopen() -> None:
    """The OPEN handler must close cleanly if teardown landed during
    CONNECTING (Claude review #187 medium #1)."""

    src = (RUNTIME_DIR / "ws.ts").read_text()
    # Look for the guard inside the open handler block. We don't try
    # to parse — just assert the comment + the close call are wired
    # together so a refactor doesn't accidentally drop the guard.
    assert "teardown_during_connect" in src, (
        "ws open handler must invoke ws.close(1000, 'teardown_during_connect') "
        "when wantOpen flipped false mid-handshake"
    )


def test_ws_manager_public_api_surface() -> None:
    """A rename of any of the four public methods cockpit-entry calls
    must fail loudly here, not silently downstream (Claude #187 test
    critique — "no test asserts WsManager exports the four methods")."""

    src = (RUNTIME_DIR / "ws.ts").read_text()
    # Class shape — method names are what cockpit-entry binds against.
    for name in ("setup(", "teardown(", "on(", "onStatus("):
        assert name in src, (
            f"WsManager must expose `{name}` — renaming it would break "
            "cockpit-entry.ts wiring silently in TS but still ship"
        )


def test_voice_ensure_mic_serialises_concurrent_calls() -> None:
    """Concurrent ensureMic() calls must share a single in-flight
    promise to avoid leaking MediaStream tracks (Claude review #187
    high-sev #2)."""

    src = (RUNTIME_DIR / "voice.ts").read_text()
    assert "micPromise" in src, (
        "voice.ts must cache the in-flight ensureMic() promise so a "
        "double-click before the permission prompt resolves doesn't "
        "open two getUserMedia() requests (Claude review #187)"
    )


def test_voice_detects_stale_mediastream() -> None:
    """ensureMic() must check stream liveness before returning the
    cache (Claude review #187 high-sev #3)."""

    src = (RUNTIME_DIR / "voice.ts").read_text()
    # Any one of the canonical signals is enough — the implementation
    # is allowed to evolve, but the *concept* of "stream went stale"
    # must be encoded somewhere in voice.ts.
    has_active_check = "stream.active" in src or "isStreamUsable" in src
    has_track_state = '"live"' in src or "readyState" in src
    assert has_active_check or has_track_state, (
        "voice.ts must detect a revoked-mid-session MediaStream "
        "(check `stream.active` or track `readyState === 'live'`)"
    )


def test_chat_sse_parser_accepts_crlf() -> None:
    """SSE parser must accept all three spec-permitted boundaries
    (Claude review #187 medium #2). A reverse proxy that normalises
    line endings would otherwise hang the stream."""

    src = (RUNTIME_DIR / "chat.ts").read_text()
    # We accept either an explicit \r\n\r\n indexOf or a regex split
    # that handles CR/CRLF. Don't pin the implementation strategy.
    handles_crlf = "\\r\\n\\r\\n" in src or "\\r\\n|\\r|\\n" in src
    assert handles_crlf, (
        "chat.ts SSE parser must handle \\r\\n\\r\\n in addition to "
        "\\n\\n (HTTP/2 proxies frequently rewrite line endings)"
    )


def test_chat_flushes_trailing_buffer_on_close() -> None:
    """A stream that closes without a final blank line must not
    silently drop the last frame (Claude review #187 medium #2 cont.)."""

    src = (RUNTIME_DIR / "chat.ts").read_text()
    # The fix-up flushes `buf` after the read loop terminates.
    # Look for either the decoder-flush idiom or a buf-trim check
    # outside the inner loop.
    assert "decoder.decode()" in src, (
        "chat.ts must call decoder.decode() after `done` to flush any "
        "remaining UTF-8 byte sequences"
    )


def test_vault_cta_link_uses_noreferrer() -> None:
    """External target=_blank links must include noreferrer (Claude
    review #187 medium #3 — defense-in-depth)."""

    src = ENTRY_PATH.read_text()
    assert '"noopener noreferrer"' in src or "'noopener noreferrer'" in src, (
        "cockpit-entry.ts external link.rel must include "
        "'noopener noreferrer' (tab-nabbing + referrer leak guard)"
    )


def test_voice_speak_guards_response_content_type() -> None:
    """playOne() must reject non-audio responses before piping bytes
    into <audio> (Claude review #187 low — JSON envelope on 200)."""

    src = (RUNTIME_DIR / "voice.ts").read_text()
    assert "audio/" in src and "content-type" in src.lower(), (
        "voice.ts must check the /api/voice/speak content-type starts "
        "with `audio/` before constructing an <audio> element"
    )


def test_api_error_constructor_handles_circular_detail() -> None:
    """ApiError must not throw inside its own super() call when
    detail contains a circular reference (Claude review #187 low)."""

    src = (RUNTIME_DIR / "api.ts").read_text()
    # Look for the try/catch wrapping JSON.stringify in the ctor.
    assert "JSON.stringify(detail)" in src, "api.ts must stringify detail"
    # Crude but effective: scan a window around the stringify call
    # for the surrounding try/catch.
    idx = src.find("JSON.stringify(detail)")
    window = src[max(0, idx - 200) : idx + 200]
    assert "try {" in window and "catch" in window, (
        "api.ts ApiError must wrap JSON.stringify(detail) in try/catch "
        "so a circular-ref detail doesn't throw inside the throw"
    )


def test_cockpit_entry_teardown_is_one_shot() -> None:
    """beforeunload + pagehide both fire on Tauri window close; the
    teardown chain must latch on first call (Claude review #187 low)."""

    src = ENTRY_PATH.read_text()
    assert "teardownRan" in src, (
        "cockpit-entry.ts must latch teardownAll() against double-fire "
        "from beforeunload + pagehide"
    )
