// SYNC: claude-w108-perf
import type { ReceiptIntegrityEnvelope } from "./types";

interface Props {
  data?: ReceiptIntegrityEnvelope;
}

function fmtTs(ts?: number | null): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  } catch {
    return String(ts);
  }
}

export function ReceiptIntegrityCard({ data }: Props) {
  if (!data || !data.available) {
    return (
      <div className="rounded-lg border border-line bg-bg-1/40 p-4">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">Receipts</h3>
        <p className="mt-3 text-[12px] text-ink-3">
          {data?.reason === "disabled"
            ? "Receipt store disabled (set TARS_RECEIPT_STORE=enabled)."
            : "No receipt data available."}
        </p>
      </div>
    );
  }
  const valid = data.chain_valid;
  return (
    <div className="rounded-lg border border-line bg-bg-1/40 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2">
          Receipt chain · {data.day_iso}
        </h3>
        <span
          className={`rounded px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1.5px] ${
            valid ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"
          }`}
        >
          {valid ? "chain valid" : "chain broken"}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
        <div className="rounded bg-bg-0/60 px-2 py-2">
          <div className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">Today</div>
          <div className="mt-1 font-mono-tech text-[14px] tabular-nums text-ink">
            {data.today_count ?? 0} receipts
          </div>
        </div>
        <div className="rounded bg-bg-0/60 px-2 py-2">
          <div className="font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3">Anchored</div>
          <div className="mt-1 font-mono-tech text-[12px] text-ink">
            {data.anchored_to_solana ? "yes (Solana)" : "not yet"}
          </div>
        </div>
      </div>
      <p className="mt-2 text-[10px] text-ink-3">
        Merkle root: <span className="font-mono-tech text-ink-2">{data.merkle_root || "—"}</span>
      </p>
      <p className="mt-1 text-[10px] text-ink-3">
        Last anchor: <span className="text-ink-2">{fmtTs(data.last_anchor_at)}</span>
      </p>
    </div>
  );
}
