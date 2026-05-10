/**
 * <WorkshopROI /> — Wave 84
 *
 * Live ROI calculator at `/workshop/roi`. Fund partners use this on
 * stage during the workshop to compute the time + dollars they'd save
 * by automating with TARS. Real working calculator, not a mock —
 * every metric updates as the operator drags a slider, and the
 * "Generate memo" button opens a print-friendly view (Cmd+P → PDF).
 *
 * Design conventions:
 *   - Defensive `initial: opacity: 1` on motion wrappers (Wave 70
 *     pattern — keeps the page legible if framer hydrates late).
 *   - Pure math lives in `src/lib/roi.ts` so the formulas are unit-
 *     testable without React.
 *   - Cmd+K accessible via `<GlobalCommandPalette />` entry registered
 *     in `src/components/GlobalCommandPalette.tsx`.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Mail, Printer, Calculator, ChevronRight } from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import {
  computeRoi,
  formatHours,
  formatPercent,
  formatUsd,
  formatWeeks,
  HOURLY_RATE_PRESETS,
  ROI_PRESETS,
  TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH,
  type RoiInput,
} from "@/lib/roi";

/**
 * Animated count-up for big-number displays. Cheap rAF loop, settles
 * within ~360ms. Re-targets when `value` changes mid-flight (i.e. the
 * operator drags a slider) so we never appear "behind" the input.
 */
function useCountUp(value: number, durationMs = 360): number {
  const [shown, setShown] = useState<number>(value);
  const startRef = useRef<number>(value);
  const frameRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  useEffect(() => {
    if (!Number.isFinite(value)) {
      setShown(value);
      return;
    }
    startRef.current = shown;
    startedAtRef.current =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    const from = startRef.current;
    const to = value;

    const step = () => {
      const now =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const elapsed = now - startedAtRef.current;
      const t = Math.min(1, elapsed / durationMs);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(from + (to - from) * eased);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(step);
      } else {
        frameRef.current = null;
      }
    };
    if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    };
    // intentional: only re-target on value change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs]);

  return shown;
}

interface MetricCardProps {
  label: string;
  display: string;
  accent: string;
  /** Underline detail under the big number (e.g. "$ saved / wk"). */
  sub?: string;
}

function MetricCard({ label, display, accent, sub }: MetricCardProps) {
  return (
    <div
      className="rounded-md border border-line bg-bg-1/50 p-5 backdrop-blur-sm"
      style={{
        borderTopColor: accent,
        borderTopWidth: 2,
      }}
    >
      <div className="mb-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
        {label}
      </div>
      <div
        className="font-display font-medium leading-[1] tracking-[-0.01em] text-ink"
        style={{ fontSize: "clamp(1.6rem, 3.2vw, 2.4rem)" }}
      >
        {display}
      </div>
      {sub && (
        <div className="mt-1.5 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
          {sub}
        </div>
      )}
    </div>
  );
}

interface SliderRowProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (v: number) => void;
  /** Optional extra render under the slider — e.g. preset buttons. */
  children?: React.ReactNode;
}

function SliderRow({
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  onChange,
  children,
}: SliderRowProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <label className="font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2">
          {label}
        </label>
        <span className="font-display text-[15px] tracking-[-0.005em] text-ink">
          {value.toLocaleString("en-US")}
          {unit && (
            <span className="ml-1 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
              {unit}
            </span>
          )}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) =>
          onChange(Number(e.target.value))
        }
        aria-label={label}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-bg-2 accent-[var(--brand-indigo)]"
      />
      {children}
    </div>
  );
}

const STORAGE_KEY = "tars-workshop-roi-input-v1";

function loadInitial(): RoiInput {
  // ROI_PRESETS[1] is the "mid fund" baseline — sane default for the
  // workshop demo when no localStorage value exists yet.
  const fallback = ROI_PRESETS[1].input;
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed == null) return fallback;
    return {
      teamSize: Number(parsed.teamSize ?? fallback.teamSize),
      hourlyRate: Number(parsed.hourlyRate ?? fallback.hourlyRate),
      hoursPerWeek: Number(parsed.hoursPerWeek ?? fallback.hoursPerWeek),
      automationRate: Number(parsed.automationRate ?? fallback.automationRate),
    };
  } catch {
    return fallback;
  }
}

function saveInput(input: RoiInput) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(input));
  } catch {
    /* private mode — silently ignore */
  }
}

export function WorkshopROI() {
  const t = useT();
  useDocumentMeta({
    title: "Workshop ROI calculator · TARS",
    description:
      "Compute time + dollars saved by automating with TARS. Live calculator built for fund partners during the algorithmic workshop.",
  });

  const [input, setInput] = useState<RoiInput>(() => loadInitial());

  useEffect(() => {
    saveInput(input);
  }, [input]);

  const result = useMemo(() => computeRoi(input), [input]);

  // Animated displays — count-up softens the slider drag.
  const hoursAnim = useCountUp(result.hoursSavedPerWeek);
  const savingAnim = useCountUp(result.annualSavingUsd);
  const costAnim = useCountUp(result.annualTarsCostUsd);
  const roiAnim = useCountUp(result.netRoiPercent);
  const paybackAnim = useCountUp(result.paybackWeeks);

  const setField = useCallback(
    <K extends keyof RoiInput>(key: K, value: RoiInput[K]) => {
      setInput((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const applyPreset = useCallback((preset: RoiInput) => {
    setInput(preset);
  }, []);

  // mailto: with a pre-filled subject + body. Operator can swap in
  // their personal address; the body line-wraps cleanly in Mail.app
  // and Gmail web.
  const mailtoHref = useMemo(() => {
    const subject = `TARS ROI estimate — ${input.teamSize} seats, ${formatPercent(result.netRoiPercent)} year-1 ROI`;
    const lines = [
      `Team size: ${input.teamSize}`,
      `Hourly rate: $${input.hourlyRate}/hr`,
      `Hours/week on automatable work: ${input.hoursPerWeek}`,
      `Automation rate (TARS handles): ${Math.round(input.automationRate * 100)}%`,
      "",
      `Hours saved / week: ${formatHours(result.hoursSavedPerWeek)}`,
      `Annual saving: ${formatUsd(result.annualSavingUsd)}`,
      `TARS Business cost (annual): ${formatUsd(result.annualTarsCostUsd)}`,
      `Net ROI year 1: ${formatPercent(result.netRoiPercent)}`,
      `Payback period: ${formatWeeks(result.paybackWeeks)}`,
      "",
      "Computed at https://tars.meeet.world/workshop/roi",
    ];
    const body = lines.join("\n");
    return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }, [input, result]);

  const onPrint = useCallback(() => {
    if (typeof window !== "undefined") window.print();
  }, []);

  return (
    <div className="relative min-h-[calc(100vh-72px)] overflow-hidden bg-bg-0 text-ink">
      {/* Ambient backdrop — same triad as Enterprise workshop landing */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background: `
            radial-gradient(ellipse 50% 40% at 18% 10%, rgba(99,102,241,0.10) 0%, transparent 60%),
            radial-gradient(ellipse 45% 35% at 82% 88%, rgba(139,92,246,0.09) 0%, transparent 60%),
            radial-gradient(ellipse 30% 25% at 50% 50%, rgba(6,182,212,0.05) 0%, transparent 60%)
          `,
        }}
      />

      <article className="mx-auto max-w-[1100px] px-6 pb-28 pt-14 md:px-12 md:pt-20">
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Inline breadcrumb — kept dependency-free so the page
              still renders if `<Breadcrumbs />` is mid-flight on a
              parallel branch. Same a11y semantics as the shared
              component (`<nav aria-label="Breadcrumb"> + ordered list +
              aria-current="page"`). */}
          <nav
            aria-label="Breadcrumb"
            className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3"
          >
            <ol className="flex flex-wrap items-center gap-1.5">
              <li className="flex items-center gap-1.5">
                <Link
                  to="/"
                  className="rounded-sm text-ink-2 transition-colors duration-150 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
                >
                  Home
                </Link>
                <ChevronRight
                  size={11}
                  strokeWidth={1.6}
                  aria-hidden="true"
                  className="text-ink-3"
                />
              </li>
              <li className="flex items-center gap-1.5">
                <Link
                  to="/workshop"
                  className="rounded-sm text-ink-2 transition-colors duration-150 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
                >
                  Workshop
                </Link>
                <ChevronRight
                  size={11}
                  strokeWidth={1.6}
                  aria-hidden="true"
                  className="text-ink-3"
                />
              </li>
              <li className="flex items-center gap-1.5">
                <span aria-current="page" className="text-ink">
                  ROI calculator
                </span>
              </li>
            </ol>
          </nav>
        </motion.div>

        {/* Hero */}
        <motion.header
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
          className="mb-12 mt-8 grid grid-cols-1 gap-4 border-b border-line pb-10"
        >
          <div className="flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <Calculator
              size={12}
              strokeWidth={1.7}
              aria-hidden
              style={{ color: "var(--brand-indigo)" }}
            />
            <span style={{ color: "var(--brand-indigo)" }}>W84</span>
            <span>Workshop · ROI calculator</span>
          </div>
          <h1
            className="max-w-[24ch] font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.2rem, 5vw, 4rem)" }}
          >
            {t("roi.title")}
          </h1>
          <p className="mt-2 max-w-[64ch] text-[15px] leading-[1.65] text-ink-2">
            {t("roi.subtitle")}
          </p>

          {/* Preset buttons */}
          <div className="mt-4 flex flex-wrap gap-2">
            {ROI_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p.input)}
                className="rounded-sm border border-line bg-bg-1/50 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 transition-colors duration-150 hover:border-ink-3 hover:bg-bg-1 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                {t(p.labelKey)}
              </button>
            ))}
          </div>
        </motion.header>

        {/* Inputs + Metrics — two-column on md+, stacked on mobile */}
        <motion.div
          initial={{ opacity: 1, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="grid grid-cols-1 gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
        >
          {/* Left: inputs */}
          <section
            aria-labelledby="roi-inputs-heading"
            className="space-y-7 rounded-md border border-line bg-bg-1/40 p-7 backdrop-blur-sm"
          >
            <h2
              id="roi-inputs-heading"
              className="font-display text-[18px] leading-[1.2] tracking-[-0.005em] text-ink"
            >
              Your numbers
            </h2>

            <SliderRow
              label={t("roi.input.team")}
              value={input.teamSize}
              min={1}
              max={50}
              unit="people"
              onChange={(v) => setField("teamSize", v)}
            />

            <SliderRow
              label={t("roi.input.rate")}
              value={input.hourlyRate}
              min={1}
              max={2000}
              step={1}
              unit="$/hr"
              onChange={(v) => setField("hourlyRate", v)}
            >
              <div className="flex flex-wrap items-center gap-2">
                {HOURLY_RATE_PRESETS.map((rate) => (
                  <button
                    key={rate}
                    type="button"
                    onClick={() => setField("hourlyRate", rate)}
                    aria-pressed={input.hourlyRate === rate}
                    className={`rounded-sm border px-2.5 py-1 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)] ${
                      input.hourlyRate === rate
                        ? "border-[var(--brand-indigo)] bg-[var(--brand-indigo)]/10 text-ink"
                        : "border-line bg-bg-2 text-ink-2 hover:border-ink-3 hover:text-ink"
                    }`}
                  >
                    ${rate}
                  </button>
                ))}
                <label className="ml-1 inline-flex items-center gap-2">
                  <span className="font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                    custom $
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={100000}
                    step={1}
                    value={input.hourlyRate}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => {
                      const n = Number(e.target.value);
                      if (Number.isFinite(n)) setField("hourlyRate", n);
                    }}
                    aria-label="custom hourly rate"
                    className="w-24 rounded-sm border border-line bg-bg-2 px-2 py-1 font-mono-tech text-[11px] text-ink focus:border-[var(--brand-indigo)] focus:outline-none"
                  />
                </label>
              </div>
            </SliderRow>

            <SliderRow
              label={t("roi.input.hours")}
              value={input.hoursPerWeek}
              min={1}
              max={40}
              unit="hrs/wk"
              onChange={(v) => setField("hoursPerWeek", v)}
            />

            <SliderRow
              label={t("roi.input.automation")}
              value={Math.round(input.automationRate * 100)}
              min={20}
              max={90}
              unit="%"
              onChange={(v) => setField("automationRate", v / 100)}
            />

            <p className="border-t border-line/60 pt-4 font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
              TARS Business · ${TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH} / seat /
              month
            </p>
          </section>

          {/* Right: metrics */}
          <section
            aria-labelledby="roi-metrics-heading"
            className="space-y-4"
          >
            <h2
              id="roi-metrics-heading"
              className="sr-only"
            >
              Computed metrics
            </h2>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <MetricCard
                label={t("roi.metric.hoursSaved")}
                display={formatHours(hoursAnim)}
                sub="hrs / wk · whole team"
                accent="var(--brand-indigo)"
              />
              <MetricCard
                label={t("roi.metric.annualSaving")}
                display={formatUsd(savingAnim)}
                sub="USD / year"
                accent="var(--brand-cyan)"
              />
              <MetricCard
                label={t("roi.metric.tarsCost")}
                display={formatUsd(costAnim)}
                sub={`${input.teamSize} × $${TARS_BUSINESS_PRICE_PER_SEAT_PER_MONTH} × 12`}
                accent="var(--brand-violet)"
              />
              <MetricCard
                label={t("roi.metric.netROI")}
                display={formatPercent(roiAnim)}
                sub="(saving − cost) / cost"
                accent="var(--brand-indigo)"
              />
            </div>

            <MetricCard
              label={t("roi.metric.payback")}
              display={formatWeeks(paybackAnim)}
              sub="weeks until cost is recovered"
              accent="var(--brand-violet)"
            />

            {/* CTAs */}
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                onClick={onPrint}
                className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-line bg-bg-1 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors duration-150 hover:border-[var(--brand-indigo)] hover:bg-bg-1/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
              >
                <Printer size={13} strokeWidth={1.7} aria-hidden />
                {t("roi.cta.memo")}
              </button>
              <a
                href={mailtoHref}
                className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-line bg-bg-1 px-4 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] text-ink transition-colors duration-150 hover:border-[var(--brand-cyan)] hover:bg-bg-1/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-cyan)]"
              >
                <Mail size={13} strokeWidth={1.7} aria-hidden />
                {t("roi.cta.email")}
              </a>
            </div>
          </section>
        </motion.div>

        {/* Disclaimer footer */}
        <motion.footer
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="mt-14 border-t border-line pt-6 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3"
        >
          {t("roi.disclaimer")}
        </motion.footer>
      </article>
    </div>
  );
}

export default WorkshopROI;
