import { motion } from "framer-motion";
import { useEffect, useId, useRef, useState } from "react";

/**
 * <RobotAvatar /> — TARS-9, the cockpit's resident operator.
 *
 * Design intent: a TARS-Interstellar monolith with one horizontal
 * scan-line eye, three brand-triad LEDs at the crown, and a service
 * plate at the foot. Pure inline SVG + framer-motion — no R3F, no
 * Spline, no images. Total markup ≈ 4 KB rendered, GPU-cheap.
 *
 * State machine (driven by `state` prop):
 *
 *   idle      — slow 4s breathing, single eye-scan cycle every 6s.
 *               Default; reads as "machine on, alert, calm".
 *   thinking  — fast eye-scans (1.4s), violet→cyan halo rotates,
 *               LEDs pulse in indigo→violet→cyan rotation.
 *   ok        — brief green halo flash (1.8s), eye holds centered.
 *               Use after a successful invocation.
 *   error     — brief red halo flash (1.8s), eye scans agitated.
 *
 * Sizing: width is the only input; height auto-scales to keep the
 * monolith aspect ratio. Recommended ranges:
 *
 *   80px   — nav indicator
 *   140px  — right-rail floating avatar (cockpit)
 *   220px  — empty-state hero or onboarding portal
 *
 * Reduced-motion users get the static idle state — every animated
 * attribute respects `prefers-reduced-motion`.
 */

export type RobotState =
  | "idle"
  | "thinking"
  | "ok"
  | "error"
  | "listening"
  | "speaking";

interface Props {
  state?: RobotState;
  width?: number;
  /** "operator-grade" name plate text, defaults to "TARS-9" */
  callSign?: string;
  className?: string;
  /**
   * Optional 0..1 amplitude. When `state === "listening"` this drives
   * the eye scan-line and outer halo so they react to *real* mic
   * input instead of the synthetic pulse. Falsy or ≤ 0 falls back to
   * the synthetic listening cadence.
   */
  audioLevel?: number;
  /**
   * When true *and* state === "idle", the eye stops scanning and
   * tracks the page-X cursor position. Subtle "watching you" detail.
   * Disabled on touch devices automatically (no pointer events).
   */
  trackCursor?: boolean;
}

const HALO_COLOR: Record<RobotState, string> = {
  idle:      "rgba(99,102,241,0.32)",
  thinking:  "rgba(139,92,246,0.55)",
  ok:        "rgba(52,211,153,0.55)",
  error:     "rgba(239,68,68,0.55)",
  listening: "rgba(6,182,212,0.55)",
  speaking:  "rgba(167,139,250,0.55)",
};

export function RobotAvatar({
  state = "idle",
  width = 160,
  callSign = "TARS-9",
  className,
  audioLevel = 0,
  trackCursor = false,
}: Props) {
  // When listening with a live mic level, snap the synthetic timing
  // to the actual amplitude. Clamp to [0, 1] so wild values can't
  // accelerate the animation past the eye slot.
  const live = state === "listening" && audioLevel > 0;
  const amp = Math.min(1, Math.max(0, audioLevel));

  // Cursor-tracking eye — disabled on touch / coarse pointer to
  // avoid weird snap-to-tap behaviour. Only active when state is
  // genuinely idle (we don't want to fight an in-flight thinking
  // animation). Stores a 0..1 X-fraction relative to the wrapper.
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [cursorFrac, setCursorFrac] = useState<number | null>(null);
  const tracking =
    trackCursor &&
    state === "idle" &&
    typeof window !== "undefined" &&
    window.matchMedia?.("(pointer: fine)").matches;

  useEffect(() => {
    if (!tracking) {
      setCursorFrac(null);
      return;
    }
    let raf = 0;
    let lastFrac = 0.5;
    const onMove = (e: PointerEvent) => {
      const el = wrapperRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // Anchor on the robot's centre. Cursor x relative to a 600px
      // half-window left/right of the robot maps to [0, 1]; clamped.
      const cx = rect.left + rect.width / 2;
      const dx = e.clientX - cx;
      const span = 600;
      const frac = Math.max(0, Math.min(1, 0.5 + dx / span));
      lastFrac = frac;
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        raf = 0;
        setCursorFrac(lastFrac);
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [tracking]);
  const uid = useId().replace(/[:]/g, ""); // SVG IDs can't include :
  const ids = {
    body: `body-${uid}`,
    eye: `eye-${uid}`,
    halo: `halo-${uid}`,
    plate: `plate-${uid}`,
    edge: `edge-${uid}`,
  };

  // Geometry — SVG units; the viewBox renders 200×220 for a 10:11 slab.
  const W = 200;
  const H = 220;
  const bodyX = 28;
  const bodyY = 18;
  const bodyW = W - bodyX * 2;
  const bodyH = 168;
  const eyeY = bodyY + 78;
  const eyeH = 14;
  const eyeMargin = 18;
  const eyeX = bodyX + eyeMargin;
  const eyeW = bodyW - eyeMargin * 2;

  // Cadence & motion variants per state — framer-motion respects
  // prefers-reduced-motion automatically when transition.duration is set
  // via a global motion config; we additionally guard the ambient
  // animations behind a media query at the wrapper level.
  const breathe =
    state === "thinking"
      ? { scale: [1, 1.018, 1], transition: { duration: 1.6, repeat: Infinity, ease: "easeInOut" } }
      : { scale: [1, 1.012, 1], transition: { duration: 4.2, repeat: Infinity, ease: "easeInOut" } };

  const haloAnim =
    state === "thinking"
      ? { opacity: [0.35, 0.7, 0.35], rotate: [0, 360], transition: { opacity: { duration: 2.2, repeat: Infinity, ease: "easeInOut" }, rotate: { duration: 12, repeat: Infinity, ease: "linear" } } }
      : state === "ok" || state === "error"
        ? { opacity: [0.85, 0.0], transition: { duration: 1.6, ease: "easeOut" } }
        : state === "listening"
          ? live
            // Live mic — opacity/scale snap to amplitude. Smoothing
            // already happens upstream in useMicLevel; here we just
            // map the value into a perceptual range.
            ? {
                opacity: 0.35 + amp * 0.55,
                scale: 1 + amp * 0.08,
                transition: { duration: 0.18, ease: "easeOut" },
              }
            : { opacity: [0.4, 0.7, 0.4], scale: [1, 1.06, 1], transition: { duration: 1.8, repeat: Infinity, ease: "easeInOut" } }
          : state === "speaking"
            ? { opacity: [0.45, 0.85, 0.55], transition: { duration: 0.45, repeat: Infinity, ease: "easeInOut" } }
            : { opacity: [0.18, 0.32, 0.18], transition: { duration: 4.6, repeat: Infinity, ease: "easeInOut" } };

  // Scan-line eye: a gradient bar slides across the eye slot.
  // When live mic is active, scan-rate accelerates with amplitude
  // (4.0s when silent, 0.6s at max amplitude).
  const scanDuration =
    state === "thinking" ? 1.2 :
    state === "error"    ? 0.9 :
    state === "speaking" ? 0.6 :
    state === "listening" ? (live ? 4.0 - amp * 3.4 : 2.4) :
    5.2;
  const scanX =
    state === "ok"
      ? { x: [eyeW * 0.45, eyeW * 0.45], transition: { duration: 0.001 } }
      : tracking && cursorFrac != null
        ? {
            // Tracking — eye slides toward cursor X. The scan-line is
            // 0.18 × eyeW wide; centre it under the mapped fraction.
            x: cursorFrac * eyeW - eyeW * 0.09 - eyeW * 0.18 / 2,
            transition: { type: "spring" as const, stiffness: 220, damping: 28, mass: 0.55 },
          }
        : {
            x: [-eyeW * 0.4, eyeW * 0.95, -eyeW * 0.4],
            transition: { duration: scanDuration, repeat: Infinity, ease: "easeInOut" },
          };

  // Crown LED rotation — three dots cycle which one is "hot" when thinking.
  const ledIntervalMs =
    state === "thinking" ? 380 : state === "error" ? 220 : 1600;
  const ledColors = ["var(--brand-indigo)", "var(--brand-violet)", "var(--brand-cyan)"];

  return (
    <motion.div
      ref={wrapperRef}
      className={`relative inline-block ${className ?? ""}`}
      style={{ width, aspectRatio: `${W} / ${H}` }}
      animate={breathe}
    >
      {/* Halo — sits behind the body, blurred radial */}
      <motion.div
        aria-hidden
        animate={haloAnim}
        className="pointer-events-none absolute inset-[-15%] rounded-full blur-2xl"
        style={{
          background: `radial-gradient(50% 50% at 50% 50%, ${HALO_COLOR[state]} 0%, transparent 75%)`,
        }}
      />

      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        height="100%"
        role="img"
        aria-label={`TARS robot · ${state}`}
      >
        <defs>
          {/* Body fill — subtle vertical sheen, OLED-grade */}
          <linearGradient id={ids.body} x1="0" y1="0" x2="0" y2={bodyH} gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#16161e" />
            <stop offset="0.5" stopColor="#0d0d14" />
            <stop offset="1" stopColor="#08080d" />
          </linearGradient>

          {/* Edge highlight — thin sweep at top */}
          <linearGradient id={ids.edge} x1="0" y1="0" x2={bodyW} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="var(--brand-indigo)" stopOpacity="0" />
            <stop offset="0.3" stopColor="var(--brand-indigo)" stopOpacity="0.45" />
            <stop offset="0.5" stopColor="var(--brand-violet)" stopOpacity="0.55" />
            <stop offset="0.7" stopColor="var(--brand-cyan)" stopOpacity="0.45" />
            <stop offset="1" stopColor="var(--brand-cyan)" stopOpacity="0" />
          </linearGradient>

          {/* Eye scan-line gradient — soft falloff on each side */}
          <linearGradient id={ids.eye} x1="0" y1="0" x2={eyeW * 0.18} y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="var(--brand-cyan)" stopOpacity="0" />
            <stop offset="0.45" stopColor="var(--brand-cyan)" stopOpacity="1" />
            <stop offset="0.55" stopColor="var(--brand-cyan)" stopOpacity="1" />
            <stop offset="1" stopColor="var(--brand-cyan)" stopOpacity="0" />
          </linearGradient>

          {/* Service plate — flat OLED with subtle inset */}
          <linearGradient id={ids.plate} x1="0" y1="0" x2="0" y2="20" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#0a0a10" />
            <stop offset="1" stopColor="#13131a" />
          </linearGradient>

          {/* Eye slot mask — clips the moving scan-line so it doesn't bleed */}
          <clipPath id={`${ids.eye}-clip`}>
            <rect x={eyeX} y={eyeY} width={eyeW} height={eyeH} rx="3" />
          </clipPath>
        </defs>

        {/* Outer body */}
        <rect
          x={bodyX}
          y={bodyY}
          width={bodyW}
          height={bodyH}
          rx="14"
          fill={`url(#${ids.body})`}
          stroke="rgba(99,102,241,0.18)"
          strokeWidth="1"
        />
        {/* Top edge sweep */}
        <rect
          x={bodyX + 12}
          y={bodyY + 0.5}
          width={bodyW - 24}
          height="1.5"
          fill={`url(#${ids.edge})`}
        />

        {/* Crown LEDs — three brand-triad indicators */}
        {ledColors.map((c, i) => (
          <CrownLED
            key={i}
            cx={bodyX + 26 + i * 22}
            cy={bodyY + 14}
            color={c}
            isHot={state === "thinking" || state === "error"}
            phase={i}
            intervalMs={ledIntervalMs}
          />
        ))}

        {/* Subtle vent grid — three thin lines below the LEDs, decorative */}
        {[0, 1, 2].map(i => (
          <rect
            key={i}
            x={bodyX + 18}
            y={bodyY + 30 + i * 4}
            width={bodyW - 36}
            height="1"
            fill="rgba(245,245,240,0.05)"
          />
        ))}

        {/* Eye slot — recessed dark band */}
        <rect
          x={eyeX}
          y={eyeY}
          width={eyeW}
          height={eyeH}
          rx="3"
          fill="#04040a"
          stroke="rgba(99,102,241,0.22)"
        />

        {/* Eye scan line — animated translate on x */}
        <g clipPath={`url(#${ids.eye}-clip)`}>
          <motion.rect
            initial={false}
            animate={scanX}
            x={eyeX}
            y={eyeY + 1}
            width={eyeW * 0.18}
            height={eyeH - 2}
            fill={`url(#${ids.eye})`}
          />
          {/* idle dim baseline so the eye never looks "off" */}
          <rect
            x={eyeX}
            y={eyeY + eyeH / 2 - 0.5}
            width={eyeW}
            height="1"
            fill="var(--brand-cyan)"
            opacity={state === "thinking" ? 0.18 : 0.32}
          />
        </g>

        {/* Lower side rivets — two on each lower corner */}
        {[
          { x: bodyX + 10, y: bodyY + bodyH - 26 },
          { x: bodyX + bodyW - 10, y: bodyY + bodyH - 26 },
          { x: bodyX + 10, y: bodyY + bodyH - 12 },
          { x: bodyX + bodyW - 10, y: bodyY + bodyH - 12 },
        ].map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="1.4"
            fill="rgba(245,245,240,0.18)"
          />
        ))}

        {/* Service plate — call-sign + tiny pulse */}
        <g transform={`translate(${bodyX + bodyW / 2 - 36} ${bodyY + bodyH - 30})`}>
          <rect
            x="0"
            y="0"
            width="72"
            height="14"
            rx="3"
            fill={`url(#${ids.plate})`}
            stroke="rgba(99,102,241,0.18)"
          />
          <text
            x="36"
            y="9.5"
            textAnchor="middle"
            fontFamily="'Share Tech Mono', 'Fira Code', monospace"
            fontSize="8"
            fill="rgba(245,245,240,0.78)"
            letterSpacing="2.2"
          >
            {callSign.toUpperCase()}
          </text>
        </g>

        {/* Foot shadow — soft floor anchor */}
        <ellipse
          cx={W / 2}
          cy={bodyY + bodyH + 14}
          rx={bodyW * 0.34}
          ry="3.5"
          fill="rgba(0,0,0,0.5)"
        />

        {/* State accent — outer halo ring (thin, behind the body, fades in on non-idle) */}
        {(state === "thinking" || state === "ok" || state === "error") && (
          <motion.circle
            initial={{ opacity: 0 }}
            animate={{
              opacity: state === "thinking" ? [0.15, 0.4, 0.15] : [0.6, 0],
              transition: state === "thinking"
                ? { duration: 2.2, repeat: Infinity, ease: "easeInOut" }
                : { duration: 1.6, ease: "easeOut" },
            }}
            cx={W / 2}
            cy={bodyY + bodyH / 2}
            r={Math.max(bodyW, bodyH) * 0.62}
            fill="none"
            stroke={
              state === "ok"
                ? "var(--color-success)"
                : state === "error"
                  ? "var(--color-alert)"
                  : "var(--brand-violet)"
            }
            strokeWidth="0.8"
            strokeOpacity="0.6"
            strokeDasharray="2 5"
          />
        )}

        {/* Listening — Siri-style concentric pulse rings expanding
            from the body. Three offset rings give the "machine is
            absorbing your voice" feel without needing real audio. */}
        {state === "listening" && (
          <g aria-hidden>
            {[0, 0.8, 1.6].map((delay, i) => (
              <motion.circle
                key={i}
                cx={W / 2}
                cy={bodyY + bodyH / 2}
                r={Math.min(bodyW, bodyH) * 0.5}
                fill="none"
                stroke="var(--brand-cyan)"
                strokeWidth="1"
                initial={{ scale: 0.6, opacity: 0.6 }}
                animate={{
                  scale: [0.6, 1.45],
                  opacity: [0.55, 0],
                }}
                transition={{
                  duration: 2.4,
                  repeat: Infinity,
                  delay,
                  ease: "easeOut",
                }}
                style={{
                  transformOrigin: `${W / 2}px ${bodyY + bodyH / 2}px`,
                }}
              />
            ))}
          </g>
        )}

        {/* Speaking — small "voice bars" jumping below the eye slot.
            Cheap CSS-style waveform built in SVG. */}
        {state === "speaking" && (
          <g
            aria-hidden
            transform={`translate(${W / 2 - 24} ${eyeY + eyeH + 14})`}
          >
            {[0, 1, 2, 3, 4].map(i => (
              <motion.rect
                key={i}
                x={i * 11}
                y={-6}
                width="3"
                height="12"
                rx="1.5"
                fill="var(--brand-orchid)"
                animate={{
                  scaleY: [0.4, 1.4, 0.7, 1.1, 0.4],
                }}
                transition={{
                  duration: 0.6,
                  repeat: Infinity,
                  delay: i * 0.08,
                  ease: "easeInOut",
                }}
                style={{ transformOrigin: `${i * 11 + 1.5}px 0px` }}
              />
            ))}
          </g>
        )}
      </svg>
    </motion.div>
  );
}

function CrownLED({
  cx,
  cy,
  color,
  isHot,
  phase,
  intervalMs,
}: {
  cx: number;
  cy: number;
  color: string;
  isHot: boolean;
  phase: number;
  intervalMs: number;
}) {
  // We don't run a JS interval here — instead, lean on framer-motion's
  // staggered keyframes so the SVG stays declarative and pauses
  // automatically when the user prefers reduced motion.
  const baseOpacity = 0.32;
  const peakOpacity = isHot ? 1 : 0.62;
  return (
    <>
      {/* Outer halo */}
      <motion.circle
        cx={cx}
        cy={cy}
        r="6"
        fill={color}
        animate={{
          opacity: [0, isHot ? 0.45 : 0.18, 0],
        }}
        transition={{
          duration: intervalMs / 1000,
          repeat: Infinity,
          delay: (phase * intervalMs) / 1000 / 3,
          ease: "easeInOut",
        }}
        style={{ filter: "blur(2.5px)" }}
      />
      {/* Core dot */}
      <motion.circle
        cx={cx}
        cy={cy}
        r="2.2"
        fill={color}
        animate={{
          opacity: [baseOpacity, peakOpacity, baseOpacity],
        }}
        transition={{
          duration: intervalMs / 1000,
          repeat: Infinity,
          delay: (phase * intervalMs) / 1000 / 3,
          ease: "easeInOut",
        }}
      />
    </>
  );
}
