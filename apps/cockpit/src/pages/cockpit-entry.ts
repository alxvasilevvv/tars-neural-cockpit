/*
 * Entry script for cockpit.html — operator shell (W307 visual contract +
 * W309 step 1 runtime restore + step 2 STT + persona picker).
 *
 * Module boundaries live in `../runtime/`:
 *   - api.ts    — typed fetch wrapper, vault status hook
 *   - tauri.ts  — IPC helpers (no-op outside Tauri)
 *   - ws.ts     — WebSocket manager, exponential backoff, event bus
 *   - voice.ts  — mic capture, TTS playback, persona state, STT upload
 *   - chat.ts   — thread send/load, optimistic strand append
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
  sttBtn: HTMLButtonElement | null;
  personaPicker: HTMLSelectElement | null;
  statusBar: HTMLElement | null;
  backendBadge: HTMLElement | null;
  voiceBadge: HTMLElement | null;
}

function pickRefs(): Refs {
  const statusBar = document.querySelector<HTMLElement>(".status-bar");
  return {
    briefing: document.querySelector<HTMLElement>(".briefing"),
    strand: document.querySelector<HTMLElement>(".strand"),
    input: document.querySelector<HTMLInputElement>(".input-bar input"),
    micBtn: document.querySelector<HTMLButtonElement>(".input-bar .mic"),
    sttBtn: document.querySelector<HTMLButtonElement>(".input-bar .stt-btn"),
    personaPicker: document.querySelector<HTMLSelectElement>("#persona-picker"),
    statusBar,
    backendBadge:
      statusBar?.querySelector<HTMLElement>('[data-cockpit="backend"]') ??
      null,
    voiceBadge:
      statusBar?.querySelector<HTMLElement>('[data-cockpit="voice-health"]') ??
      null,
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

let sttFlashTimer: ReturnType<typeof setTimeout> | null = null;

function flashVoiceStatus(refs: Refs, message: string, ms = 3000): void {
  if (!refs.voiceBadge) return;
  const prev = refs.voiceBadge.getAttribute("aria-label") ?? "";
  refs.voiceBadge.dataset.state = "degraded";
  refs.voiceBadge.setAttribute("aria-label", message);
  if (sttFlashTimer) clearTimeout(sttFlashTimer);
  sttFlashTimer = setTimeout(() => {
    applyVoiceHealth(refs);
    if (prev && !message.startsWith("Voice · STT failed")) {
      refs.voiceBadge?.setAttribute("aria-label", prev);
    }
    sttFlashTimer = null;
  }, ms);
}

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

function renderPersonaPicker(refs: Refs): void {
  const sel = refs.personaPicker;
  if (!sel) return;
  const personas = voice.getPersonas();
  if (personas.length === 0) {
    sel.hidden = true;
    clear(sel);
    return;
  }
  sel.hidden = false;
  clear(sel);
  for (const p of personas) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  }
  const current = voice.getCurrentPersona();
  if (current) sel.value = current.id;
}

function applyVault(status: VaultStatus): void {
  if (hasElevenLabsKey(status)) return;
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

function setSttButtonState(btn: HTMLButtonElement, recording: boolean): void {
  if (recording) {
    btn.dataset.state = "recording";
    btn.setAttribute("aria-label", "Stop mic");
    btn.setAttribute("aria-pressed", "true");
  } else {
    btn.dataset.state = "idle";
    btn.setAttribute("aria-label", "Start mic");
    btn.setAttribute("aria-pressed", "false");
  }
}

function bindStt(refs: Refs): void {
  if (!refs.sttBtn) return;
  refs.sttBtn.addEventListener("click", () => {
    const btn = refs.sttBtn!;
    if (voice.isRecording()) {
      btn.disabled = true;
      voice
        .stopRecording()
        .then((text) => {
          if (refs.input && text) {
            const prior = refs.input.value.trim();
            refs.input.value = prior ? `${prior} ${text}` : text;
          }
        })
        .catch((err) => {
          console.warn("[cockpit] STT failed", err);
          flashVoiceStatus(refs, "Voice · STT failed");
        })
        .finally(() => {
          btn.disabled = false;
          setSttButtonState(btn, false);
        });
      return;
    }

    voice
      .startRecording()
      .then(() => setSttButtonState(btn, true))
      .catch((err) => {
        console.warn("[cockpit] STT start failed", err);
        flashVoiceStatus(refs, "Voice · STT failed");
        setSttButtonState(btn, false);
      });
  });
}

function bindPersonaPicker(refs: Refs): void {
  if (!refs.personaPicker) return;
  refs.personaPicker.addEventListener("change", () => {
    const id = refs.personaPicker!.value;
    if (!voice.setPersona(id)) {
      console.warn("[cockpit] unknown persona", id);
    }
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
  bindStt(refs);
  bindPersonaPicker(refs);

  const unsubChat = chat.onChange(() => renderStrand(refs));
  const unsubWs = ws().onStatus((s) => applyWsStatus(refs, s));

  ws().setup(["chat", "voice", "awareness", "policy"]);

  const [voiceRes, chatRes, vaultRes] = await Promise.allSettled([
    voice.setup(),
    chat.setup(),
    vaultStatus(),
  ]);

  if (voiceRes.status === "rejected") {
    console.warn("[cockpit] voice.setup failed", voiceRes.reason);
  }
  renderPersonaPicker(refs);
  applyVoiceHealth(refs);

  if (chatRes.status === "rejected") {
    console.warn("[cockpit] chat.setup failed", chatRes.reason);
  }
  renderStrand(refs);

  if (vaultRes.status === "fulfilled") {
    applyVault(vaultRes.value);
  } else {
    console.warn("[cockpit] vault.status failed", vaultRes.reason);
  }

  let teardownRan = false;
  teardownAll = () => {
    if (teardownRan) return;
    teardownRan = true;
    if (sttFlashTimer) clearTimeout(sttFlashTimer);
    unsubChat();
    unsubWs();
    chat.teardown();
    voice.teardown();
    ws().teardown();
  };

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
