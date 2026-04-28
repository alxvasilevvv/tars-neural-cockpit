import { motion } from "framer-motion";

const links = [
  { label: "Layers", href: "#layers" },
  { label: "Domains", href: "#domains" },
  { label: "How", href: "#how" },
];

export function Nav() {
  return (
    <motion.nav
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="relative z-30 flex items-center justify-between px-8 py-5 md:px-14"
    >
      <a href="#" className="flex items-baseline gap-3">
        <span className="block h-2 w-2 self-center rounded-full bg-accent shadow-[0_0_12px_var(--color-accent-soft)]" />
        <span className="font-display text-[14px] font-bold tracking-tight text-ink">
          TARS
        </span>
        <span className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2">
          / NEURAL COCKPIT
        </span>
      </a>
      <ul className="flex items-center gap-1">
        {links.map((l) => (
          <li key={l.href}>
            <a
              href={l.href}
              className="inline-block cursor-pointer rounded-lg px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:bg-line hover:text-ink"
            >
              {l.label}
            </a>
          </li>
        ))}
        <li>
          <a
            href="#cockpit"
            className="ml-1 inline-block cursor-pointer rounded-lg border border-line-hot px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-accent transition-colors duration-200 hover:bg-accent-deep"
          >
            Open cockpit
          </a>
        </li>
      </ul>
    </motion.nav>
  );
}
