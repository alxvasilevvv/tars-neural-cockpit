/**
 * Full-screen ambient layer — minimalist per MASTER.md §1.4:
 *   "Decorative ambient: scanline opacity ≤ 0.04, only on the WebGL stage."
 *
 * Removed (were creating visual noise on every page):
 *   - Cyan rotating concentric rings (kinetic distraction)
 *   - Gold godray + cyan godray (mix-blend-screen tinted text)
 *   - Animated turbulence grain (CPU drain + flicker)
 *   - Heavy scanlines at opacity 0.08 (read-blocker)
 *
 * Kept:
 *   - Subtle top/bottom vignette for depth on OLED black.
 *   - Whisper-thin scanlines at opacity 0.025 (skill cap).
 */
export function Atmosphere() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-10 overflow-hidden"
    >
      {/* Top vignette for depth — pure dark, no colour cast. */}
      <div
        className="absolute inset-x-0 top-0 h-[24vh]"
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.55), transparent)",
        }}
      />

      {/* Bottom vignette mirrors the top for visual rhythm. */}
      <div
        className="absolute inset-x-0 bottom-0 h-[24vh]"
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.55), transparent)",
        }}
      />

      {/* Whisper-thin scanlines — opacity capped at skill threshold. */}
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(244,246,251,0.5) 0px, rgba(244,246,251,0.5) 1px, transparent 1px, transparent 4px)",
        }}
      />
    </div>
  );
}
