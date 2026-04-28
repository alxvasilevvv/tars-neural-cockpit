import { Routes, Route, useLocation } from "react-router-dom";
import { Suspense, lazy } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Brackets } from "@/components/Brackets";
import { Nav } from "@/components/Nav";
import { Atmosphere } from "@/components/Atmosphere";
import { MagneticCursor } from "@/components/MagneticCursor";

const Landing = lazy(() =>
  import("@/pages/Landing").then((m) => ({ default: m.Landing })),
);
const Cockpit = lazy(() =>
  import("@/pages/Cockpit").then((m) => ({ default: m.Cockpit })),
);

// Master.md motion rule: clean opacity/y entrance, no blur (heavy + flickers).
const variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

export default function App() {
  const loc = useLocation();
  return (
    <main className="relative min-h-screen bg-bg-0 text-ink">
      <Atmosphere />
      <Brackets />
      <MagneticCursor />
      <Nav />
      <AnimatePresence mode="wait">
        <motion.div
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
                <Suspense
                  fallback={
                    <div className="flex min-h-[50vh] items-center justify-center font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
                      loading…
                    </div>
                  }
                >
                  <Landing />
                </Suspense>
              }
            />
            <Route
              path="/cockpit"
              element={
                <Suspense
                  fallback={
                    <div className="flex min-h-[50vh] items-center justify-center font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
                      loading…
                    </div>
                  }
                >
                  <Cockpit />
                </Suspense>
              }
            />
            <Route
              path="*"
              element={
                <Suspense
                  fallback={
                    <div className="flex min-h-[50vh] items-center justify-center font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
                      loading…
                    </div>
                  }
                >
                  <Landing />
                </Suspense>
              }
            />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </main>
  );
}
