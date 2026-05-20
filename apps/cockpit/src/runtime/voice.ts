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
 *   W309 step 2 adds STT upload (`/api/voice/transcribe`) via
 *   `MediaRecorder` + `startRecording()` / `stopRecording()`.
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

import { api, apiBinary, apiMultipart, ApiError } from "./api";

const PERSONA_LS_KEY = "TARS_VOICE_PERSONA";

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
  micPromise: Promise<MediaStream> | null;
  currentPersona: Persona | null;
  personas: Persona[];
  health: VoiceHealth | null;
  ttsQueue: Promise<void>;
  alive: boolean;
  recorder: MediaRecorder | null;
  recordChunks: BlobPart[];
  recordingMime: string;
  recordPromise: Promise<void> | null;
}

const state: VoiceState = {
  mic: null,
  micPromise: null,
  currentPersona: null,
  personas: [],
  health: null,
  ttsQueue: Promise.resolve(),
  alive: true,
  recorder: null,
  recordChunks: [],
  recordingMime: "audio/webm",
  recordPromise: null,
};

/**
 * Stream is considered usable when it's present, `active === true`,
 * and at least one audio track is in `readyState === "live"`. The
 * `active` flag flips to `false` when the operator revokes permission
 * via OS settings mid-session; without this check `ensureMic()` would
 * hand back a dead stream and the UI would lie about mic status.
 */
function isStreamUsable(stream: MediaStream | null): stream is MediaStream {
  if (!stream || !stream.active) return false;
  return stream.getAudioTracks().some((t) => t.readyState === "live");
}

export async function setup(): Promise<void> {
  state.alive = true;
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
    let chosen =
      state.personas.find((p) => p.id === defId) ??
      state.personas[0] ??
      null;
    try {
      const saved = window.localStorage.getItem(PERSONA_LS_KEY);
      if (saved) {
        const restored = state.personas.find((p) => p.id === saved);
        if (restored) chosen = restored;
      }
    } catch {
      /* private browsing */
    }
    state.currentPersona = chosen;
    if (chosen) {
      void refreshPersonaEffective(chosen.id).catch((err) =>
        console.warn("[voice] personas/effective prefetch failed", err),
      );
    }
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
  state.alive = false;
  abortRecording();
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
  try {
    window.localStorage.setItem(PERSONA_LS_KEY, id);
  } catch {
    /* */
  }
  void refreshPersonaEffective(id).catch((err) =>
    console.warn("[voice] personas/effective failed", err),
  );
  return true;
}

async function refreshPersonaEffective(personaId: string): Promise<void> {
  await api<{ ok: boolean }>(
    `/api/voice/personas/effective?persona_id=${encodeURIComponent(personaId)}`,
  );
}

function pickRecordingMime(): string {
  if (typeof MediaRecorder === "undefined") return "audio/webm";
  const candidates = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"];
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return "";
}

function abortRecording(): void {
  if (state.recorder && state.recorder.state !== "inactive") {
    try {
      state.recorder.stop();
    } catch {
      /* */
    }
  }
  state.recorder = null;
  state.recordChunks = [];
  state.recordPromise = null;
}

export function isRecording(): boolean {
  return state.recorder?.state === "recording";
}

export async function startRecording(): Promise<void> {
  if (state.recordPromise) return state.recordPromise;
  if (isRecording()) return;

  state.recordPromise = (async () => {
    const stream = await ensureMic();
    const mime = pickRecordingMime();
    state.recordingMime = mime || "audio/webm";
    state.recordChunks = [];
    const recorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream);
    state.recorder = recorder;
    recorder.ondataavailable = (evt) => {
      if (evt.data && evt.data.size > 0) state.recordChunks.push(evt.data);
    };
    recorder.start();
  })().finally(() => {
    state.recordPromise = null;
  });
  return state.recordPromise;
}

export async function stopRecording(): Promise<string> {
  if (!state.recorder || state.recorder.state === "inactive") {
    throw new Error("not_recording");
  }

  const recorder = state.recorder;
  const text = await new Promise<string>((resolve, reject) => {
    recorder.onstop = () => {
      void (async () => {
        try {
          const blob = new Blob(state.recordChunks, {
            type: state.recordingMime,
          });
          state.recorder = null;
          state.recordChunks = [];
          const ext = state.recordingMime.includes("mp4") ? ".mp4" : ".webm";
          const form = new FormData();
          form.append("audio", blob, `capture${ext}`);
          const res = await apiMultipart<{ ok: boolean; text?: string }>(
            "/api/voice/transcribe",
            form,
          );
          resolve((res.text ?? "").trim());
        } catch (err) {
          reject(err);
        }
      })();
    };
    recorder.onerror = () => reject(new Error("recorder_failed"));
    try {
      recorder.stop();
    } catch (err) {
      reject(err);
    }
  });
  return text;
}

/**
 * Request mic permission on first user gesture; idempotent and
 * concurrency-safe. Resolves with the cached `MediaStream` on
 * subsequent calls. Drops the cache if the operator revoked
 * permission via OS settings (stream becomes inactive). Concurrent
 * callers share the same in-flight promise so the second click of a
 * double-click doesn't open a duplicate `getUserMedia` request whose
 * tracks then leak.
 */
export async function ensureMic(): Promise<MediaStream> {
  if (isStreamUsable(state.mic)) return state.mic;
  // Cached stream went stale (permission revoked, device unplugged).
  // Stop dead tracks so the OS frees the device and re-request below.
  if (state.mic && !isStreamUsable(state.mic)) {
    releaseMic();
  }
  if (state.micPromise) return state.micPromise;
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("getUserMedia_unavailable");
  }
  state.micPromise = (async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      // If teardown landed mid-flight, drop the stream rather than
      // caching it — caller will see a thrown error.
      if (!state.alive) {
        for (const t of stream.getTracks()) {
          try {
            t.stop();
          } catch {
            /* ignored */
          }
        }
        throw new Error("voice_torn_down");
      }
      state.mic = stream;
      return stream;
    } finally {
      state.micPromise = null;
    }
  })();
  return state.micPromise;
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
  return isStreamUsable(state.mic);
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
  // Drop late-queued utterances after teardown — keeps the chain from
  // resurrecting Audio elements on a window the user already closed.
  if (!state.alive) return;
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

  // Defensive: /api/voice/speak normally returns audio bytes, but a
  // future error path could return a 200 + JSON envelope. Don't feed
  // JSON to <audio> — surface as a typed failure instead.
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.startsWith("audio/")) {
    throw new Error(`tts_unexpected_content_type:${ct || "missing"}`);
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
