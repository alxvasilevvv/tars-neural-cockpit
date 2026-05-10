// SYNC: claude-w80-fe-only
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Play, Save, Sparkles } from "lucide-react";
import { BrandHairline } from "@/components/BrandHairline";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { API_BASE } from "@/lib/api";
import { toast } from "@/lib/toast";

/**
 * <RetuneDialog /> — Wave 80-B
 *
 * Surfaces a single diverging backtest case with the operator's
 * current system prompt prefilled. The operator can:
 *   - Edit the prompt (a delta is highlighted vs. the original)
 *   - "Test on this case" → POST /api/agents/{id}/score with the
 *     overridden prompt; preview the new output without persisting.
 *   - "Apply to agent" → PATCH /api/agents/{id} with the new prompt.
 *
 * Backend gracefully missing → soft-toast & mock the test result.
 */

export interface DivergingCase {
  rowIndex: number;
  input: string;
  agentOutput: string;
  groundTruth: string;
}

interface RetuneDialogProps {
  open: boolean;
  onClose: () => void;
  agentId: string;
  agentName: string;
  currentPrompt: string;
  divergingCase: DivergingCase | null;
  /** Called after successful PATCH so parent can update its local copy. */
  onApplied?: (newPrompt: string) => void;
}

export function RetuneDialog({
  open,
  onClose,
  agentId,
  agentName,
  currentPrompt,
  divergingCase,
  onApplied,
}: RetuneDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const [draftPrompt, setDraftPrompt] = useState(currentPrompt);
  const [busy, setBusy] = useState<"idle" | "testing" | "applying">("idle");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testAgrees, setTestAgrees] = useState<boolean | null>(null);
  useFocusTrap(dialogRef, open);

  useEffect(() => {
    if (open) {
      setDraftPrompt(currentPrompt);
      setTestResult(null);
      setTestAgrees(null);
    }
  }, [open, currentPrompt]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const promptChanged = draftPrompt !== currentPrompt;

  const onTest = async () => {
    if (!divergingCase) return;
    setBusy("testing");
    setTestResult(null);
    try {
      const r = await fetch(
        `${API_BASE}/api/agents/${encodeURIComponent(agentId)}/score`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            input: divergingCase.input,
            system_prompt_override: draftPrompt,
          }),
        },
      );
      if (r.status === 404) {
        // Backend WIP — synthesise a plausible result for the demo.
        const mock = synthesiseMock(divergingCase.input, draftPrompt);
        setTestResult(mock);
        setTestAgrees(mock.trim() === divergingCase.groundTruth.trim());
        toast.warn("backend WIP — using mock score result");
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = (await r.json()) as { output?: string; agrees?: boolean };
      setTestResult(body.output ?? "");
      setTestAgrees(
        typeof body.agrees === "boolean"
          ? body.agrees
          : (body.output ?? "").trim() === divergingCase.groundTruth.trim(),
      );
    } catch (err) {
      toast.error(`test failed · ${(err as Error).message}`);
    } finally {
      setBusy("idle");
    }
  };

  const onApply = async () => {
    setBusy("applying");
    try {
      const r = await fetch(
        `${API_BASE}/api/agents/${encodeURIComponent(agentId)}`,
        {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ system_prompt: draftPrompt }),
        },
      );
      if (r.status === 404) {
        toast.warn("backend WIP — change kept locally only");
        onApplied?.(draftPrompt);
        onClose();
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      toast.success("agent updated");
      onApplied?.(draftPrompt);
      onClose();
    } catch (err) {
      toast.error(`apply failed · ${(err as Error).message}`);
    } finally {
      setBusy("idle");
    }
  };

  return (
    <AnimatePresence>
      {open && divergingCase && (
        <motion.div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-label={`retune agent ${agentName}`}
          tabIndex={-1}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(2,4,12,0.72)] px-4 pt-[8vh] backdrop-blur-md"
          onClick={onClose}
        >
          <motion.div
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.99 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-3xl overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65)]"
          >
            <BrandHairline variant="static" />
            <header className="flex items-center justify-between border-b border-line/60 px-5 py-3">
              <div>
                <div className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
                  retune · diverging row #{divergingCase.rowIndex}
                </div>
                <h2 className="font-display text-[16px] text-ink">{agentName}</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="close"
                className="rounded p-1 text-ink-3 hover:bg-bg-2 hover:text-ink"
              >
                <X size={14} strokeWidth={1.7} />
              </button>
            </header>

            <div className="grid max-h-[70vh] grid-cols-1 gap-4 overflow-y-auto p-5 md:grid-cols-2">
              {/* Case data */}
              <section className="grid gap-3">
                <FieldCard label="Input">
                  <pre className="whitespace-pre-wrap break-words font-mono-tech text-[11px] leading-[1.55] text-ink-2">
{divergingCase.input}
                  </pre>
                </FieldCard>
                <FieldCard label="Agent output (current)">
                  <pre
                    className="whitespace-pre-wrap break-words font-mono-tech text-[11px] leading-[1.55]"
                    style={{ color: "var(--brand-amber)" }}
                  >
{divergingCase.agentOutput}
                  </pre>
                </FieldCard>
                <FieldCard label="Ground truth">
                  <pre
                    className="whitespace-pre-wrap break-words font-mono-tech text-[11px] leading-[1.55]"
                    style={{ color: "var(--color-success)" }}
                  >
{divergingCase.groundTruth}
                  </pre>
                </FieldCard>
                {testResult !== null && (
                  <FieldCard label={`Test result · ${testAgrees ? "agrees" : "diverges"}`}>
                    <pre
                      className="whitespace-pre-wrap break-words font-mono-tech text-[11px] leading-[1.55]"
                      style={{
                        color: testAgrees
                          ? "var(--color-success)"
                          : "var(--brand-amber)",
                      }}
                    >
{testResult}
                    </pre>
                  </FieldCard>
                )}
              </section>

              {/* Prompt editor */}
              <section className="grid gap-3">
                <div>
                  <div className="mb-1.5 flex items-center justify-between font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
                    <span>system prompt {promptChanged ? "(edited)" : ""}</span>
                    <span>{draftPrompt.length} chars</span>
                  </div>
                  <textarea
                    value={draftPrompt}
                    onChange={(e) => setDraftPrompt(e.target.value)}
                    rows={14}
                    className="w-full rounded-md border border-line bg-bg-0 p-3 font-mono-tech text-[11.5px] leading-[1.55] text-ink outline-none focus:border-accent"
                  />
                </div>
                {promptChanged && (
                  <div className="rounded-md border border-line/60 bg-bg-2/40 p-3 text-[11px] text-ink-2">
                    <div className="mb-1 inline-flex items-center gap-1.5 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
                      <Sparkles size={10} strokeWidth={1.7} aria-hidden /> delta
                    </div>
                    <DiffSummary before={currentPrompt} after={draftPrompt} />
                  </div>
                )}
              </section>
            </div>

            <footer className="flex items-center justify-end gap-2 border-t border-line/60 px-5 py-3">
              <button
                type="button"
                onClick={onTest}
                disabled={busy !== "idle"}
                className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-bg-2/60 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-ink hover:border-accent disabled:opacity-60"
              >
                <Play size={11} strokeWidth={1.8} aria-hidden />
                {busy === "testing" ? "testing…" : "test on this case"}
              </button>
              <button
                type="button"
                onClick={onApply}
                disabled={!promptChanged || busy !== "idle"}
                className="inline-flex items-center gap-1.5 rounded-md border border-accent bg-accent/10 px-3 py-1.5 font-mono-tech text-[10.5px] uppercase tracking-[1.8px] text-accent hover:bg-accent/15 disabled:opacity-50"
              >
                <Save size={11} strokeWidth={1.8} aria-hidden />
                {busy === "applying" ? "applying…" : "apply to agent"}
              </button>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function FieldCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-line/60 bg-bg-2/40 p-3">
      <div className="mb-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
        {label}
      </div>
      {children}
    </div>
  );
}

/** Cheap diff summary — character delta + first changed line. */
function DiffSummary({ before, after }: { before: string; after: string }) {
  const delta = after.length - before.length;
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  let firstChanged = -1;
  for (let i = 0; i < Math.max(beforeLines.length, afterLines.length); i++) {
    if (beforeLines[i] !== afterLines[i]) {
      firstChanged = i;
      break;
    }
  }
  return (
    <div className="grid gap-1 font-mono-tech text-[10.5px] text-ink-2">
      <span>
        {delta >= 0 ? "+" : ""}
        {delta} chars · {beforeLines.length} → {afterLines.length} lines
      </span>
      {firstChanged >= 0 && (
        <span className="truncate text-ink-3">
          first change @ line {firstChanged + 1}
        </span>
      )}
    </div>
  );
}

/** Used only when backend is not deployed. */
function synthesiseMock(input: string, prompt: string): string {
  const seed = (input.length + prompt.length) % 3;
  const variants = ["positive", "neutral", "negative"];
  return variants[seed];
}

export default RetuneDialog;
