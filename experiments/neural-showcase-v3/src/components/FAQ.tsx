import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { Plus } from "lucide-react";
import { SectionHead } from "@/components/SectionHead";
import { CornerFrame } from "@/components/Glyphs";
import { useT } from "@/lib/i18n";

interface QA {
  q: string;
  a: string;
}

// Curated subset of docs/FAQ.md — most-asked across categories.
// Keep the page lean (≤ 14 entries); deep questions link to /faq full text.
const FAQS: QA[] = [
  {
    q: "Where does my data live?",
    a: "On your machine. TARS is local-first — by default the SQLite memory ledger, vault, attachment chunks, embeddings, and signed receipt log all sit under ~/.tars. Cloud sync is opt-in (Pro tier and above) and end-to-end encrypted with a key derived from your Solana signature. We never see your prompts, your files, or your model API keys.",
  },
  {
    q: "What exactly leaves my machine when?",
    a: "Free tier with no opt-ins: nothing — prompts, files, chat history, embeddings all stay local. When you opt in: encrypted ciphertext blobs to meeet.world (Pro+ sync), and cloud LLM API calls when you select a cloud voice (Anthropic / OpenAI etc., governed by their DPAs). Always: outbound DNS for the skills you connect.",
  },
  {
    q: "Does it work offline?",
    a: "Mostly yes. The Mac Operator, Memory ledger, Code RAG, and Daily Briefing run fully offline against a local model (Ollama wired out of the box). Cloud features that need internet — T2T deals, $MEEET earn, council voting against frontier APIs — pause and resume gracefully when connection returns.",
  },
  {
    q: "Is it really open source?",
    a: "Yes. The local agent core is MIT-licensed on GitHub, including all 4 packs, the Mac Operator sandbox scripts, and the receipt-anchoring logic. Closed-source pieces are limited to the meeet.world relayer and the marketplace billing service — both replaceable.",
  },
  {
    q: "What's actually in Free?",
    a: "Single-device install, unlimited usage on-device, all 4 packs, Mac Operator (sandboxed file moves / summaries / web fetch), memory ledger, RAG citations, BYO LLM keys (8 providers), local single-voice council, MIT license. Not in Free: cloud sync, T2T deals, AI Clone training, two-voice council, $MEEET earn.",
  },
  {
    q: "What does Pro unlock for $19/mo?",
    a: "Cloud sync across devices, two-voice council with confidence + agreement, T2T deals (50/month), AI Clone, $MEEET earn, $10/mo cloud LLM budget, priority support. BYO-key Pro is $9/mo (no cloud budget — bring your own keys).",
  },
  {
    q: "What if I burn through my cloud budget?",
    a: "At 80% used the cockpit shows a yellow strip. At 100%, cloud LLM calls return 402 Payment Required and the UI offers an upgrade or BYO-key toggle. Your local model, memory, and Mac actions keep working — only cloud gets throttled.",
  },
  {
    q: "Do I need a Solana wallet?",
    a: "No for Free. Pro+ can sign in with email magic-link or wallet — your choice. Wallet is only required to (a) earn $MEEET, (b) join T2T deals, or (c) skip email and sign in with a wallet signature. Phantom, Backpack, Solflare, Glow tested.",
  },
  {
    q: "What's the council and why does it matter?",
    a: "Every action in TARS — sending a message, running a playbook, moving files — passes through a two-voice deliberation. Two LLMs each propose a stance with confidence and rationale. You see both. On low agreement, the operator confirms before anything destructive runs. It's the structural guardrail competitors don't have.",
  },
  {
    q: "Which LLMs are supported?",
    a: "Eight, BYO key for Free / Pro·BYO: Anthropic Claude, OpenAI GPT, Google Gemini, xAI Grok, Mistral, DeepSeek, Llama via Together, Ollama (any local model). Switch any time from the cockpit; cost is logged per-call to the local ledger.",
  },
  {
    q: "What's the sandboxing model for Mac actions?",
    a: "Every destructive Mac action runs inside an Apple sandbox-exec profile that whitelists exactly the paths and network destinations the action needs — nothing broader. Reversible operations get a 10-minute undo. Irreversible operations require two-voice council + operator confirm.",
  },
  {
    q: "What's recovery seed?",
    a: "Generated on first install, displayed exactly once: 24-word BIP-39. Print it, store offline. Lets you re-pair from a new host if your machine is lost. Without it, ciphertext blobs in meeet.world become unreadable — by design. We cannot help recover them.",
  },
  {
    q: "How is this different from Cursor?",
    a: "Cursor is an IDE — lives inside VS Code, codes for you. TARS is an agent — lives at the OS level, runs the file system, watches calendar and mail, acts across apps. Complementary: many users run Cursor for code and TARS for everything else.",
  },
  {
    q: "Can I cancel? Is there a refund?",
    a: "Yes to both. Cancel anytime from the cockpit Settings → Billing — your data stays on-device since it was always there. 14-day no-questions refund on Pro and Business. Lifetime is non-refundable after 14 days because the founders' $MEEET allocation drops immediately.",
  },
];

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const t = useT();

  return (
    <section
      id="faq"
      className="relative z-20 mx-auto max-w-[1280px] px-8 py-28 md:px-14 md:py-36"
    >
      <SectionHead
        num="09"
        tag={t("faq.tag")}
        title={t("faq.title")}
        description={t("faq.description")}
      />

      <div className="relative overflow-hidden rounded-[14px] border border-line bg-bg-1">
        <CornerFrame />
        <div
          aria-hidden
          className="h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #06B6D4 30%, #6366F1 50%, #8B5CF6 70%, transparent 100%)",
          }}
        />

        <ul className="divide-y divide-line">
          {FAQS.map((qa, i) => {
            const isOpen = open === i;
            const buttonId = `faq-button-${i}`;
            const panelId = `faq-panel-${i}`;
            return (
              <li key={i}>
                <button
                  id={buttonId}
                  type="button"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  // Terse action label — screen readers will already read the
                  // visible question text inside the button (line 127-129),
                  // so the label only needs to clarify what the affordance
                  // *does*. Echoing `qa.q` here would make SR repeat the
                  // question twice. WCAG 2.1 AA · 2.4.4 Link Purpose.
                  aria-label={isOpen ? "Collapse answer" : "Expand answer"}
                  className="flex w-full items-center gap-5 px-6 py-5 text-left transition-colors duration-150 hover:bg-bg-2/40 md:px-10 md:py-6"
                >
                  <span
                    className="font-mono-tech text-[10px] uppercase tracking-[2.6px] tabular-nums"
                    style={{ color: isOpen ? "#6366F1" : "var(--color-ink-3)" }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1 font-display text-[16px] leading-[1.35] tracking-[0.01em] text-ink md:text-[18px]">
                    {qa.q}
                  </span>
                  <span
                    className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-full transition-all duration-300"
                    style={{
                      background: isOpen
                        ? "color-mix(in srgb, #6366F1 14%, transparent)"
                        : "var(--color-bg-2)",
                      color: isOpen ? "#6366F1" : "var(--color-ink-2)",
                      transform: isOpen ? "rotate(45deg)" : "rotate(0deg)",
                      boxShadow: isOpen
                        ? "inset 0 0 0 1px #6366F155, 0 0 16px rgba(99,102,241,0.25)"
                        : "inset 0 0 0 1px var(--color-line-strong)",
                    }}
                    aria-hidden="true"
                  >
                    <Plus size={14} strokeWidth={2.2} />
                  </span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      id={panelId}
                      // `role="region"` + `aria-labelledby` ties the answer
                      // panel to its question — assistive tech announces
                      // "answer region for [question]" when focus enters.
                      role="region"
                      aria-labelledby={buttonId}
                      key="panel"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                      className="overflow-hidden"
                    >
                      <div className="grid grid-cols-[auto_1fr] gap-5 px-6 pb-6 md:px-10 md:pb-8">
                        <span aria-hidden className="w-[36px]" />
                        <p className="max-w-[64ch] text-[14px] leading-[1.7] text-ink-2">
                          {qa.a}
                        </p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </li>
            );
          })}
        </ul>

        <div className="grid items-center gap-3 border-t border-line px-6 py-5 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 md:grid-cols-[1fr_auto_auto] md:gap-6 md:px-10">
          <span>{t("faq.summary")}</span>
          <a
            href="https://github.com/meeet-world/tars/blob/main/docs/FAQ.md"
            target="_blank"
            rel="noopener"
            className="inline-flex items-center gap-2 text-ink-2 transition-colors hover:text-ink"
          >
            {t("faq.link.full")} <span aria-hidden>→</span>
          </a>
          <a
            href="https://discord.gg/meeet"
            className="inline-flex items-center gap-2 text-ink transition-colors hover:text-accent"
          >
            {t("faq.link.discord")} <span aria-hidden>→</span>
          </a>
        </div>
      </div>
    </section>
  );
}
