/*
 * runtime/voice.ts — mic capture + TTS playback + persona state
 * (W309 step 1, brief §3.3).
 *
 * Three concerns share one module at MVP scale — each is small,
 * each ties to the same backend surface (`/api/voice/*`), and
 * splitting them would force three setup/teardown plumbings in
 * `cockpit-entry.ts` for no benefit.
 *
 * Mic capture:
 *   `ensureMic()` requests `navigator.mediaDevices.getUserMedia({audio:true})`
 *   on first user gesture (per browser autoplay/permission rules).
 *   The resulting `MediaStream` is held for the cockpit session and
 *   released on `teardown()` or explicit `releaseMic()`. We don't
 *   pipe it anywhere yet — STT upload (`/api/voice/transcribe`) is
 *   a W310+ concern; W309 step 1 only proves the permission flow
 *   and stream handle.
 *
 * TTS playback:
 *   `speak(text, {personaId?})` POSTs `/api/voice/speak`, gets back
 *   audio bytes (the FastAPI handler returns a raw `Response` with
 *   `x-tars-voice-*` headers), wraps in a `blob:` URL, and plays via
 *   `new Audio()`. Playback is serialised through a `Promise` chain
 *   so two clicks don't overlap. `media-src 'self' blob:` is already
 *   in the Tauri CSP.
 *
 * Persona state:
 *   On `setup()` we hit `/api/voice/personas` (fast — list lives in
 *   `backend.core.voice.personas` and is cached) plus `/api/voice/health`
 *   (engine availability snapshot). `getCurrentPersona()` returns the
 *   server's `default_persona_id` until the operator picks something
 *   else via `setPersona(id)`.
 */

import { api, apiBinary, ApiError } from "./api";

export interface Persona {
  id: string;
  name: string;
  character?: string;
  accent?: string;
  locale?: string;
}

export interface VoiceHealth {
  ok: boolean;
  engines: Record<string, boolean>;
  any_available: boolean;
  preferred_order: string[];
  stt?: unknown;
}

interface VoiceState {
  mic: MediaStream | null;
  currentPersona: Persona | null;
  personas: Persona[];
  health: VoiceHealth | null;
  ttsQueue: Promise<void>;
}

const state: VoiceState = {
  mic: null,
  currentPersona: null,
  personas: [],
  health: null,
  ttsQueue: Promise.resolve(),
};

export async function setup(): Promise<void> {
  // Prime persona list + health snapshot in parallel; skeleton UI
  // can render while these finish so the badge doesn't block boot.
  const [personasRes, healthRes] = await Promise.allSettled([
    api<{
      ok: boolean;
      default_persona_id: string;
      personas: Persona[];
    }>("/api/voice/personas"),
    api<VoiceHealth>("/api/voice/health"),
  ]);

  if (personasRes.status === "fulfilled") {
    state.personas = personasRes.value.personas ?? [];
    const defId = personasRes.value.default_persona_id;
    state.currentPersona =
      state.personas.find((p) => p.id === defId) ??
      state.personas[0] ??
      null;
  } else {
    console.warn("[voice] personas fetch failed", personasRes.reason);
  }

  if (healthRes.status === "fulfilled") {
    state.health = healthRes.value;
  } else {
    console.warn("[voice] health fetch failed", healthRes.reason);
  }
}

export function teardown(): void {
  releaseMic();
  state.personas = [];
  state.currentPersona = null;
  state.health = null;
  state.ttsQueue = Promise.resolve();
}

export function getPersonas(): Persona[] {
  return [...state.personas];
}

export function getCurrentPersona(): Persona | null {
  return state.currentPersona;
}

export function getHealth(): VoiceHealth | null {
  return state.health;
}

export function setPersona(id: string): boolean {
  const next = state.personas.find((p) => p.id === id);
  if (!next) return false;
  state.currentPersona = next;
  return true;
}

/**
 * Request mic permission on first user gesture; idempotent. Resolves
 * with the cached `MediaStream` on subsequent calls. Throws if the
 * browser denies permission or `getUserMedia` is unavailable.
 */
export async function ensureMic(): Promise<MediaStream> {
  if (state.mic) return state.mic;
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("getUserMedia_unavailable");
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: true,
  });
  state.mic = stream;
  return stream;
}

export function releaseMic(): void {
  if (!state.mic) return;
  for (const t of state.mic.getTracks()) {
    try {
      t.stop();
    } catch {
      /* */
    }
  }
  state.mic = null;
}

export function hasMic(): boolean {
  return state.mic !== null;
}

/**
 * Queue a TTS utterance. Serialised so back-to-back clicks don't
 * overlap; the returned promise resolves when playback finishes
 * (or rejects-and-logs without propagating).
 */
export function speak(
  text: string,
  opts: { personaId?: string } = {},
): Promise<void> {
  const personaId = opts.personaId ?? state.currentPersona?.id;
  state.ttsQueue = state.ttsQueue.then(() =>
    playOne(text, personaId).catch((err) => {
      console.warn("[voice] tts failed", err);
    }),
  );
  return state.ttsQueue;
}

async function playOne(text: string, personaId?: string): Promise<void> {
  const body: Record<string, unknown> = { text };
  if (personaId) body.persona_id = personaId;

  let res: Response;
  try {
    res = await apiBinary("/api/voice/speak", body);
  } catch (err) {
    if (err instanceof ApiError && err.status === 402) {
      // Cap-hit — bubble up so the UI can show "Voice degraded".
      console.warn("[voice] tts cap-hit", err.detail);
    }
    throw err;
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    await new Promise<void>((resolve, reject) => {
      const audio = new Audio(url);
      audio.onended = () => resolve();
      audio.onerror = () => reject(new Error("audio_play_failed"));
      audio.play().catch(reject);
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}
