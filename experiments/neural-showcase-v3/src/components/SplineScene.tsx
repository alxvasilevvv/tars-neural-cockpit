"use client";

import {
  Component,
  type ErrorInfo,
  type ReactNode,
  Suspense,
  lazy,
  useEffect,
  useRef,
  useState,
} from "react";

// Bug #7 from docs/SYSTEM_AUDIT_2026-05-02.md — react-spline ships
// at 2.04 MB (uncompressed) so we want it nowhere near the
// landing-page critical path. The lazy() import is already
// async, but Vite still triggers the chunk request the moment
// the component is rendered. The IntersectionObserver guard
// below defers the chunk request until the host viewport has
// the placeholder in (or near) view, so first-paint chunks
// stay tiny and slow connections never block on the 3D scene.
const Spline = lazy(() => import("@splinetool/react-spline"));

export interface SplineSceneProps {
  scene: string;
  className?: string;
  /**
   * Pixels of margin around the host element used by the
   * IntersectionObserver root. ``"600px"`` defaults give the
   * runtime ~2-3 frames to start downloading before the
   * placeholder enters the visible viewport, so the swap looks
   * smooth on a fast connection without paying the ~600 KB
   * gzip cost on first paint when the user might never scroll
   * to MeetTars at all.
   */
  rootMargin?: string;
}

/**
 * Fallback robot silhouette. Pure SVG, no network, no JS deps. Used when:
 *   - Spline cloud (prod.spline.design) is unreachable / 403 / 5xx
 *   - The Spline runtime crashes (rare, but happened in the field)
 *   - The Suspense boot exceeds 8s (slow connection)
 *
 * Visually carries the meeet brand triad — indigo / violet / brand cyan —
 * so the section stays visually intact even when the 3D layer fails.
 */
function RobotFallback({ className }: { className?: string }) {
  return (
    <div
      className={`relative grid h-full w-full place-items-center ${className ?? ""}`}
      role="img"
      aria-label="TARS robot character (offline silhouette)"
    >
      {/* Halo */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 50% 45% at 50% 48%, rgba(139,92,246,0.32) 0%, transparent 60%)",
          filter: "blur(20px)",
        }}
      />
      <svg
        viewBox="0 0 320 360"
        className="relative max-h-[80%] w-auto"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="robotBody" x1="0" y1="0" x2="320" y2="360" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#6366F1" />
            <stop offset="0.5" stopColor="#8B5CF6" />
            <stop offset="1" stopColor="#06B6D4" />
          </linearGradient>
          <radialGradient id="robotEye" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#06B6D4" stopOpacity="0.95" />
            <stop offset="0.7" stopColor="#06B6D4" stopOpacity="0.4" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Orbit rings */}
        <g fill="none" stroke="url(#robotBody)" strokeWidth="0.8" opacity="0.35">
          <ellipse cx="160" cy="180" rx="140" ry="40" />
          <ellipse cx="160" cy="180" rx="115" ry="28" transform="rotate(-12 160 180)" />
        </g>

        {/* Head plate */}
        <g>
          <rect
            x="60" y="40" rx="22" ry="22" width="200" height="160"
            fill="none" stroke="url(#robotBody)" strokeWidth="2.4"
          />
          <rect x="60" y="40" rx="22" ry="22" width="200" height="160" fill="#0b0b10" opacity="0.85" />
          {/* visor */}
          <rect x="80" y="80" rx="14" ry="14" width="160" height="64" fill="#000" stroke="url(#robotBody)" strokeWidth="1.6" />
          {/* single cyclops eye */}
          <circle cx="160" cy="112" r="22" fill="url(#robotEye)" />
          <circle cx="160" cy="112" r="6" fill="#06B6D4">
            <animate attributeName="r" values="6;7.6;6" dur="2.6s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.85;1;0.85" dur="2.6s" repeatCount="indefinite" />
          </circle>
          {/* hud ticks */}
          <g stroke="#06B6D4" strokeWidth="1" opacity="0.55">
            <line x1="68" y1="60" x2="84" y2="60" />
            <line x1="236" y1="60" x2="252" y2="60" />
            <line x1="68" y1="180" x2="84" y2="180" />
            <line x1="236" y1="180" x2="252" y2="180" />
          </g>
          {/* mouth grille */}
          <g stroke="url(#robotBody)" strokeWidth="1" opacity="0.7">
            <line x1="120" y1="166" x2="200" y2="166" />
            <line x1="124" y1="174" x2="196" y2="174" />
            <line x1="128" y1="182" x2="192" y2="182" />
          </g>
        </g>

        {/* Neck */}
        <g>
          <rect x="135" y="200" width="50" height="14" fill="url(#robotBody)" opacity="0.6" />
          <rect x="125" y="214" width="70" height="10" fill="url(#robotBody)" opacity="0.4" />
        </g>

        {/* Shoulders */}
        <g fill="none" stroke="url(#robotBody)" strokeWidth="2">
          <path d="M 80 240 Q 160 220 240 240 L 240 280 L 80 280 Z" fill="#0b0b10" opacity="0.7" />
          <line x1="160" y1="220" x2="160" y2="280" opacity="0.4" />
        </g>

        {/* Status bar */}
        <g transform="translate(60 308)">
          <text x="0" y="0" fontFamily="'Fira Code', monospace" fontSize="9" fill="#7a786f" letterSpacing="2">
            TARS · OFFLINE PREVIEW
          </text>
          <rect x="0" y="10" width="200" height="2" fill="url(#robotBody)" opacity="0.5" />
          <rect x="0" y="10" width="80" height="2" fill="#06B6D4">
            <animate attributeName="x" values="0;200;0" dur="3.2s" repeatCount="indefinite" />
          </rect>
        </g>
      </svg>
    </div>
  );
}

/**
 * Error boundary scoped to the Spline runtime — catches anything thrown by
 * the lazy import or by the Spline scene renderer. Renders RobotFallback
 * if either path fails. Logs to console for debugging.
 */
class SplineBoundary extends Component<
  { children: ReactNode; onError: () => void; className?: string },
  { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(err: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.warn("[SplineScene] runtime error — falling back:", err.message, info.componentStack);
    this.props.onError();
  }
  render() {
    if (this.state.hasError) {
      return <RobotFallback className={this.props.className} />;
    }
    return this.props.children;
  }
}

export function SplineScene({
  scene,
  className,
  rootMargin = "600px",
}: SplineSceneProps) {
  // Bug #7 fix — defer the lazy import until the host element
  // approaches the viewport. Without this, first-paint pays the
  // 2 MB react-spline chunk even when the visitor never scrolls
  // past the hero.
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [shouldMount, setShouldMount] = useState(false);

  useEffect(() => {
    if (shouldMount) return; // already kicked off
    const host = hostRef.current;
    if (!host) return;

    // SSR / very old browsers (Safari < 12) — fall back to mount on
    // first effect tick, keeping the original behaviour.
    if (typeof IntersectionObserver === "undefined") {
      setShouldMount(true);
      return;
    }

    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShouldMount(true);
            obs.disconnect();
            break;
          }
        }
      },
      { rootMargin, threshold: 0 },
    );
    obs.observe(host);
    return () => obs.disconnect();
  }, [shouldMount, rootMargin]);

  // 8-second deadline: if Spline hasn't mounted by then, swap to fallback.
  // Common cause: prod.spline.design blocked by network / corp firewall.
  // Once `loaded=true` fires from onLoad, the deadline is ignored — Spline
  // wins and renders for the rest of the session. The deadline only starts
  // *after* shouldMount flips, so we don't punish off-screen sections.
  const [loaded, setLoaded] = useState(false);
  const [tooSlow, setTooSlow] = useState(false);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    if (!shouldMount) return;
    const t = setTimeout(() => setTooSlow(true), 8000);
    return () => clearTimeout(t);
  }, [shouldMount]);

  if (errored || (tooSlow && !loaded)) {
    return (
      <div ref={hostRef} className={className ?? "h-full w-full"}>
        <RobotFallback className={className} />
      </div>
    );
  }

  if (!shouldMount) {
    // Cheap placeholder so the layout never CLSes when the chunk
    // finally lands. The SVG fallback renders inside the same box.
    return (
      <div ref={hostRef} className={className ?? "h-full w-full"}>
        <RobotFallback className={className} />
      </div>
    );
  }

  return (
    <div ref={hostRef} className={className ?? "h-full w-full"}>
      <SplineBoundary onError={() => setErrored(true)} className={className}>
        <Suspense
          fallback={
            <div className="flex h-full w-full items-center justify-center">
              <span className="loader" aria-hidden />
            </div>
          }
        >
          <Spline scene={scene} className={className} onLoad={() => setLoaded(true)} />
        </Suspense>
      </SplineBoundary>
    </div>
  );
}
