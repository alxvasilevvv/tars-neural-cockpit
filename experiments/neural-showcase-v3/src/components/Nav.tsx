import { motion, useScroll, useSpring } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { SoundToggle } from "@/components/SoundToggle";

const links = [
  { label: "Layers", href: "/#layers" },
  { label: "Domains", href: "/#domains" },
  { label: "How", href: "/#how" },
  { label: "Cockpit", href: "/cockpit" },
];

export function Nav() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 220, damping: 30, mass: 0.6 });
  const loc = useLocation();

  return (
    <>
      {/* Top scroll-progress line */}
      <motion.span
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-px origin-left"
        style={{ scaleX, background: "linear-gradient(90deg, var(--color-accent), var(--color-hud))" }}
      />
      <motion.nav
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-30 flex items-center justify-between px-8 py-5 md:px-14"
      >
        <Link to="/" className="flex items-baseline gap-3">
          <span className="block h-2 w-2 self-center rounded-full bg-accent shadow-[0_0_12px_var(--color-accent-soft)]" />
          <span className="font-display text-[14px] font-bold tracking-tight text-ink">TARS</span>
          <span className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
            / NEURAL COCKPIT
          </span>
        </Link>
        <ul className="flex items-center gap-1">
          {links.map((l) => {
            const active =
              l.href.startsWith("/")
                ? loc.pathname === l.href.split("#")[0] && (l.href.includes("#") ? false : true)
                : false;
            const isExternal = l.href.includes("#") && l.href.startsWith("/#");
            const cls = `inline-block cursor-pointer rounded-md px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] transition-colors duration-200 ${
              active ? "text-accent" : "text-ink-2 hover:bg-line hover:text-ink"
            }`;
            return (
              <li key={l.href}>
                {isExternal ? (
                  <a href={l.href} className={cls}>
                    {l.label}
                  </a>
                ) : (
                  <Link to={l.href} className={cls}>
                    {l.label}
                  </Link>
                )}
              </li>
            );
          })}
          <li>
            <Link
              to="/cockpit"
              className="ml-1 inline-block cursor-pointer rounded-md border border-line-hot bg-accent-deep px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-accent transition-colors duration-200 hover:bg-accent/15"
            >
              Open cockpit
            </Link>
          </li>
          <li>
            <SoundToggle />
          </li>
        </ul>
      </motion.nav>
    </>
  );
}
