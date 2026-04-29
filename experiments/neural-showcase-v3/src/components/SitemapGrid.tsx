import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Home,
  Cpu,
  Download,
  Compass,
  Sparkles,
  Newspaper,
  BookOpen,
  Activity,
  Map,
  GitBranch,
  Code2,
  Shield,
  Lock,
  ScrollText,
  AlertOctagon,
  ArrowUpRight,
} from "lucide-react";

/**
 * <SitemapGrid /> — high-density route map of every page on the
 * marketing surface, grouped into three semantic buckets:
 *
 *   marketing   — hero / acquisition / story
 *   product     — operator-facing tools (cockpit, docs, status)
 *   trust       — legal + transparency surfaces
 *
 * Designed for /docs so an integrator who landed on the API page
 * can quickly see what other doc-shaped surfaces exist (status,
 * changelog, roadmap, security, etc.) without bouncing back to
 * the home page first. Each card is a deep-link with a glyph,
 * path, name, and one-line hint.
 */

interface RouteEntry {
  path: string;
  name: string;
  hint: string;
  Icon: typeof Home;
  external?: boolean;
}

interface RouteGroup {
  num: string;
  name: string;
  intro: string;
  accent: string;
  routes: RouteEntry[];
}

const GROUPS: RouteGroup[] = [
  {
    num: "01",
    name: "Marketing",
    intro: "Acquisition and story surfaces.",
    accent: "var(--brand-indigo)",
    routes: [
      { path: "/",           name: "Home",        hint: "Hero, demos, prompt cycle, full pitch.",          Icon: Home },
      { path: "/install",    name: "Install",     hint: "Per-OS download CTAs, signing notes, hashes.",    Icon: Download },
      { path: "/onboarding", name: "Onboarding",  hint: "First-run walkthrough — what to try first.",      Icon: Compass },
      { path: "/pitch",      name: "Pitch",       hint: "Long-form narrative for investors / partners.",   Icon: Sparkles },
      { path: "/press",      name: "Press",       hint: "Logo kit, screenshots, founder quotes.",          Icon: Newspaper },
      { path: "/build-with", name: "Build with",  hint: "SDK story for devs building on TARS.",            Icon: Code2 },
    ],
  },
  {
    num: "02",
    name: "Product",
    intro: "Operator-facing tools and reference.",
    accent: "var(--brand-cyan)",
    routes: [
      { path: "/cockpit",  name: "Cockpit",  hint: "Live operator surface — domains, runs, traces.",    Icon: Cpu },
      { path: "/docs",     name: "API docs", hint: "HTTP surface reference — daemon + cloud.",          Icon: BookOpen },
      { path: "/status",   name: "Status",   hint: "Realtime health for daemon + meeet.world.",         Icon: Activity },
    ],
  },
  {
    num: "03",
    name: "Trust",
    intro: "Legal, transparency, and historical record.",
    accent: "var(--brand-orchid)",
    routes: [
      { path: "/roadmap",   name: "Roadmap",   hint: "What's shipping next — phases L1…L8+.",          Icon: Map },
      { path: "/changelog", name: "Changelog", hint: "Every release, signed and dated.",                Icon: GitBranch },
      { path: "/security",  name: "Security",  hint: "Threat model, audits, disclosure policy.",        Icon: Shield },
      { path: "/privacy",   name: "Privacy",   hint: "What we do and don't collect.",                   Icon: Lock },
      { path: "/terms",     name: "Terms",     hint: "Service terms, plain-language.",                  Icon: ScrollText },
      { path: "/404",       name: "Not found", hint: "Friendly fallback for unknown routes.",           Icon: AlertOctagon },
    ],
  },
];

export function SitemapGrid() {
  return (
    <section
      aria-labelledby="sitemap-heading"
      className="mb-14 rounded-[14px] border border-line bg-bg-1/60 px-5 py-7 md:px-8 md:py-9"
    >
      <header className="mb-6 grid gap-2">
        <div className="flex items-center gap-3 font-mono-tech text-[10.5px] uppercase tracking-[3px] text-ink-2">
          <span style={{ color: "var(--brand-violet)" }}>—</span>
          <span>sitemap</span>
          <span aria-hidden>·</span>
          <span className="text-ink-3">
            {GROUPS.reduce((n, g) => n + g.routes.length, 0)} routes
          </span>
        </div>
        <h2
          id="sitemap-heading"
          className="font-display text-[22px] leading-[1.18] tracking-[-0.005em] text-ink"
        >
          The whole marketing surface, on one screen.
        </h2>
        <p className="max-w-[60ch] text-[13.5px] leading-[1.6] text-ink-2">
          Every page that lives on this domain — grouped so you can hop
          straight to onboarding, the cockpit, the changelog, or the
          security write-up without round-tripping through home.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-3">
        {GROUPS.map(g => (
          <div key={g.num} className="grid gap-3">
            <div
              className="flex items-baseline gap-2 border-b border-line/60 pb-2 font-mono-tech text-[10px] uppercase tracking-[2.6px]"
              style={{ color: g.accent }}
            >
              <span>{g.num}</span>
              <span className="text-ink">{g.name}</span>
              <span className="ml-auto tabular-nums text-ink-3">
                {g.routes.length}
              </span>
            </div>
            <p className="text-[12px] leading-[1.55] text-ink-3">{g.intro}</p>
            <ul className="grid gap-1.5">
              {g.routes.map(r => (
                <li key={r.path}>
                  <SitemapCard route={r} accent={g.accent} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function SitemapCard({
  route,
  accent,
}: {
  route: RouteEntry;
  accent: string;
}) {
  const { Icon } = route;
  return (
    <motion.div
      whileHover={{ x: 2 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
    >
      <Link
        to={route.path}
        className="group grid grid-cols-[28px_1fr_auto] items-center gap-3 rounded-md border border-line/70 bg-bg-2/30 px-3 py-2.5 transition-colors duration-150 hover:border-line-strong hover:bg-bg-2/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg focus-visible:ring-[color:var(--brand-indigo)]"
      >
        <span
          className="grid h-7 w-7 place-items-center rounded-md border border-line/60 bg-bg-1/60 transition-colors"
          style={{ color: accent }}
          aria-hidden
        >
          <Icon size={13} strokeWidth={1.7} />
        </span>
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-[13px] tracking-[-0.005em] text-ink">
              {route.name}
            </span>
            <code className="truncate font-mono-tech text-[10px] uppercase tracking-[1.6px] text-ink-3">
              {route.path}
            </code>
          </div>
          <span className="block truncate text-[11.5px] leading-[1.5] text-ink-3">
            {route.hint}
          </span>
        </div>
        <ArrowUpRight
          size={12}
          strokeWidth={1.6}
          className="text-ink-3 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          aria-hidden
        />
      </Link>
    </motion.div>
  );
}
