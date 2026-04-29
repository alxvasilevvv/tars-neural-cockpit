/**
 * Cinematic mnemonic reveal — Phase O5 polish.
 *
 * Replaces the plain text-block reveal with a face-down card grid
 * that:
 *   - flips word-by-word with a 60ms stagger after the operator
 *     explicitly taps "reveal",
 *   - renders each word as a numbered card (01..N),
 *   - keeps the "I wrote it down" gate so the card stays open until
 *     the operator confirms,
 *   - clears the words from React state on dismiss (best-effort —
 *     the host already wiped its copy),
 *   - is fully static-typed; no third-party motion libs.
 *
 * Brand-grade: gold accent, ambient glow, soft shadow, subtle 3D
 * perspective. Pairs with the existing CornerFrame brand element.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  Eye,
  EyeOff,
  ShieldCheck,
} from "lucide-react";

export interface MnemonicRevealProps {
  walletId: string;
  mnemonic: string;
  copiedKey: string | null;
  onCopy: (walletId: string, mnemonic: string) => Promise<void> | void;
  onDismiss: () => void;
}

export function MnemonicReveal({
  walletId,
  mnemonic,
  copiedKey,
  onCopy,
  onDismiss,
}: MnemonicRevealProps) {
  const words = useMemo(() => splitMnemonic(mnemonic), [mnemonic]);

  // Cinematic states:
  //   "armed"   — face-down cards, big "reveal" CTA.
  //   "showing" — cards flipping in stagger; eventually all face-up.
  //   "hidden"  — operator chose to hide again.
  const [phase, setPhase] = useState<"armed" | "showing" | "hidden">("armed");
  const [revealedCount, setRevealedCount] = useState(0);
  const timersRef = useRef<number[]>([]);

  // When entering "showing", schedule a per-card stagger.
  useEffect(() => {
    if (phase !== "showing") return;
    setRevealedCount(0);
    const STAGGER_MS = 60;
    const timers: number[] = [];
    for (let i = 0; i < words.length; i++) {
      const t = window.setTimeout(() => {
        setRevealedCount((c) => Math.max(c, i + 1));
      }, i * STAGGER_MS);
      timers.push(t);
    }
    timersRef.current = timers;
    return () => {
      for (const t of timers) window.clearTimeout(t);
      timersRef.current = [];
    };
  }, [phase, words.length]);

  const allRevealed = revealedCount === words.length;
  const wordCountLabel = `${words.length} word${words.length === 1 ? "" : "s"}`;

  return (
    <div
      className="mb-4 overflow-hidden rounded-xl border border-amber-400/40 bg-gradient-to-br from-amber-500/[0.08] via-bg-1 to-bg-1 p-4 shadow-[0_0_60px_-20px_rgba(251,191,36,0.45)]"
      role="region"
      aria-label="Recovery phrase"
    >
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-amber-300">
          <AlertTriangle size={12} />
          <span>recovery phrase · shown ONCE</span>
          <span className="text-ink-2/70">·</span>
          <span className="text-ink-2">{wordCountLabel}</span>
        </div>
        <div
          className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-2/80"
          aria-hidden="true"
        >
          wallet · {walletId.slice(0, 8)}…
        </div>
      </header>

      <p className="mb-3 font-mono-tech text-[11.5px] leading-relaxed text-ink-2">
        Write these on paper. Anyone with these words controls this wallet.
        TARS can&apos;t recover them later.
      </p>

      {phase === "armed" ? (
        <ArmedState
          words={words}
          onReveal={() => setPhase("showing")}
        />
      ) : phase === "hidden" ? (
        <HiddenState
          words={words}
          onShowAgain={() => setPhase("showing")}
        />
      ) : (
        <RevealedGrid words={words} revealedCount={revealedCount} />
      )}

      <footer className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {phase === "showing" && allRevealed ? (
            <button
              type="button"
              onClick={() => setPhase("hidden")}
              className="inline-flex items-center gap-1.5 rounded border border-line px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink"
              aria-label="Hide phrase"
            >
              <EyeOff size={11} />
              hide
            </button>
          ) : null}
          {phase !== "armed" ? (
            <button
              type="button"
              onClick={() => void onCopy(walletId, mnemonic)}
              className="inline-flex items-center gap-1.5 rounded border border-line px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 hover:border-line-strong hover:text-ink"
              aria-label="Copy phrase"
            >
              {copiedKey === walletId ? <Check size={11} /> : <Copy size={11} />}
              copy
            </button>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="inline-flex items-center gap-1.5 rounded border border-amber-400/50 bg-amber-400/10 px-3 py-1.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-amber-200 hover:bg-amber-400/15"
          aria-label="Confirm phrase saved"
        >
          <ShieldCheck size={11} />
          I wrote it down
        </button>
      </footer>
    </div>
  );
}

interface ArmedStateProps {
  words: string[];
  onReveal: () => void;
}

function ArmedState({ words, onReveal }: ArmedStateProps) {
  return (
    <div className="relative">
      <FaceDownGrid count={words.length} />
      <button
        type="button"
        onClick={onReveal}
        className="absolute inset-0 m-auto flex h-[44px] w-[180px] items-center justify-center gap-2 self-center justify-self-center rounded-lg border border-amber-400/60 bg-bg-1/95 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-amber-200 shadow-[0_0_24px_-6px_rgba(251,191,36,0.6)] backdrop-blur transition hover:border-amber-300 hover:bg-bg-1"
      >
        <Eye size={13} />
        reveal phrase
      </button>
    </div>
  );
}

interface HiddenStateProps {
  words: string[];
  onShowAgain: () => void;
}

function HiddenState({ words, onShowAgain }: HiddenStateProps) {
  return (
    <div className="relative">
      <FaceDownGrid count={words.length} />
      <button
        type="button"
        onClick={onShowAgain}
        className="absolute inset-0 m-auto flex h-[40px] w-[160px] items-center justify-center gap-2 self-center justify-self-center rounded-lg border border-line bg-bg-1/95 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-2 shadow-lg backdrop-blur hover:border-line-strong hover:text-ink"
      >
        <Eye size={12} />
        show again
      </button>
    </div>
  );
}

interface FaceDownGridProps {
  count: number;
}

function FaceDownGrid({ count }: FaceDownGridProps) {
  return (
    <div
      className="grid gap-2 opacity-[0.55]"
      style={{ gridTemplateColumns: gridTemplateForCount(count) }}
      aria-hidden="true"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="relative h-[42px] rounded-md border border-line bg-bg-1 shadow-[inset_0_0_18px_rgba(0,0,0,0.4)]"
        >
          <span className="absolute left-1.5 top-1 font-mono-tech text-[8.5px] tabular-nums text-ink-2/50">
            {(i + 1).toString().padStart(2, "0")}
          </span>
          <span className="absolute inset-0 flex items-center justify-center font-mono-tech text-[14px] tracking-[6px] text-ink-2/30">
            ····
          </span>
        </div>
      ))}
    </div>
  );
}

interface RevealedGridProps {
  words: string[];
  revealedCount: number;
}

function RevealedGrid({ words, revealedCount }: RevealedGridProps) {
  return (
    <div
      className="grid gap-2"
      style={{
        gridTemplateColumns: gridTemplateForCount(words.length),
        perspective: "900px",
      }}
    >
      {words.map((word, i) => {
        const flipped = i < revealedCount;
        return (
          <div
            key={i}
            className="relative h-[42px]"
            style={{ transformStyle: "preserve-3d" }}
          >
            <div
              className="absolute inset-0 transition-transform duration-[420ms] ease-out"
              style={{
                transformStyle: "preserve-3d",
                transform: flipped ? "rotateY(0deg)" : "rotateY(180deg)",
              }}
            >
              {/* face-up */}
              <div
                className="absolute inset-0 flex items-center justify-between rounded-md border border-amber-400/30 bg-gradient-to-br from-amber-400/[0.07] via-bg-1 to-bg-1 px-2.5"
                style={{ backfaceVisibility: "hidden" }}
              >
                <span className="font-mono-tech text-[9px] tabular-nums text-amber-300/70">
                  {(i + 1).toString().padStart(2, "0")}
                </span>
                <span className="select-text font-mono-tech text-[12.5px] font-medium text-ink">
                  {word}
                </span>
                <span className="w-[10px]" aria-hidden="true" />
              </div>
              {/* face-down */}
              <div
                className="absolute inset-0 flex items-center justify-center rounded-md border border-line bg-bg-1 shadow-[inset_0_0_18px_rgba(0,0,0,0.4)]"
                style={{
                  backfaceVisibility: "hidden",
                  transform: "rotateY(180deg)",
                }}
              >
                <span className="font-mono-tech text-[14px] tracking-[6px] text-ink-2/40">
                  ····
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── helpers ────────────────────────────────────────────────────────────────

export function splitMnemonic(raw: string): string[] {
  return raw
    .split(/\s+/g)
    .map((w) => w.trim())
    .filter((w) => w.length > 0);
}

export function gridTemplateForCount(count: number): string {
  // Tight columns that read like a printable card. 24 → 4×6, 12 → 4×3.
  if (count <= 6) return "repeat(3, minmax(0, 1fr))";
  if (count <= 12) return "repeat(4, minmax(0, 1fr))";
  if (count <= 16) return "repeat(4, minmax(0, 1fr))";
  return "repeat(4, minmax(0, 1fr))";
}
