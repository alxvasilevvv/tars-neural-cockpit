import { Link } from "react-router-dom";
import { AlertTriangle, Zap, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getEntitlements, type Entitlements } from "@/lib/api";

/**
 * <BudgetWarning /> — cockpit strip that nudges the operator before
 * cloud-LLM calls hit a 402 wall.
 *
 * Three states keyed by `live.spent_usd_24h / live.cap_usd_daily`:
 *   - none       (under 60%, or `allowed_cloud === true` and pct < 0.6)
 *   - warning    (60% ≤ used < 90%)  → muted yellow strip, dismissible
 *   - critical   (≥ 90% OR `allowed_cloud === false`)
 *                                    → red strip, not dismissible
 *
 * Live-wired to `GET /api/entitlements` (P5 backend, shipped).
 * Re-polls every 60s; fails open silently when the daemon is offline
 * (component renders nothing) so the cockpit chrome keeps loading.
 *
 * Spec: docs/PRODUCT_PHASE_M.md § 6.3 (throttle behaviour).
 */

/** Hook for live entitlement state. Returns null when daemon offline. */
function useEntitlements(): Entitlements | null {
  const [state, setState] = useState<Entitlements | null>(null);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const e = await getEntitlements();
        if (!cancelled) setState(e);
      } catch {
        /* daemon offline / endpoint unreachable — silently render nothing */
      }
    };
    void probe();
    const id = window.setInterval(probe, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return state;
}

export function BudgetWarning() {
  const ent = useEntitlements();
  const [dismissed, setDismissed] = useState(false);

  if (!ent) return null;

  const { live, byo_enabled } = ent;
  const cap = live.cap_usd_daily;
  const used = Math.max(0, live.spent_usd_24h);

  // BYO key path — operator brings their own LLM keys, no cap to warn about.
  if (byo_enabled) return null;
  // Unmetered tiers (current backend doesn't ship one but defensive).
  if (cap <= 0) return null;

  // The daemon's policy gate is authoritative. If it says cloud is blocked,
  // we render critical regardless of our percentage math.
  const blocked = live.allowed_cloud === false;
  const pct = used / cap;

  if (!blocked && pct < 0.6) return null;
  if (!blocked && pct < 0.9 && dismissed) return null;

  const critical = blocked || pct >= 0.9;
  // Tone colours pulled from CSS vars where possible. Warning amber falls
  // back to a hex constant only because we don't ship a `--color-warning`
  // token yet — wrap in `var(--color-warning, #F59E0B)` so when the token
  // lands the chip flips automatically.
  const tone = critical
    ? {
        bg: "color-mix(in srgb, var(--color-alert) 8%, transparent)",
        border: "var(--color-alert)",
        fg: "var(--color-alert)",
        Icon: AlertTriangle,
      }
    : {
        bg: "color-mix(in srgb, var(--color-warning, #F59E0B) 8%, transparent)",
        border: "color-mix(in srgb, var(--color-warning, #F59E0B) 45%, transparent)",
        fg: "var(--color-warning, #F59E0B)",
        Icon: Zap,
      };
  const Icon = tone.Icon;

  return (
    <div
      role="status"
      aria-live={critical ? "assertive" : "polite"}
      className="flex items-center gap-3 rounded-md border px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2px]"
      style={{ background: tone.bg, borderColor: tone.border, color: tone.fg }}
    >
      <Icon size={13} strokeWidth={1.8} aria-hidden />
      <span className="flex-1 text-ink-2">
        {critical ? (
          <>
            cloud budget {blocked ? "blocked" : "hit"} (${used.toFixed(2)} /
            ${cap.toFixed(2)})
            {live.reason ? <> · {live.reason}</> : null}
            {" "}· cloud LLM calls now require upgrade or BYO key
          </>
        ) : (
          <>
            cloud budget {Math.round(pct * 100)}% used (${used.toFixed(2)} /
            ${cap.toFixed(2)}) · ${live.remaining_usd.toFixed(2)} left today
          </>
        )}
      </span>
      <Link
        to="/pricing"
        className="text-ink underline-offset-4 transition-colors hover:underline"
      >
        upgrade
      </Link>
      {!critical && (
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="dismiss"
          className="grid h-5 w-5 place-items-center rounded-full text-ink-3 transition-colors hover:bg-white/5 hover:text-ink"
        >
          <X size={11} strokeWidth={2} />
        </button>
      )}
    </div>
  );
}
