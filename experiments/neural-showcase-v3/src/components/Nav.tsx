import { motion, useScroll, useSpring } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { SoundToggle } from "@/components/SoundToggle";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { WorkspaceSwitcher } from "@/components/workspaces/WorkspaceSwitcher";

// Wave 112 — top-level marketing-only links. The B2B operator pages
// (dashboard / inbox / files / reports / etc.) live in the B2B
// dropdown below to keep this row scannable on narrow viewports.
const links = [
  { label: "Cockpit", href: "/cockpit" },
  { label: "Pricing", href: "/pricing" },
  { label: "Compare", href: "/compare" },
  { label: "FAQ", href: "/faq" },
];

// Wave 112 — B2B operator surfaces grouped behind a single dropdown.
// Order is loosely "what you reach for daily → less often". Workspaces
// + Workshop sit at the end because new orgs visit them once at setup
// and rarely after that.
const b2bLinks: { label: string; href: string }[] = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Inbox", href: "/inbox" },
  { label: "Outreach", href: "/outreach" },
  { label: "Reports", href: "/reports" },
  { label: "Files", href: "/files" },
  { label: "Marketplace", href: "/marketplace" },
  { label: "Bundles", href: "/bundles" },
  { label: "Compliance", href: "/compliance" },
  { label: "Schedules", href: "/schedules" },
  { label: "Workshop", href: "/workshop" },
  { label: "Onboarding", href: "/onboard/org" },
  { label: "Workspaces", href: "/workspaces" },
  { label: "Perf", href: "/admin/perf" },
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

  // Wave 99 — only render the "Set up org" link if the wizard hasn't
  // been completed yet. Read directly from localStorage to avoid an
  // import cycle into the page chunk; cheap one-shot read on render.
  const [orgSetupNeeded, setOrgSetupNeeded] = useState(false);
  useEffect(() => {
    try {
      setOrgSetupNeeded(!window.localStorage.getItem("tars.onboard.org.completed"));
    } catch {
      setOrgSetupNeeded(false);
    }
  }, [loc.pathname]);

  // Wave 110 — workspaces fetched once for the WorkspaceSwitcher.
  // Hidden when only the default "personal" row exists, so no extra
  // visual noise in single-tenant deployments.
  const [workspaces, setWorkspaces] = useState<{ id: string; slug: string; name: string }[]>([]);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const r = await fetch("/api/workspaces");
        if (!r.ok) return;
        const data = await r.json() as { workspaces?: { id: string; slug: string; name: string }[] };
        if (!cancelled && Array.isArray(data.workspaces)) {
          setWorkspaces(data.workspaces.map((w) => ({ id: w.id, slug: w.slug, name: w.name })));
        }
      } catch {
        /* offline / endpoint missing → switcher stays hidden */
      }
    }
    void load();
  }, []);

  // Wave 101 — pending-count badge for the Inbox link. Polls
  // /api/policy/queue?count_only=true every 30s; never throws (404 →
  // 0). This is intentionally a noisy 30s vs the page's 5s loop —
  // the nav badge is decorative, not a precise count.
  const [hilPending, setHilPending] = useState<number>(0);
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const r = await fetch("/api/policy/queue?count_only=true&status=pending", {
          headers: { "content-type": "application/json" },
        });
        if (!r.ok) return;
        const body = await r.json() as { count?: number };
        if (!cancelled) setHilPending(typeof body.count === "number" ? body.count : 0);
      } catch {
        /* offline / endpoint missing → leave count as-is */
      }
    }
    void poll();
    const id = window.setInterval(() => { void poll(); }, 30_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

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
        className="sticky top-0 z-[45] flex items-center justify-between border-b border-line/60 bg-bg-0/80 px-8 py-5 backdrop-blur-md md:px-14"
      >
        <div className="flex items-baseline gap-3">
          <Link to="/" aria-label="TARS — home" className="flex items-baseline gap-3">
            <span className="block h-2 w-2 self-center rounded-full bg-accent shadow-[0_0_12px_var(--color-accent-soft)]" />
            <span className="font-display text-[14px] font-bold tracking-tight text-ink">TARS</span>
            <span className="hidden font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-2 sm:inline">
              / NEURAL COCKPIT
            </span>
          </Link>
          <a
            href="https://meeet.world"
            target="_blank"
            rel="noreferrer noopener"
            aria-label="Released by meeet.world"
            className="hidden items-center gap-1.5 rounded border border-line bg-bg-1/50 px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[2px] text-ink-3 transition-colors hover:border-accent/40 hover:text-accent md:inline-flex"
          >
            <span
              className="h-1 w-1 rounded-full bg-accent"
              style={{ boxShadow: "0 0 4px var(--color-accent)" }}
            />
            by meeet.world
          </a>
        </div>
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
            // Wave 101 — Inbox link gets a pending-count badge from
            // the 30s poll above. Hidden when zero so the nav stays
            // calm in the steady state.
            const showBadge = l.href === "/inbox" && hilPending > 0;
            const inner = (
              <span className="relative inline-flex items-center gap-1.5">
                {l.label}
                {showBadge && (
                  <span
                    aria-label={`${hilPending} pending approval${hilPending === 1 ? "" : "s"}`}
                    className="inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono-tech text-[9px] tracking-normal"
                    style={{ backgroundColor: "var(--brand-indigo, #6366f1)", color: "#fff" }}
                  >
                    {hilPending > 99 ? "99+" : hilPending}
                  </span>
                )}
              </span>
            );
            return (
              <li key={l.href} className="hidden md:inline-flex">
                {isExternal ? (
                  <a href={l.href} className={cls}>
                    {inner}
                  </a>
                ) : (
                  <Link to={l.href} className={cls}>
                    {inner}
                  </Link>
                )}
              </li>
            );
          })}
          {/* Wave 112 — B2B dropdown groups every operator surface
              behind one menu so the public marketing nav stays calm. */}
          <li className="relative hidden md:inline-flex">
            <B2BMenu pathname={loc.pathname} hilPending={hilPending} />
          </li>
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
          {orgSetupNeeded && !insideCockpit && (
            <li className="hidden md:inline-flex">
              <Link
                to="/onboard/org"
                className="ml-1 inline-block cursor-pointer rounded-md border border-line bg-bg-1/50 px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2 transition-colors duration-200 hover:border-accent/40 hover:text-accent"
                title="5-step setup wizard for new fund / company"
              >
                Set up org
              </Link>
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
          <li className="hidden lg:inline-flex">
            <LocaleSwitcher />
          </li>
          {/* Wave 110 — workspace switcher. Hidden when only the
              default "personal" workspace exists; appears once
              another workspace has been created via /workspaces. */}
          <li className="hidden md:inline-flex">
            <WorkspaceSwitcher workspaces={workspaces} />
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

// Wave 112 — B2B operator-surfaces dropdown.
// Click toggles, outside-click + Escape close. Active highlighting
// when the current pathname matches any of the B2B routes.
function B2BMenu({
  pathname,
  hilPending,
}: {
  pathname: string;
  hilPending: number;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Close menu on route change.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const anyActive = b2bLinks.some((l) => pathname === l.href);

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1 rounded-md px-3.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.4px] transition-colors duration-200 ${
          anyActive ? "text-accent" : "text-ink-2 hover:bg-line hover:text-ink"
        }`}
      >
        <span>B2B</span>
        {hilPending > 0 && (
          <span
            aria-label={`${hilPending} pending HIL approvals`}
            className="inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono-tech text-[9px] tracking-normal"
            style={{ backgroundColor: "var(--brand-indigo, #6366f1)", color: "#fff" }}
          >
            {hilPending > 99 ? "99+" : hilPending}
          </span>
        )}
        <ChevronDown
          size={11}
          strokeWidth={1.8}
          aria-hidden
          className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="B2B operator surfaces"
          className="absolute right-0 top-full z-50 mt-1 w-[210px] rounded-md border border-line bg-bg-1/95 p-1.5 shadow-2xl backdrop-blur-md"
        >
          {b2bLinks.map((l) => {
            const isActive = pathname === l.href;
            const showBadge = l.href === "/inbox" && hilPending > 0;
            return (
              <Link
                key={l.href}
                to={l.href}
                role="menuitem"
                className={`flex items-center justify-between gap-2 rounded px-2.5 py-2 font-mono-tech text-[11px] uppercase tracking-[2.2px] transition-colors duration-150 ${
                  isActive
                    ? "bg-line text-accent"
                    : "text-ink-2 hover:bg-line hover:text-ink"
                }`}
              >
                <span>{l.label}</span>
                {showBadge && (
                  <span
                    aria-label={`${hilPending} pending`}
                    className="inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 font-mono-tech text-[9px] tracking-normal"
                    style={{ backgroundColor: "var(--brand-indigo, #6366f1)", color: "#fff" }}
                  >
                    {hilPending > 99 ? "99+" : hilPending}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
