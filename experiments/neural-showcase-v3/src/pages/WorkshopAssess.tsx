/**
 * <WorkshopAssess /> — Wave 88
 *
 * Pre-workshop self-assessment quiz at /workshop/assess. Twelve Likert
 * 1-5 questions across four categories (LLM familiarity, Python
 * scripting, Trading exposure, Audit / compliance). One question per
 * screen, smooth motion transition, progress bar at top. Final screen
 * surfaces a tailored set of pre-reads based on per-category scores.
 *
 * Design conventions:
 *   - Defensive `initial: opacity: 1` on motion wrappers (Wave 70
 *     pattern — keeps the page legible if framer hydrates late).
 *   - LocalStorage persistence under `tars.workshop.assess.draft` so
 *     attendees can resume mid-quiz on a different device or after a
 *     refresh. Cleared when they "Start over".
 *   - Pure FE — no backend write. Email handoff is `mailto:` with a
 *     pre-filled body so attendees mail their own results to anyone
 *     (themselves, the facilitator, their compliance lead).
 *   - i18n strings live in `STRINGS_EN["assess.*"]` so a future locale
 *     re-enable picks them up automatically.
 *
 * Scoring rules (mirrored in the i18n recommendation copy):
 *   - Each category: sum of three 1-5 answers → range 3..15.
 *   - Total: sum of all four categories → range 12..60.
 *   - If a category < 8/15: surface that category's pre-read recommendation.
 *   - If total > 48/60: surface the "fast-track" recommendation as well.
 *   - If no recommendation triggers: surface the "balanced" copy.
 *   - Skipped questions count as 0 toward both category + total.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Mail,
  RefreshCcw,
  RotateCcw,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";
import { Breadcrumbs } from "@/components/Breadcrumbs";

// ── data ────────────────────────────────────────────────────────────

type Category = "llm" | "python" | "trading" | "audit";

interface Question {
  id: string;
  category: Category;
  /** i18n key for the question prompt. */
  promptKey: TKey;
}

// 12 questions — three per category, ordered so the quiz alternates
// difficulty/type and never lingers in one category long enough to feel
// like an exam in that subject.
const QUESTIONS: Question[] = [
  { id: "llm.1",     category: "llm",     promptKey: "assess.q.llm.1" },
  { id: "llm.2",     category: "llm",     promptKey: "assess.q.llm.2" },
  { id: "llm.3",     category: "llm",     promptKey: "assess.q.llm.3" },
  { id: "python.1",  category: "python",  promptKey: "assess.q.python.1" },
  { id: "python.2",  category: "python",  promptKey: "assess.q.python.2" },
  { id: "python.3",  category: "python",  promptKey: "assess.q.python.3" },
  { id: "trading.1", category: "trading", promptKey: "assess.q.trading.1" },
  { id: "trading.2", category: "trading", promptKey: "assess.q.trading.2" },
  { id: "trading.3", category: "trading", promptKey: "assess.q.trading.3" },
  { id: "audit.1",   category: "audit",   promptKey: "assess.q.audit.1" },
  { id: "audit.2",   category: "audit",   promptKey: "assess.q.audit.2" },
  { id: "audit.3",   category: "audit",   promptKey: "assess.q.audit.3" },
];

const CATEGORIES: ReadonlyArray<{
  id: Category;
  labelKey: TKey;
  recKey: TKey;
  accent: string;
}> = [
  { id: "llm",     labelKey: "assess.cat.llm.label",     recKey: "assess.rec.llm",     accent: "var(--brand-indigo)" },
  { id: "python",  labelKey: "assess.cat.python.label",  recKey: "assess.rec.python",  accent: "var(--brand-cyan)" },
  { id: "trading", labelKey: "assess.cat.trading.label", recKey: "assess.rec.trading", accent: "var(--brand-violet)" },
  { id: "audit",   labelKey: "assess.cat.audit.label",   recKey: "assess.rec.audit",   accent: "var(--brand-indigo)" },
];

// 0 = skipped (not yet answered, or explicitly skipped). 1..5 = Likert.
type AnswerMap = Partial<Record<string, 0 | 1 | 2 | 3 | 4 | 5>>;

interface DraftState {
  answers: AnswerMap;
  /** Index into QUESTIONS, or QUESTIONS.length for the results screen. */
  cursor: number;
  /** True once the user has reached the results screen at least once. */
  finished: boolean;
}

const STORAGE_KEY = "tars.workshop.assess.draft";

const EMPTY_DRAFT: DraftState = { answers: {}, cursor: 0, finished: false };

function loadDraft(): DraftState {
  if (typeof localStorage === "undefined") return EMPTY_DRAFT;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_DRAFT;
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed == null) return EMPTY_DRAFT;
    const answers: AnswerMap = {};
    if (parsed.answers && typeof parsed.answers === "object") {
      for (const q of QUESTIONS) {
        const v = (parsed.answers as Record<string, unknown>)[q.id];
        if (typeof v === "number" && v >= 0 && v <= 5) {
          answers[q.id] = v as 0 | 1 | 2 | 3 | 4 | 5;
        }
      }
    }
    const rawCursor = Number(parsed.cursor ?? 0);
    const cursor = Number.isFinite(rawCursor)
      ? Math.max(0, Math.min(QUESTIONS.length, Math.floor(rawCursor)))
      : 0;
    return {
      answers,
      cursor,
      finished: Boolean(parsed.finished),
    };
  } catch {
    return EMPTY_DRAFT;
  }
}

function saveDraft(draft: DraftState): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* private mode — silently ignore */
  }
}

function clearDraft(): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private mode — silently ignore */
  }
}

// ── scoring ─────────────────────────────────────────────────────────

interface ScoreResult {
  byCategory: Record<Category, number>;
  total: number;
  recommendations: TKey[];
}

function score(answers: AnswerMap): ScoreResult {
  const byCategory: Record<Category, number> = {
    llm: 0,
    python: 0,
    trading: 0,
    audit: 0,
  };
  for (const q of QUESTIONS) {
    const v = answers[q.id] ?? 0;
    byCategory[q.category] += v;
  }
  const total =
    byCategory.llm + byCategory.python + byCategory.trading + byCategory.audit;
  const recommendations: TKey[] = [];
  for (const c of CATEGORIES) {
    if (byCategory[c.id] < 8) recommendations.push(c.recKey);
  }
  if (total > 48) recommendations.push("assess.rec.fasttrack");
  if (recommendations.length === 0) recommendations.push("assess.rec.balanced");
  return { byCategory, total, recommendations };
}

// ── small UI helpers ────────────────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label="quiz progress"
      className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-2"
    >
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="absolute left-0 top-0 h-full rounded-full"
        style={{
          background:
            "linear-gradient(90deg, var(--brand-indigo) 0%, var(--brand-violet) 60%, var(--brand-cyan) 100%)",
        }}
      />
    </div>
  );
}

interface LikertScaleProps {
  value: 0 | 1 | 2 | 3 | 4 | 5 | undefined;
  onChange: (v: 1 | 2 | 3 | 4 | 5) => void;
  /** End-anchor labels under the scale (e.g. "never heard" / "could teach it"). */
  startLabel: string;
  endLabel: string;
}

function LikertScale({ value, onChange, startLabel, endLabel }: LikertScaleProps) {
  return (
    <div className="space-y-3">
      <div
        role="radiogroup"
        aria-label="likert 1 to 5"
        className="grid grid-cols-5 gap-2"
      >
        {[1, 2, 3, 4, 5].map((n) => {
          const selected = value === n;
          return (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(n as 1 | 2 | 3 | 4 | 5)}
              className={`group relative flex min-h-[56px] items-center justify-center rounded-md border font-display text-[20px] tracking-[-0.005em] transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)] ${
                selected
                  ? "border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 text-ink"
                  : "border-line bg-bg-1/50 text-ink-2 hover:border-ink-3 hover:text-ink"
              }`}
            >
              {n}
            </button>
          );
        })}
      </div>
      <div className="flex justify-between font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
        <span>1 · {startLabel}</span>
        <span>5 · {endLabel}</span>
      </div>
    </div>
  );
}

// ── page ────────────────────────────────────────────────────────────

export function WorkshopAssess() {
  const t = useT();
  useDocumentMeta({
    title: "Workshop self-assessment · TARS",
    description:
      "Twelve-question pre-workshop self-assessment. Get a tailored pre-read so you arrive on Day 1 ready to ship.",
      ogImage: "https://tars.meeet.world/og-workshop.svg",
  });

  const [draft, setDraft] = useState<DraftState>(() => loadDraft());

  useEffect(() => {
    saveDraft(draft);
  }, [draft]);

  const total = QUESTIONS.length;
  const cursor = Math.max(0, Math.min(total, draft.cursor));
  const isResults = cursor >= total;
  const current = isResults ? null : QUESTIONS[cursor];

  const setAnswer = useCallback(
    (id: string, v: 1 | 2 | 3 | 4 | 5) => {
      setDraft((prev) => ({
        ...prev,
        answers: { ...prev.answers, [id]: v },
      }));
    },
    [],
  );

  const advance = useCallback(() => {
    setDraft((prev) => {
      const next = Math.min(total, prev.cursor + 1);
      return {
        ...prev,
        cursor: next,
        finished: prev.finished || next >= total,
      };
    });
  }, [total]);

  const back = useCallback(() => {
    setDraft((prev) => ({ ...prev, cursor: Math.max(0, prev.cursor - 1) }));
  }, []);

  const skip = useCallback(() => {
    if (!current) return;
    setDraft((prev) => ({
      ...prev,
      answers: { ...prev.answers, [current.id]: 0 },
      cursor: Math.min(total, prev.cursor + 1),
      finished: prev.finished || prev.cursor + 1 >= total,
    }));
  }, [current, total]);

  const reset = useCallback(() => {
    clearDraft();
    setDraft(EMPTY_DRAFT);
  }, []);

  const result = useMemo(() => score(draft.answers), [draft.answers]);

  // Pre-fill mailto: body so attendees can fire off results to
  // themselves / facilitator / compliance lead. Subject line includes
  // total so it threads usefully if multiple attendees from the same
  // org email the same address.
  const mailtoHref = useMemo(() => {
    const subject = `TARS workshop self-assessment — ${result.total}/60`;
    const lines: string[] = [
      "Pre-workshop self-assessment results",
      "",
    ];
    for (const c of CATEGORIES) {
      lines.push(`${t(c.labelKey)}: ${result.byCategory[c.id]} / 15`);
    }
    lines.push("");
    lines.push(`Total: ${result.total} / 60`);
    lines.push("");
    lines.push("Recommended pre-work:");
    for (const recKey of result.recommendations) {
      lines.push(`  - ${t(recKey)}`);
    }
    lines.push("");
    lines.push("Computed at https://tars.meeet.world/workshop/assess");
    const body = lines.join("\n");
    return `mailto:?subject=${encodeURIComponent(
      subject,
    )}&body=${encodeURIComponent(body)}`;
  }, [result, t]);

  return (
    <div className="relative min-h-[calc(100vh-72px)] overflow-hidden bg-bg-0 text-ink">
      {/* Ambient backdrop — same triad as the rest of the workshop
          surface. Tuned softer so the quiz feels like a worksheet,
          not a sales page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 50% 40% at 12% 6%, rgba(99,102,241,0.07) 0%, transparent 60%),
            radial-gradient(ellipse 45% 35% at 88% 92%, rgba(139,92,246,0.07) 0%, transparent 60%)
          `,
        }}
      />

      <article className="mx-auto max-w-[640px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        {/* breadcrumbs */}
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <Breadcrumbs
            items={[
              { label: "Home", to: "/" },
              { label: "Workshop", to: "/workshop" },
              { label: t("assess.crumb") },
            ]}
          />
        </motion.div>

        {/* hero */}
        <motion.header
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="mb-10 mt-8 grid grid-cols-1 gap-3 border-b border-line pb-8"
        >
          <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <span style={{ color: "var(--brand-indigo)" }}>W88</span>
            <span>{t("assess.eyebrow")}</span>
          </div>
          <h1
            className="max-w-[24ch] font-display font-medium leading-[0.98] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2rem, 4.6vw, 3.2rem)" }}
          >
            {t("assess.title")}
          </h1>
          <p className="mt-1 max-w-[60ch] text-[14.5px] leading-[1.65] text-ink-2">
            {t("assess.subtitle")}
          </p>
        </motion.header>

        {/* progress + step counter (hidden on results screen) */}
        {!isResults && (
          <div className="mb-8 space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2">
                {t("assess.progress", {
                  n: cursor + 1,
                  total,
                })}
              </span>
              <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                {Math.round(((cursor + 1) / total) * 100)}%
              </span>
            </div>
            <ProgressBar value={cursor + 1} max={total} />
          </div>
        )}

        {/* question card OR results card — same panel chrome */}
        <div className="rounded-md border border-line bg-bg-1/40 p-6 backdrop-blur-sm md:p-8">
          <AnimatePresence mode="wait">
            {!isResults && current ? (
              <QuestionCard
                key={current.id}
                question={current}
                value={draft.answers[current.id]}
                onAnswer={(v) => {
                  setAnswer(current.id, v);
                  // Auto-advance after a short beat so attendees can
                  // course-correct with Back if they mis-tap. 220ms
                  // matches the panel transition duration so the
                  // motion feels intentional rather than rushed.
                  window.setTimeout(advance, 220);
                }}
                onSkip={skip}
                t={t}
              />
            ) : (
              <ResultsCard
                key="results"
                result={result}
                mailtoHref={mailtoHref}
                onReset={reset}
                t={t}
              />
            )}
          </AnimatePresence>
        </div>

        {/* nav row — Back / Next visible only mid-quiz */}
        {!isResults && (
          <div className="mt-6 flex items-center justify-between">
            <button
              type="button"
              onClick={back}
              disabled={cursor === 0}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-line bg-bg-1/50 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
            >
              <ArrowLeft size={12} aria-hidden />
              {t("assess.back")}
            </button>
            <button
              type="button"
              onClick={advance}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-sm border border-line bg-bg-1/50 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors hover:border-[var(--brand-indigo)] hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
            >
              {t("assess.next")}
              <ArrowRight size={12} aria-hidden />
            </button>
          </div>
        )}
      </article>
    </div>
  );
}

// ── question card ───────────────────────────────────────────────────

interface QuestionCardProps {
  question: Question;
  value: 0 | 1 | 2 | 3 | 4 | 5 | undefined;
  onAnswer: (v: 1 | 2 | 3 | 4 | 5) => void;
  onSkip: () => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

function QuestionCard({
  question,
  value,
  onAnswer,
  onSkip,
  t,
}: QuestionCardProps) {
  const categoryMeta = CATEGORIES.find((c) => c.id === question.category);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-7"
    >
      {categoryMeta && (
        <div className="flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
          <span
            aria-hidden
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: categoryMeta.accent }}
          />
          {t(categoryMeta.labelKey)}
        </div>
      )}
      <h2 className="font-display text-[22px] font-medium leading-[1.25] tracking-[-0.005em] text-ink md:text-[26px]">
        {t(question.promptKey)}
      </h2>
      <LikertScale
        value={value}
        onChange={onAnswer}
        startLabel={t("assess.scale.never")}
        endLabel={t("assess.scale.teach")}
      />
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onSkip}
          className="font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3 underline-offset-4 transition-colors hover:text-ink hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
        >
          {t("assess.skip")} →
        </button>
      </div>
    </motion.div>
  );
}

// ── results card ────────────────────────────────────────────────────

interface ResultsCardProps {
  result: ScoreResult;
  mailtoHref: string;
  onReset: () => void;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
}

function ResultsCard({ result, mailtoHref, onReset, t }: ResultsCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-8"
    >
      <header>
        <div className="mb-2 flex items-center gap-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
          <CheckCircle2
            size={12}
            aria-hidden
            style={{ color: "var(--brand-cyan)" }}
          />
          done · score below
        </div>
        <h2 className="font-display text-[26px] font-medium leading-tight tracking-[-0.01em] text-ink">
          {t("assess.results.title")}
        </h2>
        <p className="mt-2 max-w-[60ch] text-[14px] leading-[1.55] text-ink-2">
          {t("assess.results.subtitle")}
        </p>
      </header>

      {/* Per-category bars */}
      <ul className="space-y-3">
        {CATEGORIES.map((c) => {
          const v = result.byCategory[c.id];
          const pct = (v / 15) * 100;
          return (
            <li key={c.id} className="space-y-1.5">
              <div className="flex items-baseline justify-between font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink-2">
                <span>{t(c.labelKey)}</span>
                <span className="text-ink">
                  {v}
                  <span className="text-ink-3"> / 15</span>
                </span>
              </div>
              <div
                role="meter"
                aria-valuenow={v}
                aria-valuemin={0}
                aria-valuemax={15}
                aria-label={t(c.labelKey)}
                className="relative h-1.5 w-full overflow-hidden rounded-full bg-bg-2"
              >
                <div
                  className="absolute left-0 top-0 h-full rounded-full"
                  style={{
                    width: `${pct}%`,
                    background: c.accent,
                  }}
                />
              </div>
            </li>
          );
        })}
      </ul>

      {/* Total */}
      <div className="rounded-md border border-line bg-bg-1/50 p-4">
        <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
          {t("assess.results.total", { score: result.total })}
        </div>
        <div
          className="mt-1 font-display font-medium leading-none tracking-[-0.01em] text-ink"
          style={{ fontSize: "clamp(2rem, 5vw, 3rem)" }}
        >
          {result.total}
          <span className="text-[20px] text-ink-3"> / 60</span>
        </div>
      </div>

      {/* Recommendations */}
      <section aria-labelledby="assess-rec-heading">
        <h3
          id="assess-rec-heading"
          className="mb-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2"
        >
          {t("assess.results.recommendations")}
        </h3>
        <ul className="space-y-2">
          {result.recommendations.map((recKey) => (
            <li
              key={recKey}
              className="flex items-start gap-3 rounded-md border border-line bg-bg-1/50 p-3"
            >
              <span
                aria-hidden
                className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full"
                style={{
                  background:
                    recKey === "assess.rec.fasttrack"
                      ? "var(--brand-cyan)"
                      : recKey === "assess.rec.balanced"
                        ? "var(--brand-violet)"
                        : "var(--brand-indigo)",
                }}
              />
              <p className="text-[14px] leading-[1.55] text-ink">
                {t(recKey)}
              </p>
            </li>
          ))}
        </ul>
      </section>

      {/* CTAs */}
      <div className="flex flex-wrap gap-3 pt-2">
        <Link
          to="/workshop"
          className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors hover:bg-[var(--brand-indigo)]/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
        >
          <ArrowRight size={13} strokeWidth={1.7} aria-hidden />
          {t("assess.cta.start")}
        </Link>
        <a
          href={mailtoHref}
          className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-line bg-bg-1 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors hover:border-[var(--brand-cyan)] focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-cyan)]"
        >
          <Mail size={13} strokeWidth={1.7} aria-hidden />
          {t("assess.cta.email")}
        </a>
        <Link
          to="/workshop/materials"
          className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-line bg-bg-1 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors hover:border-[var(--brand-violet)] focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-violet)]"
        >
          <RefreshCcw size={13} strokeWidth={1.7} aria-hidden />
          {t("assess.cta.materials")}
        </Link>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-line bg-bg-1 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink-2 transition-colors hover:border-alert hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-alert"
        >
          <RotateCcw size={13} strokeWidth={1.7} aria-hidden />
          {t("assess.reset")}
        </button>
      </div>
    </motion.div>
  );
}

// Suppress unused-import warning when ReactNode is referenced only for
// future extensibility (kept so the helper signatures can grow without
// re-importing).
export type _ReactNodeUnused = ReactNode;

export default WorkshopAssess;
