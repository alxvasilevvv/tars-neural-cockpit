import gsap from "gsap";

export function initCursor() {
  if (matchMedia("(hover: none)").matches) return;

  const cursor = document.querySelector(".cursor");
  if (!cursor) return;

  const xTo = gsap.quickTo(cursor, "x", { duration: 0.35, ease: "power3" });
  const yTo = gsap.quickTo(cursor, "y", { duration: 0.35, ease: "power3" });

  let mx = innerWidth / 2;
  let my = innerHeight / 2;

  addEventListener(
    "pointermove",
    (e) => {
      mx = e.clientX;
      my = e.clientY;
      xTo(mx);
      yTo(my);
    },
    { passive: true },
  );

  const magnets = document.querySelectorAll("[data-magnet]");
  magnets.forEach((el) => {
    const strength = 0.4;
    el.addEventListener("pointerenter", () => document.body.classList.add("is-hover"));
    el.addEventListener("pointerleave", () => {
      document.body.classList.remove("is-hover");
      gsap.to(el, { x: 0, y: 0, duration: 0.6, ease: "elastic.out(1,0.4)" });
    });
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = e.clientX - (r.left + r.width / 2);
      const y = e.clientY - (r.top + r.height / 2);
      gsap.to(el, { x: x * strength, y: y * strength, duration: 0.4, ease: "power3" });
    });
  });
}
