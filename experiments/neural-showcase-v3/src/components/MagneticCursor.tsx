import { useEffect, useRef, useState } from "react";

const HOVER_SELECTOR = 'a, button, [role="button"], [data-magnetic]';

export function MagneticCursor() {
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;

    setEnabled(true);

    let ringX = window.innerWidth / 2;
    let ringY = window.innerHeight / 2;
    let mouseX = ringX;
    let mouseY = ringY;
    let scale = 1;
    let scaleTarget = 1;
    let raf = 0;

    const onMove = (e: PointerEvent) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (dot.current) {
        dot.current.style.transform = `translate3d(${mouseX}px, ${mouseY}px, 0) translate(-50%, -50%)`;
      }
    };

    const tick = () => {
      ringX += (mouseX - ringX) * 0.18;
      ringY += (mouseY - ringY) * 0.18;
      scale += (scaleTarget - scale) * 0.18;
      if (ring.current) {
        ring.current.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%) scale(${scale})`;
      }
      raf = requestAnimationFrame(tick);
    };

    const onEnter = (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (target && target.closest(HOVER_SELECTOR)) {
        scaleTarget = 2.2;
        ring.current?.classList.add("is-hot");
      }
    };
    const onLeave = (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (target && target.closest(HOVER_SELECTOR)) {
        scaleTarget = 1;
        ring.current?.classList.remove("is-hot");
      }
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("mouseover", onEnter, true);
    document.addEventListener("mouseout", onLeave, true);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("mouseover", onEnter, true);
      document.removeEventListener("mouseout", onLeave, true);
    };
  }, []);

  if (!enabled) return null;

  return (
    <>
      <div
        ref={dot}
        aria-hidden
        className="tars-cursor-dot pointer-events-none fixed left-0 top-0 z-[100] h-1.5 w-1.5 rounded-full bg-accent mix-blend-screen"
        style={{
          boxShadow: "0 0 12px var(--color-accent-soft)",
          willChange: "transform",
        }}
      />
      <div
        ref={ring}
        aria-hidden
        className="tars-cursor-ring pointer-events-none fixed left-0 top-0 z-[99] h-9 w-9 rounded-full border border-accent/45 mix-blend-screen transition-[border-color] duration-200"
        style={{ willChange: "transform" }}
      />
    </>
  );
}
