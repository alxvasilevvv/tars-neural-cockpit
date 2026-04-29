import { motion, useScroll, useSpring } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { SoundToggle } from "@/components/SoundToggle";
import { ThemeToggle } from "@/components/ThemeToggle";

const links = [
  { label: "Domains", href: "/#domains" },
  { label: "Pricing", href: "/#pricing" },
  { label: "FAQ", href: "/#faq" },
  { label: "Cockpit", href: "/cockpit" },
];

export function Nav() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 220, damping: 30, mass: 0.6 });
  const loc = useLocation();

  // Detect mac for the keyboard hint label
  const [mac, setMac] = useState(false);
  useEffect(() => {
    if (typeof navigator !== "undefined") {
      setMac(/mac/i.test(navigator.platform) || /mac os/i.test(navigator.userAgent));
    }
  }, []);
  const insideCockpit = loc.pathname.startsWith("/cockpit");

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
        <Link to="/" aria-label="TARS — home" className="flex items-baseline gap-3">
          <span className="block h-2 w-2 self-center rounded-full bg-accent shadow-[0_0_12px_var(--color-accent-soft)]" />
          <span className="font-display text-[14px] font-bold tracking-tight text-ink">TARS</span>
          <span className="hidden font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2 sm:inline">
            / NEURAL COCKPIT
          </span>
        </Link>
        <ul className="flex items-center gap-1">
          {/* Inner anchor links — hidden on small screens; scroll is enough nav. */}
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
              <li key={l.href} className="hidden md:inline-flex">
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
          {/* ⌘K hint — visible on landing-side routes only (cockpit owns its own ⌘K). */}
          {!insideCockpit && (
            <li className="hidden md:inline-flex">
              <button
                type="button"
                onClick={() => {
                  // Synthesise the same hotkey GlobalCommandPalette listens for
                  const evt = new KeyboardEvent("keydown", {
                    key: "k",
                    metaKey: mac,
                    ctrlKey: !mac,
                    bubbles: true,
                  });
                  window.dispatchEvent(evt);
                }}
                aria-label="open command palette"
                title={`Open command palette · ${mac ? "⌘" : "Ctrl"}K`}
                className="ml-1 inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line bg-bg-1/60 px-2.5 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3 backdrop-blur-sm transition-colors duration-200 hover:border-line-strong hover:text-ink"
              >
                <kbd className="font-mono-tech">{mac ? "⌘" : "Ctrl"}</kbd>
                <kbd className="font-mono-tech">K</kbd>
              </button>
            </li>
          )}
          <li>
            <Link
              to="/install"
              className="ml-1 inline-block cursor-pointer rounded-md border border-line-hot bg-accent-deep px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-accent transition-colors duration-200 hover:bg-accent/15"
            >
              Install
            </Link>
          </li>
          <li>
            <ThemeToggle />
          </li>
          <li>
            <SoundToggle />
          </li>
        </ul>
      </motion.nav>
    </>
  );
}
