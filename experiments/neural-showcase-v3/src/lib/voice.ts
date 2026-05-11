/**
 * Voice client + persona / playback / mic hooks (Phase L4.1).
 *
 * Backend surface:
 *   GET  /api/voice/personas
 *   GET  /api/voice/health
 *   POST /api/voice/speak                      → audio bytes
 *
 * Persona choice is operator-scoped (localStorage), TTS playback uses
 * a single shared <audio> element so a new utterance interrupts the
 * previous one cleanly.
 *
 * STT (mic input) uses the browser's Web Speech API — zero deps,
 * works in Chrome/Edge/Safari. The hook degrades cleanly when the
 * API is missing (e.g. Firefox).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE } from "./api";
import { getSessionId } from "./session";

// --------------------------------------------------------------------
// Types
// --------------------------------------------------------------------

export type VoiceProviderId = "auto" | "elevenlabs" | "openai" | "mac_say";

export interface VoicePersona {
  id: string;
  name: string;
  character: string;
  description: string;
  short: string;
  accent: string;
  locale: string;
  license_note: string | null;
  providers: {
    elevenlabs: { voice_id: string | null; model: string };
    openai: { voice: string | null; model: string; has_instructions: boolean };
    mac_say: { voice: string | null; rate: number | null; pitch: number | null };
  };
}

export interface VoiceHealth {
  ok: boolean;
  any_available: boolean;
  engines: { elevenlabs: boolean; openai: boolean; mac_say: boolean };
  preferred_order: VoiceProviderId[];
}

// --------------------------------------------------------------------
// Storage helpers
// --------------------------------------------------------------------

const PERSONA_KEY = "tars.voice.persona";
const PROVIDER_KEY = "tars.voice.provider";
const AUTOPLAY_KEY = "tars.voice.autoplay";
const MUTED_KEY = "tars.voice.muted";

// Wave 122 — every localStorage call is now wrapped: in private/incognito
// browsing both Safari and Firefox throw on access, which previously could
// crash any voice-control surface that called these helpers at mount time.

function _safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function _safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode / quota exceeded — silently drop, runtime keeps going */
  }
}

export function getStoredPersonaId(): string {
  // Persona slug is a functional id mapped to the backend voice registry
  // (`backend/core/voice/personas.py` — DEFAULT_PERSONA_ID). Distinct from
  // the product name (TARS); stays as the historical character slug.
  return _safeGet(PERSONA_KEY) || "jarvis";
}

export function setStoredPersonaId(id: string): void {
  _safeSet(PERSONA_KEY, id);
}

export function getStoredProvider(): VoiceProviderId {
  const v = _safeGet(PROVIDER_KEY);
  if (v === "elevenlabs" || v === "openai" || v === "mac_say") return v;
  return "auto";
}

export function setStoredProvider(p: VoiceProviderId): void {
  _safeSet(PROVIDER_KEY, p);
}

export function getAutoplay(): boolean {
  return _safeGet(AUTOPLAY_KEY) === "1";
}

export function setAutoplay(v: boolean): void {
  _safeSet(AUTOPLAY_KEY, v ? "1" : "0");
}

export function getMuted(): boolean {
  return _safeGet(MUTED_KEY) === "1";
}

export function setMuted(v: boolean): void {
  _safeSet(MUTED_KEY, v ? "1" : "0");
}

// --------------------------------------------------------------------
// Fetch helpers
// --------------------------------------------------------------------

export async function listPersonas(): Promise<VoicePersona[]> {
  const r = await fetch(`${API_BASE}/api/voice/personas`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const body = (await r.json()) as { personas: VoicePersona[] };
  return body.personas;
}

export async function getVoiceHealth(): Promise<VoiceHealth> {
  const r = await fetch(`${API_BASE}/api/voice/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as VoiceHealth;
}

export interface SpeakOptions {
  text: string;
  personaId?: string;
  provider?: VoiceProviderId;
  sessionId?: string;
  signal?: AbortSignal;
}

export interface SpeakResult {
  blob: Blob;
  url: string;
  provider: string;
  voiceId: string;
  durationMs: number;
}

export async function speak(opts: SpeakOptions): Promise<SpeakResult> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-tars-session-id": opts.sessionId ?? getSessionId(),
  };
  const r = await fetch(`${API_BASE}/api/voice/speak`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text: opts.text,
      persona: opts.personaId,
      provider: opts.provider && opts.provider !== "auto" ? opts.provider : undefined,
    }),
    signal: opts.signal,
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(`speak failed · HTTP ${r.status} · ${detail}`);
  }
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  return {
    blob,
    url,
    provider: r.headers.get("x-tars-voice-provider") || "?",
    voiceId: r.headers.get("x-tars-voice-voice-id") || "?",
    durationMs: Number(r.headers.get("x-tars-voice-duration-ms") || 0),
  };
}

// --------------------------------------------------------------------
// Playback hook
// --------------------------------------------------------------------

export interface VoicePlaybackHook {
  /** Play `text` through the selected persona. */
  play: (text: string, opts?: { personaId?: string }) => Promise<void>;
  /** Stop the currently-playing utterance. */
  stop: () => void;
  speaking: boolean;
  /** Last error message, surfaced for the cockpit's status UI. */
  error: string | null;
  /** Currently-playing provider (`"elevenlabs"`, `"openai"`, `"mac_say"`). */
  lastProvider: string | null;
  personaId: string;
  setPersonaId: (id: string) => void;
  provider: VoiceProviderId;
  setProvider: (p: VoiceProviderId) => void;
  autoplay: boolean;
  setAutoplay: (v: boolean) => void;
  muted: boolean;
  setMuted: (v: boolean) => void;
}

export function useVoicePlayback(): VoicePlaybackHook {
  const [personaId, setPersonaIdState] = useState<string>(() => getStoredPersonaId());
  const [provider, setProviderState] = useState<VoiceProviderId>(() => getStoredProvider());
  const [autoplay, setAutoplayState] = useState<boolean>(() => getAutoplay());
  const [muted, setMutedState] = useState<boolean>(() => getMuted());
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastProvider, setLastProvider] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastUrlRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Stop on unmount.
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
      abortRef.current?.abort();
    };
  }, []);

  const setPersonaId = useCallback((id: string) => {
    setStoredPersonaId(id);
    setPersonaIdState(id);
  }, []);
  const setProvider = useCallback((p: VoiceProviderId) => {
    setStoredProvider(p);
    setProviderState(p);
  }, []);
  const setAutoplayPref = useCallback((v: boolean) => {
    setAutoplay(v);
    setAutoplayState(v);
  }, []);
  const setMutedPref = useCallback((v: boolean) => {
    setMuted(v);
    setMutedState(v);
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    audioRef.current?.pause();
    setSpeaking(false);
  }, []);

  const play = useCallback(
    async (text: string, opts: { personaId?: string } = {}) => {
      if (muted) return;
      const trimmed = text.trim();
      if (!trimmed) return;
      stop();
      setError(null);
      setSpeaking(true);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const result = await speak({
          text: trimmed,
          personaId: opts.personaId ?? personaId,
          provider,
          signal: ctrl.signal,
        });
        if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = result.url;
        setLastProvider(result.provider);
        const audio = new Audio(result.url);
        audioRef.current = audio;
        audio.addEventListener("ended", () => setSpeaking(false), { once: true });
        audio.addEventListener("error", () => {
          setError("audio_playback_error");
          setSpeaking(false);
        }, { once: true });
        await audio.play();
      } catch (exc) {
        if ((exc as Error)?.name === "AbortError") {
          setSpeaking(false);
          return;
        }
        setError(String((exc as Error)?.message ?? exc));
        setSpeaking(false);
      } finally {
        abortRef.current = null;
      }
    },
    [muted, personaId, provider, stop],
  );

  return useMemo(
    () => ({
      play,
      stop,
      speaking,
      error,
      lastProvider,
      personaId,
      setPersonaId,
      provider,
      setProvider,
      autoplay,
      setAutoplay: setAutoplayPref,
      muted,
      setMuted: setMutedPref,
    }),
    [
      play,
      stop,
      speaking,
      error,
      lastProvider,
      personaId,
      setPersonaId,
      provider,
      setProvider,
      autoplay,
      setAutoplayPref,
      muted,
      setMutedPref,
    ],
  );
}

// --------------------------------------------------------------------
// Persona / health hooks
// --------------------------------------------------------------------

export function usePersonas() {
  const [personas, setPersonas] = useState<VoicePersona[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await listPersonas();
        if (!cancelled) setPersonas(list);
      } catch (exc) {
        if (!cancelled) setError(String((exc as Error)?.message ?? exc));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return { personas, error };
}

export function useVoiceHealth(intervalMs = 30000) {
  const [data, setData] = useState<VoiceHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const h = await getVoiceHealth();
        if (!cancelled) setData(h);
      } catch (exc) {
        if (!cancelled) setError(String((exc as Error)?.message ?? exc));
      }
    };
    void tick();
    const handle = window.setInterval(() => void tick(), intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [intervalMs]);
  return { data, error };
}

// --------------------------------------------------------------------
// Web Speech STT (browser-native, free)
// --------------------------------------------------------------------

interface SpeechRecognitionEventLike {
  results: ArrayLike<{
    isFinal: boolean;
    [index: number]: { transcript: string };
  }>;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}

function _SpeechRecognitionCtor(): {
  new (): SpeechRecognitionLike;
} | null {
  const w = window as unknown as Record<string, unknown>;
  const ctor = (w.SpeechRecognition || w.webkitSpeechRecognition) as
    | { new (): SpeechRecognitionLike }
    | undefined;
  return ctor ?? null;
}

export interface MicHook {
  supported: boolean;
  listening: boolean;
  transcript: string;
  start: () => void;
  stop: () => void;
  error: string | null;
}

export function useMicTranscription(opts: { lang?: string } = {}): MicHook {
  const [supported] = useState(() => _SpeechRecognitionCtor() !== null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);

  const start = useCallback(() => {
    if (listening) return;
    const Ctor = _SpeechRecognitionCtor();
    if (!Ctor) {
      setError("speech_recognition_unsupported");
      return;
    }
    const rec = new Ctor();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = opts.lang ?? navigator.language ?? "en-US";
    rec.onresult = (e) => {
      let txt = "";
      const results = e.results;
      for (let i = 0; i < results.length; i++) {
        txt += results[i][0].transcript;
      }
      setTranscript(txt);
    };
    rec.onerror = (e) => {
      setError(e.error || "mic_error");
      setListening(false);
    };
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setError(null);
    setTranscript("");
    setListening(true);
    rec.start();
  }, [listening, opts.lang]);

  const stop = useCallback(() => {
    recRef.current?.stop();
    setListening(false);
  }, []);

  useEffect(() => {
    return () => {
      recRef.current?.abort();
    };
  }, []);

  return { supported, listening, transcript, start, stop, error };
}
