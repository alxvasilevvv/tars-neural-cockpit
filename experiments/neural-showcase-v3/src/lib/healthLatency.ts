import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

/**
 * useHealthLatency — polls `/health` every PROBE_MS, keeps the last
 * SAMPLES round-trip times in a sliding window. Pauses when the tab
 * is hidden so we don't drain the operator's battery in the
 * background.
 *
 * Returns:
 *   samples: (number | null)[]  — ms latencies, null = probe failed.
 *                                  Always SAMPLES long; oldest first.
 *   latest:  number | null       — last successful latency or null.
 *   tier:    "fast" | "ok" | "slow" | "down"
 *
 * Tier thresholds:
 *   fast   < 200ms
 *   ok     200..500ms
 *   slow   500..1500ms
 *   down   1500ms+ or failed
 *
 * Use from `<CockpitRightRail />` to render the latency sparkline.
 */

const PROBE_MS = 5000;
const SAMPLES = 12; // 12 × 5s = 60s window

export type LatencyTier = "fast" | "ok" | "slow" | "down";

export interface HealthLatencyResult {
  samples: (number | null)[];
  latest: number | null;
  tier: LatencyTier;
}

function tierFor(ms: number | null): LatencyTier {
  if (ms == null) return "down";
  if (ms < 200) return "fast";
  if (ms < 500) return "ok";
  if (ms < 1500) return "slow";
  return "down";
}

export function useHealthLatency(enabled = true): HealthLatencyResult {
  const [samples, setSamples] = useState<(number | null)[]>(() =>
    new Array<number | null>(SAMPLES).fill(null),
  );

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const probe = async () => {
      if (cancelled) return;
      // Skip when tab is hidden — keeps the OS-level network LED dark
      // and the operator's battery happy. We catch up on the next
      // visibility-change burst.
      if (typeof document !== "undefined" && document.hidden) {
        timer = setTimeout(probe, PROBE_MS);
        return;
      }
      const t0 =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      let ms: number | null = null;
      try {
        const h = await Promise.race([
          getHealth(),
          new Promise<null>((_, rej) =>
            setTimeout(() => rej(new Error("probe-timeout")), 1500),
          ),
        ]);
        if (h && (h as { ok?: boolean }).ok !== false) {
          const t1 =
            typeof performance !== "undefined" ? performance.now() : Date.now();
          ms = Math.max(1, Math.round(t1 - t0));
        }
      } catch {
        ms = null;
      }
      if (!cancelled) {
        setSamples(prev => {
          const next = prev.slice(1);
          next.push(ms);
          return next;
        });
      }
      if (!cancelled) {
        timer = setTimeout(probe, PROBE_MS);
      }
    };

    // First probe runs almost immediately so the sparkline has at
    // least one real bar within the first PROBE_MS interval.
    timer = setTimeout(probe, 250);

    const onVisibility = () => {
      if (!document.hidden && !cancelled) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(probe, 0);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled]);

  // Resolve `latest` from the most recent non-null sample.
  let latest: number | null = null;
  for (let i = samples.length - 1; i >= 0; i--) {
    if (samples[i] != null) {
      latest = samples[i];
      break;
    }
  }

  return { samples, latest, tier: tierFor(latest) };
}
