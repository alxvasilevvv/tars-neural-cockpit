// SYNC: claude-w80-fe-only
/**
 * <ReceiptVerifier /> — Wave 80-D
 *
 * Paste a receipt JSON, click Verify, get back ✓ / ✗ with the
 * verifying pubkey + a short reason. Useful for auditors who receive
 * a receipt out-of-band and need to confirm it's authentic without
 * trusting any UI other than this one round-trip to the local
 * daemon.
 *
 * Hand-off contract: POST /api/receipts/verify with { receipt: {…} }.
 * Backend returns { ok: bool, verified: bool, signer: string,
 * reason?: string }. Daemon offline / 404 → we render an "offline
 * verify" mock that explicitly tells the user the result is
 * unverified — never claim a fake ✓.
 */

import { useId, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { API_BASE } from "@/lib/api";
import { BrandHairline } from "@/components/BrandHairline";

const SAMPLE = `{
  "v": 1,
  "id": "rcpt-mock-2026-05-09T10:01:23",
  "ts": ${Math.round(Date.now() / 1000)},
  "actor": "agent:trader-01",
  "action": "wallet.spend",
  "resource": "WBTC",
  "cost_usd": 12.50,
  "trace_id": "tr-abc123",
  "signer": "ed25519:org-pubkey…",
  "sig": "base64-signature…"
}`;

type State =
  | { kind: "idle" }
  | { kind: "verifying" }
  | { kind: "ok"; signer: string; offline: boolean }
  | { kind: "fail"; reason: string }
  | { kind: "error"; message: string };

export function ReceiptVerifier() {
  const id = useId();
  const [text, setText] = useState<string>(SAMPLE);
  const [state, setState] = useState<State>({ kind: "idle" });

  const onVerify = async () => {
    setState({ kind: "verifying" });
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (e) {
      setState({
        kind: "error",
        message: `JSON parse failed · ${(e as Error).message}`,
      });
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/api/receipts/verify`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ receipt: parsed }),
      });
      if (r.status === 404) {
        // Backend hasn't shipped — offer offline verification result
        // explicitly labeled as un-checked.
        setState({
          kind: "ok",
          signer: "(offline · daemon route pending)",
          offline: true,
        });
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = (await r.json()) as {
        ok?: boolean;
        verified?: boolean;
        signer?: string;
        reason?: string;
      };
      if (body.verified) {
        setState({
          kind: "ok",
          signer: body.signer ?? "(unknown signer)",
          offline: false,
        });
      } else {
        setState({
          kind: "fail",
          reason: body.reason ?? "signature did not verify",
        });
      }
    } catch (e) {
      setState({
        kind: "error",
        message: (e as Error).message,
      });
    }
  };

  return (
    <section
      id="verify"
      className="rounded-[12px] border border-line/60 bg-bg-1/40 p-5"
    >
      <header className="mb-2 flex items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
          <ShieldCheck
            size={12}
            strokeWidth={1.7}
            aria-hidden
            style={{ color: "var(--brand-cyan)" }}
          />
          <span>verify receipt</span>
        </div>
      </header>
      <BrandHairline variant="static" />

      <label
        htmlFor={`${id}-text`}
        className="mt-4 block font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3"
      >
        paste receipt JSON
      </label>
      <textarea
        id={`${id}-text`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        spellCheck={false}
        className="mt-1.5 w-full resize-y rounded-md border border-line/60 bg-bg-0/60 p-3 font-mono-tech text-[11px] leading-[1.55] text-ink-2 outline-none focus:border-accent"
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={onVerify}
          disabled={state.kind === "verifying" || !text.trim()}
          className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-2/60 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink transition-colors hover:border-accent disabled:opacity-50"
        >
          {state.kind === "verifying" ? (
            <Loader2
              size={12}
              strokeWidth={2}
              className="animate-spin"
              aria-hidden
            />
          ) : (
            <ShieldCheck size={12} strokeWidth={1.7} aria-hidden />
          )}
          <span>
            {state.kind === "verifying" ? "verifying…" : "verify signature"}
          </span>
        </button>

        <button
          type="button"
          onClick={() => {
            setText(SAMPLE);
            setState({ kind: "idle" });
          }}
          className="font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3 transition-colors hover:text-ink"
        >
          reset to sample
        </button>
      </div>

      <div className="mt-4 min-h-[2.5em]">
        {state.kind === "ok" && (
          <p
            className="inline-flex items-start gap-2 rounded-md border px-3 py-2 text-[12px] leading-[1.5]"
            style={{
              borderColor: state.offline
                ? "var(--brand-amber)"
                : "var(--color-success)",
              color: state.offline ? "var(--brand-amber)" : "var(--color-success)",
              background: `color-mix(in srgb, ${state.offline ? "var(--brand-amber)" : "var(--color-success)"} 8%, transparent)`,
            }}
          >
            <CheckCircle2
              size={13}
              strokeWidth={1.7}
              aria-hidden
              className="mt-0.5"
            />
            <span>
              {state.offline
                ? "Backend WIP · cannot verify signature locally."
                : "Signature verified."}
              <br />
              <span className="font-mono-tech text-[10.5px] uppercase tracking-[1.6px] opacity-80">
                signer · {state.signer}
              </span>
            </span>
          </p>
        )}
        {state.kind === "fail" && (
          <p
            className="inline-flex items-start gap-2 rounded-md border px-3 py-2 text-[12px] leading-[1.5]"
            style={{
              borderColor: "var(--color-alert)",
              color: "var(--color-alert)",
              background:
                "color-mix(in srgb, var(--color-alert) 8%, transparent)",
            }}
          >
            <XCircle
              size={13}
              strokeWidth={1.7}
              aria-hidden
              className="mt-0.5"
            />
            <span>
              Signature INVALID.
              <br />
              <span className="font-mono-tech text-[10.5px] uppercase tracking-[1.6px] opacity-80">
                {state.reason}
              </span>
            </span>
          </p>
        )}
        {state.kind === "error" && (
          <p className="inline-flex items-start gap-2 text-[12px] text-rose-200">
            <AlertCircle
              size={12}
              strokeWidth={1.7}
              aria-hidden
              className="mt-0.5"
            />
            <span>{state.message}</span>
          </p>
        )}
      </div>
    </section>
  );
}

export default ReceiptVerifier;
