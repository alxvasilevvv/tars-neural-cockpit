/**
 * Decorative HUD corner brackets.
 * Source: design-system/tars/MASTER.md → "HUD / Sci-Fi FUI" rules.
 * 1px lines, single HUD colour (cyan), opacity 0.32 base, hidden < 880px.
 */

const Bracket = ({ d, className }: { d: string; className: string }) => (
  <svg
    viewBox="0 0 24 24"
    aria-hidden="true"
    className={`pointer-events-none fixed z-30 hidden h-5 w-5 fill-none [stroke-width:1.4] [animation:pulseSoft_3.4s_ease-in-out_infinite] md:block ${className}`}
    style={{ stroke: "var(--color-hud)" }}
  >
    <path d={d} />
  </svg>
);

export function Brackets() {
  return (
    <>
      <Bracket d="M2 9 L2 2 L9 2" className="left-[18px] top-[18px]" />
      <Bracket d="M22 9 L22 2 L15 2" className="right-[18px] top-[18px]" />
      <Bracket d="M2 15 L2 22 L9 22" className="left-[18px] bottom-[18px]" />
      <Bracket d="M22 15 L22 22 L15 22" className="right-[18px] bottom-[18px]" />
    </>
  );
}
