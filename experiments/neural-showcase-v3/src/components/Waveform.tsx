import { useEffect, useRef } from "react";

/**
 * Live awareness waveform.
 *
 * Cheap deterministic-pseudo-random animated bars so the rail feels alive
 * before a real /api/awareness/stream lands. Each bar is updated on its
 * own offset so the result reads as continuous neural activity instead
 * of a synced pulse.
 *
 *  - bars: number of bars
 *  - className: applied to <svg>
 *  - color: stroke + fill (accent by default)
 */
export function Waveform({
  bars = 28,
  width = 120,
  height = 22,
  color = "var(--color-accent)",
  className,
}: {
  bars?: number;
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const svg = ref.current;
    if (!svg) return;
    const rects = Array.from(svg.querySelectorAll("rect.bar")) as SVGRectElement[];
    let raf = 0;

    const phases = rects.map(() => Math.random() * Math.PI * 2);
    const speeds = rects.map(() => 0.9 + Math.random() * 1.6);

    const tick = (t: number) => {
      const time = t * 0.001;
      rects.forEach((r, i) => {
        const v =
          0.5 +
          Math.sin(time * speeds[i] + phases[i]) * 0.34 +
          Math.sin(time * 0.45 + i * 0.38) * 0.16;
        const h = Math.max(2, v * height);
        r.setAttribute("y", String((height - h) / 2));
        r.setAttribute("height", String(h));
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [bars, height]);

  const gap = 2;
  const barW = (width - (bars - 1) * gap) / bars;

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={className}
      aria-hidden="true"
    >
      {Array.from({ length: bars }).map((_, i) => (
        <rect
          key={i}
          className="bar"
          x={i * (barW + gap)}
          y={height / 2 - 1}
          width={barW}
          height={2}
          rx={1}
          fill={color}
          opacity={0.85}
        />
      ))}
    </svg>
  );
}
