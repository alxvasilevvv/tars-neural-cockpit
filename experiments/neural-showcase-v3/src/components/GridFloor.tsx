/**
 * GridFloor — receding tron-grid that anchors the bottom of the hero.
 *
 * Pure CSS (linear gradients + perspective). 0 JS, 0 deps. Subtle
 * scroll animation drives the grid towards the camera at constant
 * velocity, giving the hero a "moving floor" feel without burning
 * CPU.
 */
export function GridFloor({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-x-0 bottom-0 h-[60%] overflow-hidden ${className ?? ""}`}
      style={{
        maskImage:
          "linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.65) 35%, rgba(0,0,0,0) 100%)",
        WebkitMaskImage:
          "linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.65) 35%, rgba(0,0,0,0) 100%)",
      }}
    >
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `
            linear-gradient(to right, rgba(99,102,241,0.18) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(139,92,246,0.18) 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px",
          transform: "perspective(700px) rotateX(62deg) translateY(35%)",
          transformOrigin: "bottom center",
          animation: "gridScroll 12s linear infinite",
        }}
      />
      <style>{`
        @keyframes gridScroll {
          0%   { background-position: 0 0; }
          100% { background-position: 0 96px; }
        }
      `}</style>
    </div>
  );
}
