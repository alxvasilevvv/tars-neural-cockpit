import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function initReveals() {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll(".cards .card").forEach((el, i) => {
    if (reduce) {
      el.classList.add("in");
      return;
    }
    gsap.fromTo(
      el,
      { y: 40, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.9,
        ease: "power3.out",
        delay: (i % 3) * 0.05,
        scrollTrigger: { trigger: el, start: "top 85%" },
        onStart: () => el.classList.add("in"),
      },
    );
  });

  document.querySelectorAll(".domain-cards .domain").forEach((el, i) => {
    if (reduce) {
      el.classList.add("in");
      return;
    }
    gsap.fromTo(
      el,
      { y: 40, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.9,
        ease: "power3.out",
        delay: (i % 2) * 0.08,
        scrollTrigger: { trigger: el, start: "top 85%" },
        onStart: () => el.classList.add("in"),
      },
    );
  });

  document.querySelectorAll(".steps .step").forEach((el, i) => {
    if (reduce) {
      el.classList.add("in");
      return;
    }
    gsap.fromTo(
      el,
      { y: 40, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.9,
        ease: "power3.out",
        delay: i * 0.08,
        scrollTrigger: { trigger: el, start: "top 85%" },
        onStart: () => el.classList.add("in"),
      },
    );
  });
}

export function initCounters() {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fmt = new Intl.NumberFormat("en-US");
  document.querySelectorAll("[data-count]").forEach((el) => {
    const target = parseInt(el.dataset.count, 10);
    if (reduce) {
      el.textContent = formatBig(target, fmt);
      return;
    }
    const obj = { v: 0 };
    gsap.to(obj, {
      v: target,
      duration: 2,
      ease: "power3.out",
      scrollTrigger: { trigger: el, start: "top 90%" },
      onUpdate() {
        el.textContent = formatBig(Math.floor(obj.v), fmt);
      },
    });
  });
}

function formatBig(v, fmt) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(1) + "k";
  return fmt.format(v);
}
