/**
 * <DiffView /> — line-level JSON diff between `prev` and `next` text.
 *
 * Pure-string algorithm — no external diff library (~12 KB saved).
 * Computes a Longest-Common-Subsequence on lines, then walks the
 * matrix once to emit `added` / `removed` / `unchanged` rows. Good
 * enough for the cockpit's small JSON arg blobs (typically < 30
 * lines); we don't try to do intra-line word-diff.
 *
 * Visual:
 *   - Removed lines    — red prefix `−`, red-tinted bg
 *   - Added lines      — green prefix `+`, green-tinted bg
 *   - Unchanged lines  — grey prefix ` `, neutral
 *
 * No state, no animations heavier than `whileInView` opacity. Drops
 * cleanly into any panel; respects `prefers-reduced-motion` via
 * global CSS.
 */

import { useMemo } from "react";

interface Props {
  prev: string;
  next: string;
  /** Hide the legend/header ribbon if the parent already shows context */
  bare?: boolean;
  /** Max rows to render before "+ N more" tail; protects very long diffs */
  maxRows?: number;
  className?: string;
}

type Row =
  | { kind: "ctx";  text: string; ln: { a: number; b: number } }
  | { kind: "add";  text: string; ln: { b: number } }
  | { kind: "del";  text: string; ln: { a: number } };

export function DiffView({
  prev,
  next,
  bare,
  maxRows = 200,
  className,
}: Props) {
  const rows = useMemo(() => diffLines(prev, next), [prev, next]);

  const adds = rows.filter(r => r.kind === "add").length;
  const dels = rows.filter(r => r.kind === "del").length;
  const truncated = rows.length > maxRows;
  const view = rows.slice(0, maxRows);

  if (rows.length === 0 || (adds === 0 && dels === 0)) {
    return (
      <div
        className={`rounded-md border border-line bg-bg-2/40 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 ${className ?? ""}`}
      >
        no changes
      </div>
    );
  }

  return (
    <div
      className={`overflow-hidden rounded-md border border-line bg-bg-2/30 font-mono text-[11.5px] leading-[1.55] ${className ?? ""}`}
    >
      {!bare && (
        <header className="flex items-center justify-between border-b border-line/70 bg-bg-1/40 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          <span>diff · last invoke vs current</span>
          <span className="flex items-center gap-2.5 tabular-nums">
            <span style={{ color: "var(--color-success)" }}>+{adds}</span>
            <span style={{ color: "var(--color-alert)" }}>−{dels}</span>
            <span>{rows.length} ln</span>
          </span>
        </header>
      )}
      <ol className="overflow-x-auto">
        {view.map((r, i) => (
          <li
            key={i}
            className="grid grid-cols-[44px_18px_1fr] items-baseline px-3 py-px"
            style={rowStyle(r.kind)}
          >
            <span className="select-none text-ink-3 tabular-nums">
              {r.kind === "del"
                ? `${"a" in r.ln ? r.ln.a : ""}` + "  "
                : r.kind === "add"
                  ? "  " + `${"b" in r.ln ? r.ln.b : ""}`
                  : `${(r as Extract<Row, { kind: "ctx" }>).ln.a} ${(r as Extract<Row, { kind: "ctx" }>).ln.b}`}
            </span>
            <span
              aria-hidden
              style={{ color: glyphColor(r.kind) }}
              className="select-none"
            >
              {r.kind === "add" ? "+" : r.kind === "del" ? "−" : " "}
            </span>
            <span className="whitespace-pre text-ink/95">{r.text || " "}</span>
          </li>
        ))}
      </ol>
      {truncated && (
        <footer className="border-t border-line/70 bg-bg-1/40 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          + {rows.length - maxRows} more lines
        </footer>
      )}
    </div>
  );
}

function rowStyle(kind: Row["kind"]): React.CSSProperties {
  if (kind === "add") {
    return {
      background: "color-mix(in srgb, var(--color-success) 8%, transparent)",
    };
  }
  if (kind === "del") {
    return {
      background: "color-mix(in srgb, var(--color-alert) 9%, transparent)",
    };
  }
  return {};
}

function glyphColor(kind: Row["kind"]): string {
  if (kind === "add") return "var(--color-success)";
  if (kind === "del") return "var(--color-alert)";
  return "var(--color-ink-3)";
}

/* ─── LCS-driven line diff ──────────────────────────────────────── */

function diffLines(a: string, b: string): Row[] {
  const A = a.split(/\r?\n/);
  const B = b.split(/\r?\n/);
  const m = A.length;
  const n = B.length;

  // Build LCS length matrix (one row at a time would save memory but
  // arg blobs are tiny). Indexed [i][j] = longest common up to A[i-1]
  // and B[j-1].
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = A[i - 1] === B[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Walk back from (m,n) to (0,0) emitting rows.
  const out: Row[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (A[i - 1] === B[j - 1]) {
      out.push({ kind: "ctx", text: A[i - 1], ln: { a: i, b: j } });
      i--;
      j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      out.push({ kind: "del", text: A[i - 1], ln: { a: i } });
      i--;
    } else {
      out.push({ kind: "add", text: B[j - 1], ln: { b: j } });
      j--;
    }
  }
  while (i > 0) {
    out.push({ kind: "del", text: A[i - 1], ln: { a: i } });
    i--;
  }
  while (j > 0) {
    out.push({ kind: "add", text: B[j - 1], ln: { b: j } });
    j--;
  }
  return out.reverse();
}
