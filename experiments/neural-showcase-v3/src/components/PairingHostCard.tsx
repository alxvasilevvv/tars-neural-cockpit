/**
 * <PairingHostCard /> — host-side pairing UI for L5 (mock-crypto era).
 *
 * Walks the operator through the 5-state machine pinned by
 * `docs/contracts/L5_PAIRING_DRAFT.md` (v1, host-only):
 *
 *   idle → pending → awaiting_confirmation → linked
 *                  ↘ expired / rejected
 *
 * Wires against the already-shipped `/api/pairing/{begin,accept,reject,
 * status,devices,revoke}` endpoints via `@/lib/pairing.ts`. Crypto is
 * still mock — the operator-visible `host_fingerprint` is real, the
 * `client_epk` we send is a deterministic placeholder for now. When
 * Cursor swaps in the real X25519 wrapping, only the `client_epk`
 * provider here needs touching; the UI stays frozen.
 *
 * Card design:
 *   - Brand-triad hairline accent on top
 *   - Dynamic body per state (QR + fingerprint + accept/reject CTAs)
 *   - Devices roster footer with per-device revoke (policy-gated)
 *   - 120-second countdown until QR expiry
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Loader2,
  ShieldCheck,
  X,
  RefreshCw,
  Smartphone,
  Monitor,
} from "lucide-react";
import {
  acceptPairing,
  beginPairing,
  formatFingerprint,
  listDevices,
  pollPairingStatus,
  rejectPairing,
  revokeDevice,
  type BeginResponse,
  type DeviceKind,
  type PairedDevice,
  type PairingStatus,
} from "@/lib/pairing";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";

type LocalState = "idle" | "pending" | "confirm" | "linked" | "error";

interface Props {
  /** Pre-fill what kind of client we expect to pair with — defaults to mobile_ios. */
  defaultKind?: DeviceKind;
}

export function PairingHostCard({ defaultKind = "mobile_ios" }: Props) {
  const [state, setState] = useState<LocalState>("idle");
  const [begin, setBegin] = useState<BeginResponse | null>(null);
  const [status, setStatus] = useState<PairingStatus | null>(null);
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);

  // 1-second tick for the expiry countdown
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);

  // Poll status while a pairing is in flight
  useEffect(() => {
    if (state !== "pending" && state !== "confirm") return;
    if (!begin?.pair_id) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await pollPairingStatus(begin.pair_id);
        if (cancelled) return;
        setStatus(s);
        if (s.state === "linked") setState("linked");
        else if (s.state === "expired" || s.state === "rejected") setState("error");
        else if (s.state === "pending") {
          // mobile has scanned and posted /begin — host now waits for operator
          setState("confirm");
        }
      } catch (e) {
        if (!cancelled) setError(String((e as Error)?.message ?? e));
      }
    };
    const timer = setInterval(poll, 1500);
    void poll();
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [state, begin]);

  // Devices roster — refresh on `linked` and on initial mount
  const refreshDevices = useCallback(async () => {
    try {
      const r = await listDevices();
      setDevices(r.devices);
    } catch {
      // non-fatal, keep stale list
    }
  }, []);
  useEffect(() => {
    void refreshDevices();
  }, [refreshDevices, state]);

  const startPairing = useCallback(async () => {
    setError(null);
    setStatus(null);
    setState("pending");
    try {
      const r = await beginPairing({
        client_epk: "mock_client_epk_placeholder", // Cursor swaps when crypto lands
        kind: defaultKind,
      });
      setBegin(r);
    } catch (e) {
      setState("error");
      setError(String((e as Error)?.message ?? e));
    }
  }, [defaultKind]);

  const accept = useCallback(async () => {
    if (!begin?.accept_token) return;
    try {
      await acceptPairing(begin.accept_token);
      setState("linked");
      void refreshDevices();
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    }
  }, [begin, refreshDevices]);

  const reject = useCallback(async () => {
    if (!begin?.accept_token) return;
    try {
      await rejectPairing(begin.accept_token, "operator_declined");
      setState("error");
      setError("operator_declined");
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    }
  }, [begin]);

  const reset = useCallback(() => {
    setState("idle");
    setBegin(null);
    setStatus(null);
    setError(null);
  }, []);

  const expiresIn = useMemo(() => {
    if (!begin?.expires_at) return null;
    return Math.max(0, Math.round(begin.expires_at - now));
  }, [begin, now]);

  return (
    <section
      aria-label="device pairing"
      className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1/70 backdrop-blur-sm"
    >
      <CornerFrame />
      {/* Top brand-triad hairline */}
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
        }}
      />

      <header className="flex items-center justify-between gap-3 border-b border-line px-6 py-5">
        <div className="flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[3px]">
          <span style={{ color: "#6366F1" }}>L5</span>
          <span className="text-ink">device pairing</span>
          <span className="text-ink-3">contract 1.1.0</span>
        </div>
        {state === "linked" && <StatusLozenge label="LINKED" tone="success" />}
        {state === "error" && <StatusLozenge label="ABORTED" tone="alert" />}
        {(state === "pending" || state === "confirm") && (
          <StatusLozenge label="PAIRING" tone="accent" />
        )}
      </header>

      <div className="px-6 py-7 md:px-8 md:py-8">
        {/* IDLE — "Pair phone" CTA */}
        {state === "idle" && (
          <div className="grid grid-cols-1 items-center gap-6 md:grid-cols-[auto_1fr_auto]">
            <span
              className="grid h-12 w-12 place-items-center rounded-md text-accent"
              style={{
                background: "color-mix(in srgb, var(--color-accent) 14%, transparent)",
                boxShadow: "inset 0 0 0 1px rgba(99,102,241,0.32)",
              }}
              aria-hidden
            >
              <Smartphone size={20} strokeWidth={1.6} />
            </span>
            <div>
              <div className="font-display text-[16px] tracking-[0.01em] text-ink">
                Pair a new device
              </div>
              <p className="mt-1 max-w-[52ch] text-[13px] leading-[1.55] text-ink-2">
                Scan a QR with your phone or paste a 24-char code. Pairing seed
                expires in 120 seconds. Master keyring stays on this Mac.
              </p>
            </div>
            <button
              type="button"
              onClick={startPairing}
              className="inline-flex items-center gap-2 rounded-md px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5"
              style={{
                background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                boxShadow:
                  "0 0 0 1px rgba(99,102,241,0.45), 0 12px 32px -10px rgba(99,102,241,0.55)",
              }}
            >
              Generate seed
            </button>
          </div>
        )}

        {/* PENDING — QR + fingerprint + countdown */}
        {state === "pending" && begin && (
          <div className="grid grid-cols-1 gap-7 md:grid-cols-[auto_1fr] md:gap-9">
            <PlaceholderQR seed={begin.pair_id} />
            <div>
              <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                step 1 of 2
              </div>
              <h3 className="mt-1 font-display text-[18px] leading-[1.3] text-ink">
                Scan the QR with your phone.
              </h3>
              <p className="mt-3 max-w-[52ch] text-[13px] leading-[1.6] text-ink-2">
                The bech32 fallback below works if the camera isn't available.
                Pairing seed expires automatically.
              </p>

              <Bech32Fallback seed={begin.pair_id} hostId={begin.host_id} />

              <FingerprintRow
                label="host fingerprint"
                value={begin.host_fingerprint}
              />

              {expiresIn !== null && <CountdownPill secondsLeft={expiresIn} />}

              <button
                type="button"
                onClick={reset}
                className="mt-5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3 transition-colors hover:text-alert"
              >
                Cancel pairing
              </button>
            </div>
          </div>
        )}

        {/* CONFIRM — operator accepts after phone scanned */}
        {state === "confirm" && begin && status && (
          <div className="grid grid-cols-1 gap-7 md:grid-cols-[auto_1fr] md:gap-9">
            <PlaceholderQR seed={begin.pair_id} dimmed />
            <div>
              <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
                step 2 of 2
              </div>
              <h3 className="mt-1 font-display text-[18px] leading-[1.3] text-ink">
                Confirm fingerprint matches your phone.
              </h3>
              <p className="mt-3 max-w-[52ch] text-[13px] leading-[1.6] text-ink-2">
                Both screens should show the same string. If they don't, tap
                <span className="text-alert"> reject</span>.
              </p>

              <FingerprintRow label="host" value={begin.host_fingerprint} />
              <FingerprintRow label="client" value={status.host_fingerprint} highlight />

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={accept}
                  className="inline-flex items-center gap-2 rounded-md px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white"
                  style={{
                    background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                    boxShadow: "0 0 0 1px rgba(99,102,241,0.45), 0 10px 28px -10px rgba(99,102,241,0.55)",
                  }}
                >
                  <ShieldCheck size={14} strokeWidth={1.8} />
                  Accept & link
                </button>
                <button
                  type="button"
                  onClick={reject}
                  className="inline-flex items-center gap-2 rounded-md border border-line px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-alert transition-colors hover:bg-alert/10"
                >
                  <X size={14} strokeWidth={2} />
                  Reject
                </button>
              </div>
            </div>
          </div>
        )}

        {/* LINKED — success */}
        {state === "linked" && status && (
          <div className="flex flex-col items-start gap-4">
            <div
              className="grid h-12 w-12 place-items-center rounded-full"
              style={{
                background: "color-mix(in srgb, var(--color-success) 16%, transparent)",
                color: "var(--color-success)",
                boxShadow: "inset 0 0 0 1px rgba(52,211,153,0.45), 0 0 24px rgba(52,211,153,0.3)",
              }}
              aria-hidden
            >
              <ShieldCheck size={22} strokeWidth={1.6} />
            </div>
            <div className="font-display text-[18px] text-ink">Device linked.</div>
            <p className="max-w-[52ch] text-[13px] leading-[1.6] text-ink-2">
              {status.client_kind} added to your sync graph. Ciphertext blobs
              now wrap for {devices.length + 1} device{devices.length === 0 ? "" : "s"};
              meeet.world stores them opaquely. Revoke any time below.
            </p>
            <button
              type="button"
              onClick={reset}
              className="mt-2 inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              Pair another
            </button>
          </div>
        )}

        {/* ERROR */}
        {state === "error" && (
          <div className="flex flex-col items-start gap-4">
            <div
              className="grid h-12 w-12 place-items-center rounded-full"
              style={{
                background: "color-mix(in srgb, var(--color-alert) 14%, transparent)",
                color: "var(--color-alert)",
                boxShadow: "inset 0 0 0 1px rgba(239,68,68,0.4)",
              }}
              aria-hidden
            >
              <X size={22} strokeWidth={2} />
            </div>
            <div className="font-display text-[18px] text-ink">Pairing aborted.</div>
            <p className="max-w-[52ch] text-[13px] leading-[1.6] text-ink-2">
              {error ?? "Unknown error."}
            </p>
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              <RefreshCw size={12} strokeWidth={1.8} />
              Try again
            </button>
          </div>
        )}
      </div>

      {/* Devices roster */}
      {devices.length > 0 && (
        <div className="border-t border-line px-6 py-5 md:px-8">
          <div className="mb-3 flex items-center justify-between font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
            <span>paired devices · {devices.length}</span>
            <button
              type="button"
              onClick={() => void refreshDevices()}
              className="inline-flex items-center gap-1.5 transition-colors hover:text-ink"
            >
              <RefreshCw size={11} strokeWidth={1.6} /> refresh
            </button>
          </div>
          <ul className="grid gap-2">
            {devices.map(d => (
              <DeviceRow
                key={d.device_id}
                device={d}
                onRevoke={async () => {
                  try {
                    await revokeDevice(d.device_id);
                    void refreshDevices();
                  } catch (e) {
                    setError(String((e as Error)?.message ?? e));
                  }
                }}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/* ─── Helpers ──────────────────────────────────────────────────────── */

function PlaceholderQR({ seed, dimmed }: { seed: string; dimmed?: boolean }) {
  // Deterministic noise grid keyed by `seed` — not a real QR encoding.
  // When Cursor adds a qrcode library, swap this for the real renderer
  // — same outer dimensions, no layout shift.
  const cells = useMemo(() => {
    const out: boolean[] = [];
    let acc = 0;
    for (let i = 0; i < seed.length; i++) acc = (acc * 31 + seed.charCodeAt(i)) >>> 0;
    for (let i = 0; i < 25 * 25; i++) {
      acc = (acc * 1664525 + 1013904223) >>> 0;
      out.push((acc & 1) === 1);
    }
    return out;
  }, [seed]);
  return (
    <div
      className="relative grid h-[200px] w-[200px] place-items-center rounded-[10px] border border-line-strong bg-white p-3"
      style={{ opacity: dimmed ? 0.4 : 1 }}
      aria-label="pairing QR placeholder"
    >
      <svg viewBox="0 0 25 25" className="block h-full w-full" aria-hidden>
        {cells.map((on, i) => {
          if (!on) return null;
          const x = i % 25;
          const y = Math.floor(i / 25);
          return <rect key={i} x={x} y={y} width="1" height="1" fill="#0b0b10" />;
        })}
        {/* finder squares */}
        {[
          [0, 0],
          [18, 0],
          [0, 18],
        ].map(([x, y]) => (
          <g key={`${x}-${y}`}>
            <rect x={x} y={y} width="7" height="7" fill="#0b0b10" />
            <rect x={x + 1} y={y + 1} width="5" height="5" fill="#fff" />
            <rect x={x + 2} y={y + 2} width="3" height="3" fill="#0b0b10" />
          </g>
        ))}
      </svg>
    </div>
  );
}

function Bech32Fallback({ seed, hostId }: { seed: string; hostId: string }) {
  const value = `tars1${hostId.slice(0, 12)}${seed.slice(0, 12)}`;
  const copy = () => navigator.clipboard?.writeText(value);
  return (
    <div className="mt-5 grid grid-cols-[1fr_auto] items-center gap-2 rounded-md border border-line bg-bg-2/50 px-3 py-2 font-mono text-[11px]">
      <code className="truncate text-ink-2" title={value}>
        {value}
      </code>
      <button
        type="button"
        onClick={copy}
        className="font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3 transition-colors hover:text-ink"
      >
        copy
      </button>
    </div>
  );
}

function FingerprintRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="mt-4 flex items-baseline gap-3 font-mono-tech text-[11px] uppercase tracking-[2.4px]">
      <span className="text-ink-3">{label}</span>
      <span
        className="rounded-md px-2 py-0.5 tabular-nums"
        style={{
          color: highlight ? "var(--color-success)" : "var(--color-ink)",
          background: highlight
            ? "color-mix(in srgb, var(--color-success) 12%, transparent)"
            : "var(--color-bg-2)",
          boxShadow: highlight
            ? "inset 0 0 0 1px rgba(52,211,153,0.4)"
            : "inset 0 0 0 1px var(--color-line-strong)",
        }}
      >
        {formatFingerprint(value)}
      </span>
    </div>
  );
}

function CountdownPill({ secondsLeft }: { secondsLeft: number }) {
  const danger = secondsLeft < 30;
  return (
    <div
      className="mt-4 inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono-tech text-[10px] uppercase tracking-[2.2px]"
      style={{
        borderColor: danger ? "var(--color-alert)" : "var(--color-line-strong)",
        color: danger ? "var(--color-alert)" : "var(--color-ink-2)",
      }}
    >
      <Loader2 size={11} strokeWidth={1.8} className={danger ? "" : "animate-spin"} />
      expires in {secondsLeft}s
    </div>
  );
}

function DeviceRow({
  device,
  onRevoke,
}: {
  device: PairedDevice;
  onRevoke: () => void;
}) {
  const Icon =
    device.kind === "mobile_ios" || device.kind === "mobile_android"
      ? Smartphone
      : Monitor;
  return (
    <li className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 rounded-md border border-line bg-bg-1/40 px-3 py-2.5">
      <span className="text-ink-2" aria-hidden>
        <Icon size={14} strokeWidth={1.6} />
      </span>
      <div className="min-w-0">
        <div className="truncate font-mono-tech text-[11.5px] text-ink">
          {device.kind} · {device.device_id.slice(0, 12)}
        </div>
        <div className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
          last seen {fmtRelative(device.last_seen_at)}
        </div>
      </div>
      <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        linked {fmtRelative(device.linked_at)}
      </span>
      <button
        type="button"
        onClick={onRevoke}
        aria-label={`revoke ${device.device_id}`}
        className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-alert/45 hover:text-alert"
      >
        revoke
      </button>
    </li>
  );
}

function fmtRelative(ts: number): string {
  if (!ts) return "—";
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}
