// SYNC: claude-w107-bundles
/**
 * <InstallProgressBar /> — fake-ish progress bar shown while a
 * bundle install is mid-flight. Backend is fast (~100ms) so we
 * animate to 90% over 600ms then snap to 100% on resolve.
 */

import { useEffect, useState } from "react";

interface Props {
  active: boolean;
  done?: boolean;
  label?: string;
}

export function InstallProgressBar({ active, done, label }: Props) {
  const [pct, setPct] = useState(0);

  useEffect(() => {
    if (!active) {
      setPct(0);
      return;
    }
    if (done) {
      setPct(100);
      return;
    }
    let raf = 0;
    let start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / 600, 1);
      // ease-out toward 90%.
      setPct(90 * (1 - Math.pow(1 - t, 2)));
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, done]);

  if (!active && !done) return null;
  return (
    <div className="flex flex-col gap-1.5" role="status" aria-live="polite">
      <div className="flex items-center justify-between text-xs text-white/60">
        <span>{label || (done ? "Installed." : "Installing…")}</span>
        <span>{Math.round(pct)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full bg-[var(--accent,#7c3aed)] transition-[width] duration-200 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
