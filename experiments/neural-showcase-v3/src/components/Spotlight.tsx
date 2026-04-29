import { motion } from "framer-motion";

/**
 * Spotlight — Aceternity-style ambient cone of light.
 *
 * Pure SVG with a radial gradient. No JS, no canvas. Renders once,
 * the position is animated via framer-motion's transform stack.
 *
 * Designed to anchor the upper-left of the hero in indigo + violet,
 * casting soft directional light behind the headline.
 */
interface Props {
  className?: string;
  fill?: string;
  side?: "left" | "right";
}

export function Spotlight({
  className,
  fill = "#6366F1",
  side = "left",
}: Props) {
  return (
    <motion.svg
      initial={{ opacity: 0, x: side === "left" ? -40 : 40 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1] }}
      className={`pointer-events-none absolute z-0 ${className ?? ""}`}
      viewBox="0 0 3787 2842"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        transform: side === "right" ? "scaleX(-1)" : undefined,
      }}
      aria-hidden
    >
      <g filter="url(#spotlight-blur)">
        <ellipse
          cx="1924.71"
          cy="273.501"
          rx="1924.71"
          ry="273.501"
          transform="matrix(-0.822377 -0.568943 -0.568943 0.822377 3631.88 2291.09)"
          fill={fill}
          fillOpacity="0.2"
        />
      </g>
      <defs>
        <filter
          id="spotlight-blur"
          x="0.860352"
          y="0.838989"
          width="3785.16"
          height="2840.26"
          filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB"
        >
          <feFlood floodOpacity="0" result="BackgroundImageFix" />
          <feBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <feGaussianBlur stdDeviation="151" result="effect1_foregroundBlur" />
        </filter>
      </defs>
    </motion.svg>
  );
}
