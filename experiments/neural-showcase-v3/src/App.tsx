import { Routes, Route, useLocation } from "react-router-dom";
import { Suspense, lazy, useEffect } from "react";
import { trackPageView } from "@/lib/analytics";
import { useTarsDeepLink } from "@/lib/useTarsDeepLink";
import { AnimatePresence, motion } from "framer-motion";
import { Brackets } from "@/components/Brackets";
import { CockpitGate } from "@/components/CockpitGate";
import { Nav } from "@/components/Nav";
import { Atmosphere } from "@/components/Atmosphere";
import { MagneticCursor } from "@/components/MagneticCursor";
import { GlobalCommandPalette } from "@/components/GlobalCommandPalette";
import { RouteTransition } from "@/components/RouteTransition";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ScrollHint } from "@/components/ScrollHint";
import { CookieConsent } from "@/components/CookieConsent";
import { RouteSkeleton } from "@/components/RouteSkeleton";
import { StickyCTA } from "@/components/StickyCTA";
import { ToastBus } from "@/components/ToastBus";
import { KeyboardOverlay } from "@/components/KeyboardOverlay";
import { SidecarStatusBadge } from "@/components/SidecarStatusBadge";

const Landing = lazy(() =>
  import("@/pages/Landing").then((m) => ({ default: m.Landing })),
);
const Cockpit = lazy(() =>
  import("@/pages/Cockpit").then((m) => ({ default: m.Cockpit })),
);
const Planner = lazy(() =>
  import("@/pages/Planner").then((m) => ({ default: m.Planner })),
);
const Traces = lazy(() =>
  import("@/pages/Traces").then((m) => ({ default: m.Traces })),
);
const Policy = lazy(() =>
  import("@/pages/Policy").then((m) => ({ default: m.Policy })),
);
const Council = lazy(() =>
  import("@/pages/Council").then((m) => ({ default: m.Council })),
);
const Awareness = lazy(() =>
  import("@/pages/Awareness").then((m) => ({ default: m.Awareness })),
);
const Install = lazy(() =>
  import("@/pages/Install").then((m) => ({ default: m.Install })),
);
const Onboarding = lazy(() =>
  import("@/pages/Onboarding").then((m) => ({ default: m.Onboarding })),
);
const Privacy = lazy(() =>
  import("@/pages/Privacy").then((m) => ({ default: m.Privacy })),
);
const Terms = lazy(() =>
  import("@/pages/Terms").then((m) => ({ default: m.Terms })),
);
const Security = lazy(() =>
  import("@/pages/Security").then((m) => ({ default: m.Security })),
);
const Pitch = lazy(() =>
  import("@/pages/Pitch").then((m) => ({ default: m.Pitch })),
);
const Press = lazy(() =>
  import("@/pages/Press").then((m) => ({ default: m.Press })),
);
const Docs = lazy(() =>
  import("@/pages/Docs").then((m) => ({ default: m.Docs })),
);
const Status = lazy(() =>
  import("@/pages/Status").then((m) => ({ default: m.Status })),
);
const NotFound = lazy(() =>
  import("@/pages/NotFound").then((m) => ({ default: m.NotFound })),
);
const Roadmap = lazy(() =>
  import("@/pages/Roadmap").then((m) => ({ default: m.Roadmap })),
);
const Changelog = lazy(() =>
  import("@/pages/Changelog").then((m) => ({ default: m.Changelog })),
);
const BuildWith = lazy(() =>
  import("@/pages/BuildWith").then((m) => ({ default: m.BuildWith })),
);
const PricingPage = lazy(() =>
  import("@/pages/PricingPage").then((m) => ({ default: m.PricingPage })),
);
const FAQPage = lazy(() =>
  import("@/pages/FAQPage").then((m) => ({ default: m.FAQPage })),
);
const ComparePage = lazy(() =>
  import("@/pages/ComparePage").then((m) => ({ default: m.ComparePage })),
);

// Default skeleton for routes that don't pin a specific layout shape.
const Loading = () => <RouteSkeleton variant="default" />;

// Route entrance: opacity only. Avoid `transform` on this wrapper — any non-none
// transform creates a containing block and breaks `position: sticky` deep in
// marketing sections (e.g. ScrollStory pinned track).
const variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
  exit: { opacity: 0 },
};

function AppShell() {
  const loc = useLocation();
  // ScrollHint shown only on landing — Hero is the relevant fold there.
  const showScrollHint = loc.pathname === "/";

  // Emit `tars.page.view` for every route change. Pre-launch the events
  // queue locally; once brother lands /api/log they drain on next batch.
  useEffect(() => {
    trackPageView(loc.pathname + loc.search);
  }, [loc.pathname, loc.search]);

  // Wave 59 — Tauri desktop deep-link routing. Cheap no-op in browser
  // builds (gated by typeof __TAURI_INTERNALS__).
  useTarsDeepLink();
  return (
    <main className="relative min-h-screen bg-bg-0 text-ink">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Atmosphere />
      <Brackets />
      <MagneticCursor />
      <Nav />
      <GlobalCommandPalette />
      <KeyboardOverlay />
      <RouteTransition />
      <StickyCTA />
      <CookieConsent />
      <ToastBus />
      <SidecarStatusBadge />
      {showScrollHint && <ScrollHint />}
      <AnimatePresence mode="wait">
        <motion.div
          id="main"
          key={loc.pathname}
          initial="hidden"
          animate="show"
          exit="exit"
          variants={variants}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        >
          <Routes location={loc} key={loc.pathname}>
            <Route
              path="/"
              element={
                <Suspense fallback={<RouteSkeleton variant="hero" />}>
                  <Landing />
                </Suspense>
              }
            />
            <Route
              path="/cockpit"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Cockpit />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/cockpit/planner"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Planner />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/cockpit/traces"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Traces />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/cockpit/policy"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Policy />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/cockpit/council"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Council />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/cockpit/awareness"
              element={
                <CockpitGate>
                  <Suspense fallback={<RouteSkeleton variant="cockpit" />}>
                    <Awareness />
                  </Suspense>
                </CockpitGate>
              }
            />
            <Route
              path="/install"
              element={
                <Suspense fallback={<RouteSkeleton variant="hero" />}>
                  <Install />
                </Suspense>
              }
            />
            <Route
              path="/onboarding"
              element={
                <Suspense fallback={<RouteSkeleton variant="default" />}>
                  <Onboarding />
                </Suspense>
              }
            />
            <Route
              path="/pricing"
              element={
                <Suspense fallback={<RouteSkeleton variant="default" />}>
                  <PricingPage />
                </Suspense>
              }
            />
            <Route
              path="/faq"
              element={
                <Suspense fallback={<RouteSkeleton variant="default" />}>
                  <FAQPage />
                </Suspense>
              }
            />
            <Route
              path="/compare"
              element={
                <Suspense fallback={<RouteSkeleton variant="default" />}>
                  <ComparePage />
                </Suspense>
              }
            />
            <Route
              path="/privacy"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <Privacy />
                </Suspense>
              }
            />
            <Route
              path="/terms"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <Terms />
                </Suspense>
              }
            />
            <Route
              path="/security"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <Security />
                </Suspense>
              }
            />
            <Route
              path="/pitch"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Pitch />
                </Suspense>
              }
            />
            <Route
              path="/press"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Press />
                </Suspense>
              }
            />
            <Route
              path="/docs"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Docs />
                </Suspense>
              }
            />
            <Route
              path="/status"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Status />
                </Suspense>
              }
            />
            <Route
              path="/roadmap"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <Roadmap />
                </Suspense>
              }
            />
            <Route
              path="/changelog"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <Changelog />
                </Suspense>
              }
            />
            <Route
              path="/build-with"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <BuildWith />
                </Suspense>
              }
            />
            <Route
              path="*"
              element={
                <Suspense fallback={<Loading />}>
                  <NotFound />
                </Suspense>
              }
            />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </main>
  );
}

/**
 * Default export — wraps the shell in a global ErrorBoundary so that
 * a render error anywhere under <main> renders a brand-styled fallback
 * instead of a blank page.
 */
export default function App() {
  return (
    <ErrorBoundary>
      <AppShell />
    </ErrorBoundary>
  );
}
