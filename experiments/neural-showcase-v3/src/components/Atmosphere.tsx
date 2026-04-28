/**
 * Full-screen ambient layer:
 *   - animated SVG turbulence grain (very low opacity)
 *   - hairline scanlines
 *   - two soft godray streaks
 *   - slow-rotating concentric guide ring at the hero center
 * All decoration; pointer-events: none.
 */
export function Atmosphere() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-10 overflow-hidden"
    >
      {/* Concentric guide rings echoing the WebGL core */}
      <svg
        viewBox="-100 -100 200 200"
        className="absolute left-1/2 top-[42vh] h-[120vh] w-[120vh] -translate-x-1/2 -translate-y-1/2 opacity-[0.28] mix-blend-screen"
      >
        <defs>
          <radialGradient id="ring-fade" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#67E8F9" stopOpacity="0" />
            <stop offset="55%" stopColor="#67E8F9" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#67E8F9" stopOpacity="0" />
          </radialGradient>
        </defs>
        <g
          fill="none"
          stroke="url(#ring-fade)"
          strokeWidth="0.18"
          style={{
            transformOrigin: "center",
            animation: "tars-spin 60s linear infinite",
          }}
        >
          <circle r="38" />
          <circle r="58" strokeDasharray="0.6 1.2" />
          <circle r="78" strokeDasharray="2 4" />
          <circle r="92" strokeDasharray="0.4 6" />
        </g>
      </svg>

      {/* Soft godray streaks */}
      <div
        className="absolute -left-[12vw] top-[-8vh] h-[68vh] w-[42vw] rotate-[18deg] mix-blend-screen"
        style={{
          background:
            "radial-gradient(closest-side, rgba(103,232,249,0.16), rgba(103,232,249,0) 70%)",
          filter: "blur(8px)",
        }}
      />
      <div
        className="absolute right-[-10vw] top-[24vh] h-[58vh] w-[40vw] -rotate-[16deg] mix-blend-screen"
        style={{
          background:
            "radial-gradient(closest-side, rgba(251,191,36,0.07), rgba(251,191,36,0) 70%)",
          filter: "blur(10px)",
        }}
      />

      {/* Scanlines (hairline horizontal lines) */}
      <div
        className="absolute inset-0 opacity-[0.08]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(244,246,251,0.28) 0px, rgba(244,246,251,0.28) 1px, transparent 1px, transparent 3px)",
          mixBlendMode: "overlay",
        }}
      />

      {/* Animated turbulence grain */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.07] mix-blend-overlay">
        <filter id="tars-noise">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            stitchTiles="stitch"
          >
            <animate
              attributeName="baseFrequency"
              dur="14s"
              values="0.85;1.15;0.85"
              repeatCount="indefinite"
            />
          </feTurbulence>
          <feColorMatrix
            type="matrix"
            values="0 0 0 0 0.95
                    0 0 0 0 0.96
                    0 0 0 0 1.00
                    0 0 0 0.95 0"
          />
        </filter>
        <rect width="100%" height="100%" filter="url(#tars-noise)" />
      </svg>
    </div>
  );
}
