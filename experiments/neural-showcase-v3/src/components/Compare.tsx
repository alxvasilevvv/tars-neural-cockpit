import { motion } from "framer-motion";
import { Check, X, Minus } from "lucide-react";
import { SectionHead } from "@/components/SectionHead";
import { CornerFrame } from "@/components/Glyphs";
import { useT, type TKey } from "@/lib/i18n";

/**
 * Compare — feature matrix TARS vs Cursor vs Claude Desktop.
 *
 * Honest framing: Cursor wins at code-IDE depth, Claude Desktop wins
 * at Anthropic-only chat polish. TARS wins on local-first, multi-LLM
 * council, $MEEET economy, T2T, and Mac operator. Highlight only those.
 */

type Mark = "yes" | "no" | "partial";

interface Row {
  feature: string;
  hint?: string;
  cells: [Mark, Mark, Mark]; // [tars, cursor, claudeDesktop]
}

const COLS: { key: string; name: string; accent: string; noteKey: TKey }[] = [
  { key: "tars",   name: "TARS",            accent: "#6366F1",            noteKey: "compare.col.tars.note" },
  { key: "cursor", name: "Cursor",          accent: "var(--color-ink-2)", noteKey: "compare.col.cursor.note" },
  { key: "claude", name: "Claude Desktop",  accent: "var(--color-ink-2)", noteKey: "compare.col.claude.note" },
];

const ROWS: Row[] = [
  {
    feature: "Local-first install",
    hint: "Runs on your machine, your data never leaves the device by default.",
    cells: ["yes", "partial", "no"],
  },
  {
    feature: "Multi-LLM council",
    hint: "Two voices vote on every action — Anthropic + OpenAI side by side.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "Bring-your-own keys (8+ LLMs)",
    hint: "Claude, GPT, Gemini, Grok, Ollama, Mistral, DeepSeek, Llama.",
    cells: ["yes", "yes", "no"],
  },
  {
    feature: "Mac Operator (file/web/system actions)",
    hint: "Sandboxed sandbox-exec. Real moves, signed receipts, undo within 10 min.",
    cells: ["yes", "no", "partial"],
  },
  {
    feature: "Domain packs (traders / business / entrepreneur / science)",
    hint: "Same neural core, four crafts. Swap by clicking a tab.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "Persistent memory ledger",
    hint: "SQLite-backed, queryable, exportable, signed receipts per write.",
    cells: ["yes", "partial", "partial"],
  },
  {
    feature: "Background awareness (always-on)",
    hint: "Headless daemon watching calendar, mail, repos — wakes on triggers.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "T2T — agent-to-agent deals",
    hint: "Your agent talks to my agent. Signed handshake, off-chain escrow.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "AI Clone (your tone, your rhythm)",
    hint: "Per-user style learning. Drafts in your voice, not the model's.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "$MEEET earn while agent works",
    hint: "Receipt → reputation graph → on-chain reward. No subscription required for free tier.",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "Code RAG (sqlite-vec)",
    hint: "Index your repos, ask questions across files.",
    cells: ["yes", "yes", "partial"],
  },
  {
    feature: "MCP support",
    hint: "Both as server (expose skills) and client (consume MCP tools).",
    cells: ["yes", "partial", "yes"],
  },
  {
    feature: "Open source (MIT)",
    cells: ["yes", "no", "no"],
  },
  {
    feature: "Solana magic-link login",
    hint: "Sign in with wallet. No email, no password.",
    cells: ["yes", "no", "no"],
  },
];

function MarkCell({ mark, accent }: { mark: Mark; accent: string }) {
  if (mark === "yes") {
    return (
      <span
        className="grid h-7 w-7 place-items-center rounded-full"
        style={{
          background: `color-mix(in srgb, ${accent} 12%, transparent)`,
          color: accent,
          boxShadow: `inset 0 0 0 1px ${accent}55`,
        }}
        aria-label="supported"
      >
        <Check size={14} strokeWidth={2.4} />
      </span>
    );
  }
  if (mark === "partial") {
    return (
      <span
        className="grid h-7 w-7 place-items-center rounded-full text-ink-2"
        style={{
          background: "var(--color-bg-2)",
          boxShadow: "inset 0 0 0 1px var(--color-line-strong)",
        }}
        aria-label="partial"
      >
        <Minus size={14} strokeWidth={2.2} />
      </span>
    );
  }
  return (
    <span
      className="grid h-7 w-7 place-items-center rounded-full text-ink-3"
      aria-label="not supported"
    >
      <X size={13} strokeWidth={2} />
    </span>
  );
}

export function Compare() {
  const t = useT();
  return (
    <section
      id="compare"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-36"
    >
      <SectionHead
        num="07"
        tag={t("compare.tag")}
        title={t("compare.title")}
        description={t("compare.description")}
      />

      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1">
        <CornerFrame />
        {/* Hairline accent */}
        <div
          aria-hidden
          className="h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        {/* Mobile-friendly horizontal scroll wrapper */}
        <div className="overflow-x-auto">
          <table className="min-w-[640px] w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line">
                <th
                  scope="col"
                  className="px-6 py-5 text-left font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3 md:px-8"
                >
                  {t("compare.col.header")}
                </th>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    className="px-3 py-5 text-center font-mono-tech text-[10px] uppercase tracking-[2.6px] md:px-6"
                  >
                    <div
                      className="font-display text-[15px] tracking-[0.04em]"
                      style={{ color: c.accent }}
                    >
                      {c.name}
                    </div>
                    <div className="mt-1 text-[9px] tracking-[2.4px] text-ink-3">
                      {t(c.noteKey)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row, i) => (
                <motion.tr
                  key={row.feature}
                  initial={{ opacity: 0, y: 6 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-40px" }}
                  transition={{
                    duration: 0.4,
                    delay: Math.min(i * 0.025, 0.3),
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="border-b border-line last:border-b-0 hover:bg-bg-2/40"
                >
                  <td className="px-6 py-4 md:px-8">
                    <div className="text-[13.5px] leading-tight text-ink">
                      {row.feature}
                    </div>
                    {row.hint && (
                      <div className="mt-1 max-w-[42ch] text-[11.5px] leading-[1.5] text-ink-3">
                        {row.hint}
                      </div>
                    )}
                  </td>
                  {row.cells.map((mark, ci) => {
                    const col = COLS[ci];
                    const isTars = ci === 0;
                    return (
                      <td
                        key={ci}
                        className="px-3 py-4 text-center md:px-6"
                        style={{
                          background: isTars
                            ? "color-mix(in srgb, #6366F1 4%, transparent)"
                            : undefined,
                        }}
                      >
                        <div className="inline-flex">
                          <MarkCell mark={mark} accent={col.accent} />
                        </div>
                      </td>
                    );
                  })}
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Footer note */}
        <div className="grid items-center gap-3 border-t border-line px-6 py-4 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 md:grid-cols-[1fr_auto] md:px-8">
          <span>{t("compare.footer.disclaimer")}</span>
          <span style={{ color: "var(--color-meeet-violet, #8B5CF6)" }}>
            {t("compare.footer.source")}
          </span>
        </div>
      </div>
    </section>
  );
}
