/**
 * Decorative tech glyphs used across HUD plates and section headers.
 * 1px stroke, single-colour per skill HUD/Sci-Fi FUI rules.
 */

interface GlyphProps {
  size?: number;
  className?: string;
  stroke?: string;
}

const base = (className?: string) =>
  `pointer-events-none select-none ${className ?? ""}`;

export function Reticle({ size = 18, className, stroke }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={base(className)}
      stroke={stroke ?? "currentColor"}
      strokeWidth={1.2}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <path d="M12 1.5 V5.5 M12 18.5 V22.5 M1.5 12 H5.5 M18.5 12 H22.5" />
    </svg>
  );
}

export function Crosshair({ size = 18, className, stroke }: GlyphProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={base(className)}
      stroke={stroke ?? "currentColor"}
      strokeWidth={1.2}
      aria-hidden="true"
    >
      <path d="M12 2 V8 M12 16 V22 M2 12 H8 M16 12 H22" />
      <rect x="8" y="8" width="8" height="8" />
      <path d="M10 10 L14 14 M14 10 L10 14" />
    </svg>
  );
}

export function StatusLozenge({
  label,
  tone = "accent",
  className,
}: {
  label: string;
  tone?: "accent" | "hud" | "alert" | "success" | "muted";
  className?: string;
}) {
  const colorVar =
    tone === "hud"
      ? "var(--color-hud)"
      : tone === "alert"
        ? "var(--color-alert)"
        : tone === "success"
          ? "var(--color-success)"
          : tone === "muted"
            ? "var(--color-ink-2)"
            : "var(--color-accent)";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2.6px] ${className ?? ""}`}
      style={{
        borderColor: colorVar,
        color: colorVar,
        background: `color-mix(in srgb, ${colorVar} 8%, transparent)`,
      }}
    >
      <span
        className="block h-1 w-1 rounded-full"
        style={{
          background: colorVar,
          boxShadow: `0 0 8px ${colorVar}`,
          animation: "pulseDot 1.6s ease-in-out infinite",
        }}
      />
      {label}
    </span>
  );
}

export function CornerFrame({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 ${className ?? ""}`}
    >
      {/* Four corner ticks */}
      <span className="absolute left-0 top-0 h-2 w-2 border-l border-t" style={{ borderColor: "var(--color-hud-soft)" }} />
      <span className="absolute right-0 top-0 h-2 w-2 border-r border-t" style={{ borderColor: "var(--color-hud-soft)" }} />
      <span className="absolute bottom-0 left-0 h-2 w-2 border-b border-l" style={{ borderColor: "var(--color-hud-soft)" }} />
      <span className="absolute bottom-0 right-0 h-2 w-2 border-b border-r" style={{ borderColor: "var(--color-hud-soft)" }} />
    </span>
  );
}

export function BarStack({
  values,
  height = 18,
  width = 56,
  color = "var(--color-accent)",
  className,
}: {
  values: number[];
  height?: number;
  width?: number;
  color?: string;
  className?: string;
}) {
  const gap = 1;
  const barW = (width - (values.length - 1) * gap) / values.length;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden="true">
      {values.map((v, i) => {
        const h = Math.max(1.2, v * height);
        return (
          <rect
            key={i}
            x={i * (barW + gap)}
            y={height - h}
            width={barW}
            height={h}
            fill={color}
            opacity={0.75 + 0.25 * (i / values.length)}
          />
        );
      })}
    </svg>
  );
}
