/**
 * Recovery seed flow (Phase L5 K4).
 *
 * Uses `lib/recovery.ts` against `POST /api/recovery/generate|verify`.
 * Clipboard copy intentionally omitted — operator must transcribe offline.
 */

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, ShieldAlert } from "lucide-react";
import {
  WORD_COUNT,
  chunkMnemonic,
  generateSeed,
  isCompleteAttempt,
  mnemonicsMatch,
  verifySeed,
  type GenerateResponse,
  type RecoveryError,
} from "@/lib/recovery";
import { CornerFrame } from "@/components/Glyphs";

type Step = "gen" | "confirm" | "verify";

export interface RecoverySetupProps {
  /** Called after server confirms the typed mnemonic (fingerprint known). */
  onCompleted?: (fingerprint: string) => void;
  /** Dangerous bypass — persists skip flag upstream. */
  onSkip?: () => void;
  /** Start at verify step only (re-entry from settings). */
  initialMnemonic?: string;
}

export function RecoverySetup({
  onCompleted,
  onSkip,
  initialMnemonic,
}: RecoverySetupProps) {
  const [step, setStep] = useState<Step>(() => (initialMnemonic ? "confirm" : "gen"));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [written, setWritten] = useState(false);
  const [gen, setGen] = useState<GenerateResponse | null>(
    initialMnemonic
      ? {
          ok: true,
          trace_id: "",
          mnemonic: initialMnemonic,
          fingerprint: "",
          word_count: WORD_COUNT,
        }
      : null,
  );
  const [typed, setTyped] = useState("");

  const startGenerate = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await generateSeed();
      setGen(r);
      setStep("confirm");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }, []);

  const onContinueToVerify = useCallback(() => {
    if (!written || !gen) return;
    setTyped("");
    setStep("verify");
    setErr(null);
  }, [written, gen]);

  const onVerify = useCallback(async () => {
    if (!gen?.mnemonic) return;
    setBusy(true);
    setErr(null);
    if (!mnemonicsMatch(gen.mnemonic, typed)) {
      setErr("Phrase doesn't match · check each word carefully.");
      setBusy(false);
      return;
    }
    try {
      const r = await verifySeed({ mnemonic: typed });
      try {
        localStorage.setItem("tars_recovery_verified_fp", r.fingerprint);
      } catch {
        /* quota / private mode */
      }
      onCompleted?.(r.fingerprint);
    } catch (e: unknown) {
      const re = e as RecoveryError;
      const msg = typeof re.message === "string" ? re.message : String(e);
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }, [gen?.mnemonic, typed, onCompleted]);

  let grid: string[][] = [];
  if (gen?.mnemonic) {
    try {
      grid = chunkMnemonic(gen.mnemonic);
    } catch {
      grid = [];
    }
  }

  return (
    <div className="relative rounded-[14px] border border-line-strong bg-bg-1 p-6 md:p-8">
      <CornerFrame />

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="font-mono-tech text-[9.5px] uppercase tracking-[2.8px] text-ink-2">
            L5 · recovery seed
          </p>
          <h2 className="mt-1 font-display text-[clamp(1.35rem,2.8vw,1.75rem)] font-medium uppercase tracking-[0.02em] text-ink">
            Master backup phrase
          </h2>
        </div>
        {step === "gen" && !initialMnemonic && (
          <span className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
            offline-first
          </span>
        )}
      </div>

      <p className="mb-6 max-w-[62ch] text-[13px] leading-[1.6] text-ink-2">
        Store these {WORD_COUNT} words on paper. Never screenshot, never sync them to cloud.
        The host never logs your phrase — only a short fingerprint reaches the audit log.
      </p>

      <div aria-live="polite">
        <AnimatePresence mode="wait">
          {step === "gen" && (
            <motion.div
              key="gen"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              <button
                type="button"
                disabled={busy}
                onClick={startGenerate}
                className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-hot bg-accent-deep px-4 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.6px] text-ink transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating…
                  </>
                ) : (
                  "Generate 24-word phrase"
                )}
              </button>
            </motion.div>
          )}

          {step === "confirm" && gen && (
            <motion.div
              key="confirm"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-5"
            >
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {grid.flatMap((row, ri) =>
                  row.map((w, wi) => (
                    <div
                      key={`${ri}-${wi}`}
                      className="rounded-md border border-line bg-bg-0 px-2.5 py-2 font-mono-tech text-[12px] uppercase tracking-[0.08em] text-ink"
                    >
                      <span className="mr-1.5 tabular-nums text-ink-3">
                        {ri * row.length + wi + 1}.
                      </span>
                      <span>{w}</span>
                    </div>
                  )),
                )}
              </div>

              <label className="flex cursor-pointer items-start gap-3 text-[13px] leading-[1.5] text-ink-2">
                <input
                  type="checkbox"
                  className="mt-1 cursor-pointer accent-[#6366F1]"
                  checked={written}
                  onChange={(e) => setWritten(e.target.checked)}
                />
                I wrote these words down in order — I understand there is no account recovery without them.
              </label>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={!written}
                  onClick={onContinueToVerify}
                  className="inline-flex rounded-md border border-line px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink transition-colors hover:border-line-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Continue → verify
                </button>
                {onSkip && (
                  <button
                    type="button"
                    onClick={onSkip}
                    className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 underline-offset-2 hover:text-alert hover:underline"
                  >
                    Skip for now
                  </button>
                )}
              </div>
            </motion.div>
          )}

          {step === "verify" && gen && (
            <motion.div
              key="verify"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              <label className="block">
                <span className="mb-2 block font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-2">
                  Type the full phrase ({WORD_COUNT} words)
                </span>
                <textarea
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  rows={5}
                  className="w-full resize-y rounded-md border border-line bg-bg-0 px-3 py-2.5 font-mono-tech text-[12.5px] leading-relaxed tracking-wide text-ink placeholder:text-ink-3 focus:border-line-hot focus:outline-none"
                  placeholder="abandon abandon ability …"
                  spellCheck={false}
                  autoCapitalize="off"
                  autoComplete="off"
                />
              </label>

              <button
                type="button"
                disabled={busy || !isCompleteAttempt(typed)}
                onClick={onVerify}
                className="inline-flex items-center gap-2 rounded-md border border-line-strong bg-bg-0 px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink hover:border-accent disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Verifying…
                  </>
                ) : (
                  "Verify with host"
                )}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {err && (
        <div className="mt-5 rounded-md border border-alert/35 bg-alert/[0.06] px-3 py-2 font-mono-tech text-[12px] leading-[1.5] text-ink">
          <ShieldAlert className="mb-1 inline-block h-3.5 w-3.5 align-middle text-alert" aria-hidden />{" "}
          {err}
        </div>
      )}
    </div>
  );
}
