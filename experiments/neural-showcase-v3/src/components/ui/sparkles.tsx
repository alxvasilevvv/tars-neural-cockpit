"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/**
 * SparklesCore — canvas particle background.
 *
 * Visually equivalent to Aceternity's sparkles
 * (https://21st.dev/community/components/aceternity/sparkles/default)
 * but self-contained with zero external dependencies.
 *
 * Real Aceternity uses @tsparticles/react + @tsparticles/slim. To swap
 * to the official package later:
 *   npx shadcn@latest add "https://21st.dev/r/aceternity/sparkles"
 * The component name (`SparklesCore`) and prop API are kept identical, so
 * call-sites won't change.
 *
 * Respects `prefers-reduced-motion` — when set, particles render once
 * without twinkle.
 */

interface SparklesProps {
  /** CSS background; usually leave undefined and use parent bg. */
  background?: string;
  /** Smallest particle radius in px (default 0.4). */
  minSize?: number;
  /** Largest particle radius in px (default 1.4). */
  maxSize?: number;
  /** Particles per 10,000 px² (default 1.2 ≈ 200 on 1280×1024). */
  particleDensity?: number;
  /** Hex/rgb colour of particles. Default: theme `--color-ink`. */
  particleColor?: string;
  /** Speed multiplier for the twinkle (1 = default). */
  speed?: number;
  /** Optional id (unused, kept for API parity with Aceternity). */
  id?: string;
  /** Additional classes for the canvas wrapper. */
  className?: string;
}

interface Particle {
  x: number;
  y: number;
  r: number;          // radius
  base: number;       // base opacity
  phase: number;      // twinkle phase
  speed: number;      // twinkle speed
}

export const SparklesCore = ({
  background,
  minSize = 0.4,
  maxSize = 1.4,
  particleDensity = 1.2,
  particleColor = "#F5F5F0",
  speed = 1,
  className,
}: SparklesProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    let particles: Particle[] = [];
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let lastTime = performance.now();

    const seed = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);

      const target = Math.max(
        24,
        Math.round((w * h) / 10_000 * particleDensity),
      );
      particles = Array.from({ length: target }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: minSize + Math.random() * (maxSize - minSize),
        base: 0.18 + Math.random() * 0.62,
        phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 1.4,
      }));
    };

    const onResize = () => {
      // Reset transform before re-scaling on resize
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      seed();
    };

    const draw = (now: number) => {
      const dt = Math.min((now - lastTime) / 1000, 0.05);
      lastTime = now;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;

      ctx.clearRect(0, 0, w, h);
      if (background) {
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, w, h);
      }

      ctx.fillStyle = particleColor;
      for (const p of particles) {
        if (!reduceMotion) p.phase += dt * p.speed * speed * 1.4;
        const twinkle = reduceMotion
          ? p.base
          : p.base + Math.sin(p.phase) * 0.34;
        const a = Math.max(0, Math.min(1, twinkle));
        ctx.globalAlpha = a;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      if (!reduceMotion) {
        rafRef.current = requestAnimationFrame(draw);
      }
    };

    seed();
    rafRef.current = requestAnimationFrame(draw);
    window.addEventListener("resize", onResize);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", onResize);
    };
  }, [
    background,
    minSize,
    maxSize,
    particleDensity,
    particleColor,
    speed,
  ]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 h-full w-full",
        className,
      )}
    />
  );
};
