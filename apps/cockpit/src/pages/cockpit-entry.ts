/*
 * Entry script for cockpit.html — operator shell (W307 visual contract +
 * W309 step 1 runtime restore).
 *
 * Before W309 step 1 this file imported tokens.css and called it a
 * day; the cockpit shell was static markup. Step 1 wires the four
 * MVP behaviors back in (mic + WebSocket + chat + TTS) without
 * touching the W307 visual contract — every DOM hook is additive,
 * keyed off existing classes / aria roles, and degrades to the
 * static shell when the sidecar is unreachable.
 *
 * Module boundaries live in `../runtime/`:
 *   - api.ts    — typed fetch wrapper, vault status hook
 *   - tauri.ts  — IPC helpers (no-op outside Tauri)
 *   - ws.ts     — WebSocket manager, exponential backoff, event bus
 *   - voice.ts  — mic capture, TTS playback queue, persona state
 *   - chat.ts   — thread send/load, optimistic strand append
 *
 * Operator knobs (localStorage):
 *   - `TARS_API_URL` — base URL override (default http://127.0.0.1:8765)
 *   - `TARS_WS_URL`  — WS URL override (derived from API base by default)
 *
 * Note on DOM construction: all dynamic content is built via
 * `document.createElement` + `textContent`. We never assign
 * `innerHTML` from user / server data so the strand renderer cannot
 * inject markup even if a sidecar response somehow contained HTML.
 */

import "../styles/global.css";

import {
  vaultStatus,
  hasElevenLabsKey,
  type VaultStatus,
} from "../runtime/api";
import { ws, type WsStatus } from "../runtime/ws";
import * as voice from "../runtime/voice";
import * as chat from "../runtime/chat";

interface Refs {
  briefing: HTMLElement | null;
  strand: HTMLElement | null;
  input: HTMLInputElement | null;
  micBtn: HTMLButtonElement | null;
  statusBar: HTMLElement | null;
  backendBadge: HTMLElement | null;
  voiceBadge: HTMLElement | null;
}

function pickRefs(): Refs {
  const statusBar = document.querySelector<HTMLElement>(".status-bar");
  const badges = statusBar?.querySelectorAll<HTMLElement>("span") ?? [];
  return {
    briefing: document.querySelector<HTMLElement>(".briefing"),
    strand: document.querySelector<HTMLElement>(".strand"),
    input: document.querySelector<HTMLInputElement>(".input-bar input"),
    micBtn: document.querySelector<HTMLButtonElement>(".input-bar .mic"),
    statusBar,
    // First two spans are: "Backend · …" and "ElevenLabs · …".
    backendBadge: badges[0] ?? null,
    voiceBadge: badges[1] ?? null,
  };
}

/* ------------------------------------------------------------------- */
/* Strand renderer (DOM-safe — no innerHTML).                          */
/* ------------------------------------------------------------------- */

function clear(el: Element): void {
  while (el.firstChild) el.removeChild(el.firstChild);
}

function renderCollapsedStrand(strand: HTMLElement, count: number): void {
  clear(strand);
  strand.dataset.state = "collapsed";
  strand.setAttribute(
    "aria-label",
    "Conversation strand (collapsed)",
  );
  const label = document.createElement("span");
  label.className = "strand-collapsed-label";
  label.append("⌃ Conversation · ");
  const turns = document.createElement("span");
  turns.className = "strand-collapsed-count";
  turns.textContent = `${count} turn${count === 1 ? "" : "s"}`;
  label.appendChild(turns);
  strand.appendChild(label);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "strand-expand";
  btn.textContent = "Expand";
  strand.appendChild(btn);
}

function renderExpandedStrand(
  strand: HTMLElement,
  messages: ReturnType<typeof chat.getMessages>,
): void {
  strand.dataset.state = "expanded";
  strand.setAttribute("aria-label", "Conversation strand");

  // Ensure header + ordered list are present; reuse if already there
  // to avoid scroll-jump on incremental updates.
  let head = strand.querySelector<HTMLElement>(":scope > .strand-head");
  let list = strand.querySelector<HTMLOListElement>(":scope > .strand-list");
  if (!head || !list) {
    clear(strand);
    head = document.createElement("header");
    head.className = "strand-head";
    const title = document.createElement("span");
    title.textContent = "⌃ Conversation";
    const count = document.createElement("span");
    count.className = "strand-count";
    head.appendChild(title);
    head.appendChild(count);
    list = document.createElement("ol");
    list.className = "strand-list";
    strand.appendChild(head);
    strand.appendChild(list);
  }

  const countEl = head.querySelector(".strand-count");
  if (countEl) {
    countEl.textContent = `${messages.length} turn${messages.length === 1 ? "" : "s"}`;
  }

  // Re-render the whole list. Cheap for ≤20 messages; saves a diff.
  clear(list);
  for (const m of messages) {
    const li = document.createElement("li");
    li.className = "strand-msg";
    li.dataset.role = safeAttr(m.role);
    li.dataset.status = safeAttr(m.status ?? "delivered");

    const roleEl = document.createElement("span");
    roleEl.className = "strand-role";
    roleEl.textContent = m.role;
    li.appendChild(roleEl);

    const body = document.createElement("div");
    body.className = "strand-body";
    body.textContent = m.text || (m.role === "assistant" ? "…" : "");
    li.appendChild(body);

    list.appendChild(li);
  }

  // Keep latest message visible.
  list.scrollTop = list.scrollHeight;
}

function renderStrand(refs: Refs): void {
  if (!refs.strand) return;
  const messages = chat.getMessages();
  if (messages.length === 0) {
    refs.briefing?.removeAttribute("hidden");
    renderCollapsedStrand(refs.strand, 0);
    return;
  }
  refs.briefing?.setAttribute("hidden", "");
  renderExpandedStrand(refs.strand, messages);
}

function safeAttr(s: string): string {
  return s.replace(/[^a-zA-Z0-9_-]/g, "");
}

/* ------------------------------------------------------------------- */
/* Status indicators                                                   */
/* ------------------------------------------------------------------- */

function applyWsStatus(refs: Refs, s: WsStatus): void {
  if (!refs.backendBadge) return;
  refs.backendBadge.dataset.state =
    s === "open" ? "online" : s === "reconnecting" ? "degraded" : "offline";
  refs.backendBadge.setAttribute("aria-label", `Backend · ${s}`);
}

function applyVoiceHealth(refs: Refs): void {
  if (!refs.voiceBadge) return;
  const h = voice.getHealth();
  const ok = !!h?.any_available;
  refs.voiceBadge.dataset.state = ok ? "online" : "degraded";
  refs.voiceBadge.setAttribute(
    "aria-label",
    ok ? "Voice engines available" : "Voice degraded",
  );
}

function applyVault(status: VaultStatus): void {
  if (hasElevenLabsKey(status)) return;
  // Insert (or update) a lightweight CTA inline with the briefing —
  // brief §3.5 calls for "render the existing vault prompt" but the
  // new shell doesn't have one yet. Append a minimal CTA so the
  // operator sees the missing-key state without us reaching into
  // the visual contract.
  const briefing = document.querySelector(".briefing");
  if (!briefing) return;
  let cta = document.querySelector<HTMLElement>(".vault-cta");
  if (!cta) {
    cta = document.createElement("div");
    cta.className = "vault-cta";
    cta.setAttribute("role", "status");
    briefing.appendChild(cta);
  }
  clear(cta);
  const icon = document.createElement("span");
  icon.className = "vault-cta-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "⚠";
  const label = document.createElement("span");
  label.className = "vault-cta-label";
  label.textContent =
    "ElevenLabs key not in vault — TTS unavailable";
  const link = document.createElement("a");
  link.className = "vault-cta-link";
  link.href = "https://elevenlabs.io/";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Add key";
  cta.appendChild(icon);
  cta.appendChild(label);
  cta.appendChild(link);
}

/* ------------------------------------------------------------------- */
/* Input bindings                                                      */
/* ------------------------------------------------------------------- */

function bindInput(refs: Refs): void {
  if (!refs.input) return;
  refs.input.addEventListener("keydown", (evt) => {
    if (evt.key !== "Enter" || evt.shiftKey || evt.isComposing) return;
    evt.preventDefault();
    const text = refs.input!.value;
    if (!text.trim()) return;
    refs.input!.value = "";
    chat.send(text).catch((err) => console.warn("[cockpit] send failed", err));
  });
}

function bindMic(refs: Refs): void {
  if (!refs.micBtn) return;
  refs.micBtn.addEventListener("click", () => {
    if (voice.hasMic()) {
      voice.releaseMic();
      refs.micBtn!.setAttribute("aria-pressed", "false");
      refs.micBtn!.dataset.state = "off";
      return;
    }
    voice
      .ensureMic()
      .then(() => {
        refs.micBtn!.setAttribute("aria-pressed", "true");
        refs.micBtn!.dataset.state = "on";
      })
      .catch((err) => {
        console.warn("[cockpit] mic permission denied", err);
        refs.micBtn!.dataset.state = "denied";
      });
  });
}

/* ------------------------------------------------------------------- */
/* Boot                                                                */
/* ------------------------------------------------------------------- */

let teardownAll: (() => void) | null = null;

async function boot(): Promise<void> {
  const refs = pickRefs();

  bindInput(refs);
  bindMic(refs);

  // Subscribe to chat strand updates before kicking setup so the
  // initial empty render is the same code path as later updates.
  const unsubChat = chat.onChange(() => renderStrand(refs));

  // WS status → backend badge.
  const unsubWs = ws().onStatus((s) => applyWsStatus(refs, s));

  // Subscribe to commonly-needed topics. The realtime bus advertises
  // its full topic list in the `hello` envelope; we pick the slice
  // the MVP cockpit reacts to.
  ws().setup(["chat", "voice", "awareness", "policy"]);

  // Fire setup of voice + chat in parallel. Vault status is a
  // separate fetch that's allowed to race.
  const [voiceRes, chatRes, vaultRes] = await Promise.allSettled([
    voice.setup(),
    chat.setup(),
    vaultStatus(),
  ]);

  if (voiceRes.status === "rejected") {
    console.warn("[cockpit] voice.setup failed", voiceRes.reason);
  }
  applyVoiceHealth(refs);

  if (chatRes.status === "rejected") {
    console.warn("[cockpit] chat.setup failed", chatRes.reason);
  }
  renderStrand(refs); // explicit first paint in case onChange already fired

  if (vaultRes.status === "fulfilled") {
    applyVault(vaultRes.value);
  } else {
    console.warn("[cockpit] vault.status failed", vaultRes.reason);
  }

  // One-shot teardown — both `beforeunload` and `pagehide` fire on
  // Tauri window close, and each individual module's teardown is
  // idempotent, but running the whole chain twice still churns
  // event-handler bookkeeping and double-aborts in-flight SSE for no
  // reason. Latch on first invocation.
  let teardownRan = false;
  teardownAll = () => {
    if (teardownRan) return;
    teardownRan = true;
    unsubChat();
    unsubWs();
    chat.teardown();
    voice.teardown();
    ws().teardown();
  };

  // Best-effort cleanup; Tauri + browser both fire `beforeunload` on
  // window close, and Tauri also fires `pagehide` for WebView reloads.
  window.addEventListener("beforeunload", () => {
    teardownAll?.();
  });
  window.addEventListener("pagehide", () => {
    teardownAll?.();
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    void boot();
  });
} else {
  void boot();
}
