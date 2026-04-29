import { useEffect, useRef, useState } from "react";

/**
 * useMicLevel — request `getUserMedia({ audio })` only while `enabled`,
 * compute a smoothed RMS level (0..1), and yank the entire stream +
 * AudioContext the moment `enabled` flips back to false. No mic when
 * mic is off; no analyser, no track, no permission lingering.
 *
 * Privacy / UX:
 *   - We never request audio until `enabled === true`.
 *   - On permission denial we expose `status: "denied"` so the UI can
 *     fall back to a synthetic pulse rather than appearing broken.
 *   - `level` is a smoothed exponential of the per-frame RMS, clamped
 *     to [0, 1]. Useful for driving robot scan-rate / halo intensity
 *     without needing the raw waveform.
 *   - Cleans up on unmount AND on `enabled=false` (the same code path).
 *
 * Returns: { level, status, error }
 *
 *   level:   0..1 smoothed amplitude estimate
 *   status:  "off" | "requesting" | "live" | "denied" | "unsupported"
 *   error:   raw Error message when status === "denied" or "unsupported"
 */

export type MicStatus = "off" | "requesting" | "live" | "denied" | "unsupported";

export interface MicLevelResult {
  level: number;
  status: MicStatus;
  error: string | null;
}

const SMOOTHING = 0.18; // higher = snappier, lower = floatier
const FLOOR = 0.04;     // background noise floor we treat as silence

export function useMicLevel(enabled: boolean): MicLevelResult {
  const [level, setLevel] = useState(0);
  const [status, setStatus] = useState<MicStatus>("off");
  const [error, setError] = useState<string | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const smoothedRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      // Tear down — important: revokes the OS-level mic LED.
      teardown(contextRef, streamRef, rafRef);
      smoothedRef.current = 0;
      setLevel(0);
      setStatus("off");
      setError(null);
      return;
    }

    let cancelled = false;
    const start = async () => {
      // Bail early on environments without getUserMedia.
      if (
        typeof navigator === "undefined" ||
        !navigator.mediaDevices?.getUserMedia ||
        typeof window === "undefined" ||
        !(window.AudioContext || (window as any).webkitAudioContext)
      ) {
        setStatus("unsupported");
        setError("Web Audio API unavailable");
        return;
      }
      setStatus("requesting");
      setError(null);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        if (cancelled) {
          stream.getTracks().forEach(t => t.stop());
          return;
        }
        const Ctx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new Ctx();
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.65;
        source.connect(analyser);

        contextRef.current = ctx;
        streamRef.current = stream;
        setStatus("live");

        const buffer = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          analyser.getByteTimeDomainData(buffer);
          // RMS over the centred-around-128 PCM byte stream
          let sumSq = 0;
          for (let i = 0; i < buffer.length; i++) {
            const v = (buffer[i] - 128) / 128;
            sumSq += v * v;
          }
          const rms = Math.sqrt(sumSq / buffer.length); // 0..~1
          // Apply silence floor + exponential smoothing.
          const adj = Math.max(0, rms - FLOOR) / (1 - FLOOR);
          smoothedRef.current =
            smoothedRef.current * (1 - SMOOTHING) + adj * SMOOTHING;
          setLevel(Math.min(1, smoothedRef.current));
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch (e) {
        if (cancelled) return;
        const msg =
          (e as { name?: string; message?: string })?.name === "NotAllowedError"
            ? "Mic permission denied"
            : ((e as Error)?.message ?? String(e));
        setStatus("denied");
        setError(msg);
      }
    };

    void start();

    return () => {
      cancelled = true;
      teardown(contextRef, streamRef, rafRef);
      smoothedRef.current = 0;
      setLevel(0);
    };
  }, [enabled]);

  return { level, status, error };
}

function teardown(
  contextRef: React.MutableRefObject<AudioContext | null>,
  streamRef: React.MutableRefObject<MediaStream | null>,
  rafRef: React.MutableRefObject<number | null>,
) {
  if (rafRef.current != null) {
    cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
  }
  if (streamRef.current) {
    streamRef.current.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }
  if (contextRef.current) {
    void contextRef.current.close();
    contextRef.current = null;
  }
}
