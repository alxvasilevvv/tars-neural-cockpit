import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Brackets } from "@/components/Brackets";
import { Nav } from "@/components/Nav";
import { Atmosphere } from "@/components/Atmosphere";
import { MagneticCursor } from "@/components/MagneticCursor";
import { Landing } from "@/pages/Landing";
import { Cockpit } from "@/pages/Cockpit";

const variants = {
  hidden: { opacity: 0, y: 24, filter: "blur(8px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -16, filter: "blur(8px)" },
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
            <Route path="/" element={<Landing />} />
            <Route path="/cockpit" element={<Cockpit />} />
            <Route path="*" element={<Landing />} />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </main>
  );
}
