import gsap from "gsap";

export function runLoader({ minDuration = 1400 } = {}) {
  return new Promise((resolve) => {
    const num = document.querySelector("[data-loader-num]");
    const start = performance.now();
    const obj = { v: 0 };
    gsap.to(obj, {
      v: 100,
      duration: minDuration / 1000,
      ease: "power2.inOut",
      onUpdate() {
        if (num) num.textContent = Math.round(obj.v);
      },
      onComplete() {
        const elapsed = performance.now() - start;
        const wait = Math.max(0, minDuration - elapsed);
        setTimeout(() => {
          document.body.classList.add("is-ready");
          resolve();
        }, wait);
      },
    });
  });
}

export function runIntro() {
  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
  tl.to(
    ".hero__title .word",
    {
      yPercent: 0,
      duration: 1.0,
      stagger: { each: 0.06, from: "start" },
    },
    0,
  )
    .to(
      ".hero__lead",
      { opacity: 1, y: 0, duration: 0.8 },
      0.4,
    )
    .to(
      ".hero__cta",
      { opacity: 1, y: 0, duration: 0.8 },
      0.55,
    )
    .to(
      ".hero__stats",
      { opacity: 1, y: 0, duration: 0.8 },
      0.7,
    );
  return tl;
}
