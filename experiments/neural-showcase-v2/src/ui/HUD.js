import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function initHUD() {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll(".hud").forEach((el, i) => {
    if (reduce) {
      el.style.opacity = "1";
      return;
    }
    gsap.fromTo(
      el,
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.9, delay: 1.3 + i * 0.15, ease: "power2.out" },
    );
  });

  const integrity = document.querySelector("[data-hud-integrity]");
  if (integrity && !reduce) {
    const obj = { v: 87.2 };
    integrity.textContent = obj.v.toFixed(1);
    gsap.to(obj, {
      v: 99.4,
      duration: 2.2,
      delay: 1.5,
      ease: "power3.out",
      onUpdate() {
        integrity.textContent = obj.v.toFixed(1);
      },
    });
  }

  const heartbeats = document.querySelectorAll(".hud__bars span");
  heartbeats.forEach((el, i) => {
    if (reduce) return;
    gsap.to(el, {
      scaleY: () => 0.4 + Math.random() * 0.7,
      duration: 0.45,
      delay: i * 0.07,
      ease: "sine.inOut",
      yoyo: true,
      repeat: -1,
    });
  });

  const huds = document.querySelectorAll(".hud");
  ScrollTrigger.create({
    trigger: ".hero",
    start: "bottom 90%",
    onEnter: () => huds.forEach((h) => h.classList.add("is-min")),
    onLeaveBack: () => huds.forEach((h) => h.classList.remove("is-min")),
  });
}
