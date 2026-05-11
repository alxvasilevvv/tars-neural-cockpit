import { Routes, Route, Navigate, useLocation } from "react-router-dom";
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
const SettingsPage = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
// Wave 80-D — Generic 4-phase workshop wizard. Lazy so the heavy
// composer/designer/backtest panels only ship when the operator opens
// /workshop. Wave 113 — fix: this lazy import was missing, causing
// "Workshop is not defined" 500 on production /workshop and any page
// embedding the WorkshopTutorial (which had Workshop in its component
// stack via the / route's error boundary).
const Workshop = lazy(() =>
  import("@/pages/Workshop").then((m) => ({ default: m.Workshop })),
);
// Wave 116 — caught by the new pre-build route-import lint:
// `<Compliance />` was rendered on line 463 but never lazy-imported,
// so /compliance would have 500'd in prod the same way /workshop did
// in Wave 114. Lint script flagged it; this declaration fixes it.
const Compliance = lazy(() =>
  import("@/pages/Compliance").then((m) => ({ default: m.Compliance })),
);
const EnterpriseWorkshop = lazy(() =>
  import("@/pages/EnterpriseWorkshop").then((m) => ({
    default: m.EnterpriseWorkshop,
  })),
);
// Wave 84 — Workshop ROI calculator. Lazy-loaded to keep the main
// landing bundle tight; the calculator only ships when fund partners
// drill in via /workshop/roi or the Cmd+K palette.
const WorkshopROI = lazy(() =>
  import("@/pages/WorkshopROI").then((m) => ({ default: m.WorkshopROI })),
);
// Wave 85 — Workshop materials hub (decks, recipes, videos, community).
const WorkshopMaterials = lazy(() =>
  import("@/pages/WorkshopMaterials").then((m) => ({
    default: m.WorkshopMaterials,
  })),
);
// Wave 88 — Workshop pre-flight self-assessment quiz. Twelve Likert
// questions across LLM/Python/Trading/Audit, lazy so the chunk only
// ships when an attendee actually opens the URL.
const WorkshopAssess = lazy(() =>
  import("@/pages/WorkshopAssess").then((m) => ({
    default: m.WorkshopAssess,
  })),
);
// Wave 89 — Facilitator cohort dashboard. Internal-facing surface
// (the meeet.world team running a workshop). Lazy + wide variant so
// the dense table + right rail get the full marketing-bleed width.
const WorkshopCohort = lazy(() =>
  import("@/pages/WorkshopCohort").then((m) => ({
    default: m.WorkshopCohort,
  })),
);
// Wave 96 - Reporting dashboard. Wide variant so the 12-col widget
// grid gets the full marketing-bleed width.
const Dashboard = lazy(() =>
  import("@/pages/Dashboard").then((m) => ({ default: m.Dashboard })),
);
// Wave 97 - Scheduler page. Default variant (table + detail panel).
const Schedules = lazy(() =>
  import("@/pages/Schedules").then((m) => ({ default: m.Schedules })),
);
// Wave 98 - Outreach (email drafting + Gmail send + HIL gate). Wide variant
// for the three-column drafts/approved/sent layout.
const Outreach = lazy(() =>
  import("@/pages/Outreach").then((m) => ({ default: m.Outreach })),
);
// Wave 99 - Org onboarding wizard. Narrow variant: 5-step single-column
// wizard for new fund/company setup.
const OrgOnboarding = lazy(() =>
  import("@/pages/OrgOnboarding").then((m) => ({ default: m.OrgOnboarding })),
);
// Wave 101 - Unified HIL approval inbox. Wide variant for the table
// + side panel layout.
const Inbox = lazy(() =>
  import("@/pages/Inbox").then((m) => ({ default: m.Inbox })),
);
// Wave 102 — /files document & file management surface.
const Files = lazy(() =>
  import("@/pages/Files").then((m) => ({ default: m.Files })),
);
// Wave 103 — /reports report export module (PDF/PPTX/XLSX/DOCX).
const Reports = lazy(() =>
  import("@/pages/Reports").then((m) => ({ default: m.Reports })),
);
// Wave 106 — /marketplace community registry + browse + install.
const Marketplace = lazy(() =>
  import("@/pages/Marketplace").then((m) => ({ default: m.Marketplace })),
);
// Wave 107 — /bundles per-org-type vertical bundle installer.
const Bundles = lazy(() =>
  import("@/pages/Bundles").then((m) => ({ default: m.Bundles })),
);
// Wave 108 — /admin/perf operational health dashboard.
const PerfDashboard = lazy(() =>
  import("@/pages/PerfDashboard").then((m) => ({ default: m.PerfDashboard })),
);
// Wave 110 — /workspaces multi-tenant Workspaces management surface.
// Wide variant: list + detail panel. Schema-only foundation; fencing
// arrives in v9.3.
const Workspaces = lazy(() =>
  import("@/pages/Workspaces").then((m) => ({ default: m.Workspaces })),
);
const WorkspaceInviteAccept = lazy(() =>
  import("@/pages/Workspaces").then((m) => ({
    default: m.WorkspaceInviteAccept,
  })),
);
// Wave 129 — Cowork (multiplayer agent sessions). Three named exports
// from one module: list (Cowork), single session (CoworkSession), and
// recipient accept screen (CoworkHandoffAccept). Lazy-imported as 3
// chunks via the same file so the bundle doesn't bloat the marketing
// surface — only loaded when /cowork/* routes are visited.
const Cowork = lazy(() =>
  import("@/pages/Cowork").then((m) => ({ default: m.Cowork })),
);
const CoworkSession = lazy(() =>
  import("@/pages/Cowork").then((m) => ({ default: m.CoworkSession })),
);
const CoworkHandoffAccept = lazy(() =>
  import("@/pages/Cowork").then((m) => ({ default: m.CoworkHandoffAccept })),
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
            {/* Wave 66 — Cockpit removed from public marketing surface
                (Nav link, StickyCTA, Landing's CockpitLive section all
                gone), but routes remain functional. CockpitGate already
                gates the cockpit: browser visitors see a Download CTA
                instead of the real cockpit; only the Tauri desktop
                shell + operators with a local daemon ever see the live
                surface. So we don't need to redirect /cockpit/* — the
                gate handles it correctly in both contexts. */}
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
              path="/settings"
              element={
                <Suspense fallback={<RouteSkeleton variant="legal" />}>
                  <SettingsPage />
                </Suspense>
              }
            />
            {/* Wave 80-D — Workshop + Compliance, lazy-loaded. */}
            <Route
              path="/workshop"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Workshop />
                </Suspense>
              }
            />
            <Route
              path="/compliance"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Compliance />
                </Suspense>
              }
            />
            <Route
              path="/workshop/enterprise"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <EnterpriseWorkshop />
                </Suspense>
              }
            />
            {/* Wave 87 — backward-compat redirect. The legacy
                /workshop/cresco URL was used as a workshop example;
                preserve external links by redirecting to the generic
                /workshop/enterprise surface. */}
            <Route
              path="/workshop/cresco"
              element={<Navigate to="/workshop/enterprise" replace />}
            />
            {/* Wave 84 — Workshop ROI calculator. Lives under /workshop/*
                so the breadcrumb (Home → Workshop → ROI calculator) and
                the lazy-route bundle name read consistently. */}
            <Route
              path="/workshop/roi"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <WorkshopROI />
                </Suspense>
              }
            />
            {/* Wave 85 — Workshop materials hub. Same /workshop/*
                breadcrumb pattern; precached by the SW (see public/sw.js). */}
            <Route
              path="/workshop/materials"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <WorkshopMaterials />
                </Suspense>
              }
            />
            {/* Wave 88 — Workshop self-assessment quiz. Narrow column
                layout — one question per screen, so the skeleton uses
                the new `narrow` variant which mirrors the 640px
                article width + Likert row. */}
            <Route
              path="/workshop/assess"
              element={
                <Suspense fallback={<RouteSkeleton variant="narrow" />}>
                  <WorkshopAssess />
                </Suspense>
              }
            />
            {/* Wave 89 — Facilitator cohort dashboard. Wide variant so
                the table + right rail share the full marketing-bleed
                width. Internal surface — not linked from the public
                Nav, only from Cmd+K and the Workshop materials hub. */}
            <Route
              path="/workshop/cohort"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <WorkshopCohort />
                </Suspense>
              }
            />
            {/* Wave 96 - Reporting dashboard. Wide variant for the
                12-col widget grid. */}
            <Route
              path="/dashboard"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Dashboard />
                </Suspense>
              }
            />
            {/* Wave 97 - Schedules page. Default variant: table +
                detail panel + new-schedule dialog. */}
            <Route
              path="/schedules"
              element={
                <Suspense fallback={<Loading />}>
                  <Schedules />
                </Suspense>
              }
            />
            {/* Wave 98 - Outreach. Wide variant: three columns + templates +
                campaigns. */}
            <Route
              path="/outreach"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Outreach />
                </Suspense>
              }
            />
            {/* Wave 99 - Org onboarding wizard. Narrow variant: 5-step
                single-column wizard from /onboard/org. */}
            <Route
              path="/onboard/org"
              element={
                <Suspense fallback={<RouteSkeleton variant="narrow" />}>
                  <OrgOnboarding />
                </Suspense>
              }
            />
            {/* Wave 101 - Unified HIL approval inbox. Wide variant
                for the table + side panel layout. */}
            <Route
              path="/inbox"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Inbox />
                </Suspense>
              }
            />
            {/* Wave 102 — /files document & file management surface. */}
            <Route
              path="/files"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Files />
                </Suspense>
              }
            />
            {/* Wave 103 — /reports report export module (PDF/PPTX/XLSX/DOCX). */}
            <Route
              path="/reports"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Reports />
                </Suspense>
              }
            />
            {/* Wave 106 — /marketplace community registry. */}
            <Route
              path="/marketplace"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Marketplace />
                </Suspense>
              }
            />
            {/* Wave 107 — /bundles vertical templates. */}
            <Route
              path="/bundles"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Bundles />
                </Suspense>
              }
            />
            <Route
              path="/bundles/:bundleId"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Bundles />
                </Suspense>
              }
            />
            {/* Wave 108 — /admin/perf operational health dashboard. */}
            <Route
              path="/admin/perf"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <PerfDashboard />
                </Suspense>
              }
            />
            {/* Wave 110 — Workspaces multi-tenant management. Wide
                variant for the 320 / fluid two-column list + detail
                layout. Plus a public token-auth invite-accept route. */}
            <Route
              path="/workspaces"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Workspaces />
                </Suspense>
              }
            />
            <Route
              path="/workspaces/invite/:token"
              element={
                <Suspense fallback={<RouteSkeleton variant="narrow" />}>
                  <WorkspaceInviteAccept />
                </Suspense>
              }
            />
            {/* Wave 129 — Cowork: multiplayer agent sessions. Three
                routes: list, single session, recipient accept page. */}
            <Route
              path="/cowork"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <Cowork />
                </Suspense>
              }
            />
            <Route
              path="/cowork/handoff/:token"
              element={
                <Suspense fallback={<RouteSkeleton variant="narrow" />}>
                  <CoworkHandoffAccept />
                </Suspense>
              }
            />
            <Route
              path="/cowork/:slug"
              element={
                <Suspense fallback={<RouteSkeleton variant="wide" />}>
                  <CoworkSession />
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
