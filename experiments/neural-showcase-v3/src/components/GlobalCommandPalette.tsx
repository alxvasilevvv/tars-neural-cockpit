import { motion, AnimatePresence } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  Download,
  Sparkles,
  FileText,
  Compass,
  ScanSearch,
  Activity,
  Lock,
  ShieldCheck,
  Newspaper,
  Briefcase,
  Image,
  Stamp,
  FolderOpen,
  Upload,
  Settings2,
  Search,
  Hash,
  FlaskRound,
  CornerDownLeft,
  ArrowDown,
  ArrowUp,
} from "lucide-react";
import { BrandHairline } from "@/components/BrandHairline";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { reset as resetWorkshopTutorials } from "@/lib/tutorial";
import { dispatchRestartTutorial } from "@/components/WorkshopTutorial";

// Docs MD pulled at build time via Vite ?raw — pre-indexed below.
// When adding a new legal/info markdown, register it here so it
// surfaces in the Cmd+K full-text search.
import privacyMd from "@docs/PRIVACY_POLICY.md?raw";
import termsMd from "@docs/TERMS_OF_SERVICE.md?raw";
import securityMd from "@docs/SECURITY.md?raw";
import faqMd from "@docs/FAQ.md?raw";

/**
 * GlobalCommandPalette — Cmd/Ctrl+K from any landing-side route.
 *
 * Different from the cockpit's `<CommandPalette />` (which searches
 * threads / messages / traces). This one is a navigation palette:
 * jump between marketing routes, deep-link to legal docs, copy the
 * install command, fuzzy match by title or tag.
 *
 * Distinct from cockpit palette:
 *   - cockpit one is mounted only on /cockpit, hits /api/search
 *   - this one is mounted globally, no backend, navigates routes
 *
 * Both use ⌘K. We mount this only OUTSIDE /cockpit so they don't
 * collide.
 */

type CmdKind = "route" | "anchor" | "copy" | "external" | "action";

interface CmdItem {
  id: string;
  kind: CmdKind;
  title: string;
  hint: string;
  Icon: typeof Home;
  /** for kind=route or kind=anchor (anchor uses /#section) */
  href?: string;
  /** for kind=copy */
  payload?: string;
  /** for kind=action — fire-and-forget callback (Wave 92). */
  run?: () => void;
  /** group label */
  group: "Pages" | "Sections" | "Actions" | "External" | "Docs";
  /** keywords for fuzzy match */
  keywords?: string;
}

const ITEMS: CmdItem[] = [
  // Pages
  { id: "home",      kind: "route", title: "Home",            hint: "Hero, packs, pricing, FAQ", Icon: Home,        href: "/",           group: "Pages" },
  { id: "install",   kind: "route", title: "Install",         hint: "One-curl setup",            Icon: Download,    href: "/install",    group: "Pages" },
  { id: "onboard",   kind: "route", title: "Onboarding",      hint: "Sign in → role → first brief", Icon: Sparkles, href: "/onboarding", group: "Pages" },
  { id: "cockpit",   kind: "route", title: "Cockpit",         hint: "Live operator console",     Icon: Compass,     href: "/cockpit",    group: "Pages", keywords: "console daemon" },
  { id: "pitch",     kind: "route", title: "Pitch deck",      hint: "12-slide product overview", Icon: FileText,    href: "/pitch",      group: "Pages", keywords: "deck investor presentation" },
  { id: "press",     kind: "route", title: "Press kit",       hint: "Brand, palette, contact",   Icon: Newspaper,   href: "/press",      group: "Pages", keywords: "media journalist boilerplate" },
  { id: "docs",      kind: "route", title: "API reference",   hint: "Public HTTP surface",       Icon: ScanSearch,  href: "/docs",       group: "Pages", keywords: "endpoints contract" },
  { id: "status",    kind: "route", title: "Status",          hint: "Live system pulses",        Icon: Activity,    href: "/status",     group: "Pages", keywords: "uptime health" },
  { id: "privacy",   kind: "route", title: "Privacy Policy",  hint: "What we don't collect",     Icon: Lock,        href: "/privacy",    group: "Pages", keywords: "gdpr ccpa data" },
  { id: "terms",     kind: "route", title: "Terms of Service",hint: "License + obligations",     Icon: Briefcase,   href: "/terms",      group: "Pages", keywords: "tos legal" },
  { id: "security",  kind: "route", title: "Security model",  hint: "Threat model + crypto",     Icon: ShieldCheck, href: "/security",   group: "Pages", keywords: "crypto sandbox audit" },
  { id: "roadmap",   kind: "route", title: "Roadmap",          hint: "Phase M product plan",       Icon: FileText,    href: "/roadmap",    group: "Pages", keywords: "future plan" },
  { id: "changelog", kind: "route", title: "Changelog",        hint: "What shipped, top-down",     Icon: FileText,    href: "/changelog",  group: "Pages", keywords: "history release" },
  { id: "buildwith", kind: "route", title: "Built with TARS",  hint: "Embed badge for your repo / site", Icon: Stamp,    href: "/build-with", group: "Pages", keywords: "badge embed widget viral share" },
  { id: "settings",  kind: "route", title: "Settings",          hint: "Updates · keyboard · about",         Icon: Settings2, href: "/settings",   group: "Pages", keywords: "preferences updater shortcuts version about" },
  // Wave 84 — Workshop ROI calculator entry. Surfaces during the
  // structured onboarding workshop so fund partners can compute live
  // savings via Cmd+K instead of hunting for the URL.
  { id: "workshop-roi", kind: "route", title: "Calculate workshop ROI", hint: "Live time + dollar saving estimator", Icon: FlaskRound, href: "/workshop/roi", group: "Pages", keywords: "workshop roi calculator savings hours dollars business pricing tarsbusiness fund" },
  // Wave 85 — Workshop materials hub. Decks, recipes, videos,
  // community. Top-of-bookmark-bar for cohort attendees.
  { id: "workshop-materials", kind: "route", title: "Workshop materials", hint: "Decks · recipes · videos · community", Icon: FlaskRound, href: "/workshop/materials", group: "Pages", keywords: "workshop materials decks slides handouts pdf videos loom recipe library playbook slack office hours enterprise cohort" },
  // Wave 88 — Pre-workshop self-assessment quiz. Sits next to the
  // materials hub so attendees take it before they binge the decks.
  { id: "workshop-assess", kind: "route", title: "Workshop self-assessment", hint: "12-question pre-flight quiz", Icon: FlaskRound, href: "/workshop/assess", group: "Pages", keywords: "workshop assess assessment quiz pre-flight pre-work llm python trading audit likert score self evaluation cohort" },
  // Wave 89 — Facilitator cohort dashboard. Internal surface — only
  // workshop runners need it, but Cmd+K is the fastest path. Keep it
  // out of the public Nav.
  { id: "workshop-cohort", kind: "route", title: "Cohort dashboard", hint: "Live facilitator view of every attendee", Icon: FlaskRound, href: "/workshop/cohort", group: "Pages", keywords: "workshop cohort dashboard facilitator attendees live activity broadcast risk alerts intake design test deploy" },
  // Wave 96 - Reporting dashboard. Personal /dashboard with 10
  // configurable widgets pulling from every TARS surface.
  { id: "dashboard", kind: "route", title: "Dashboard", hint: "Your day at a glance - calendar, mentions, PRs, receipts", Icon: Compass, href: "/dashboard", group: "Pages", keywords: "dashboard widgets calendar slack gmail github pr wallet receipts backtest cohort hil playbook home overview report personal workspace" },
  // Wave 98 - Outreach (LP updates, founder DD, intros, follow-ups,
  // welcome touches). Drafted in the operator's voice via AI Clone +
  // Gmail send is HIL-gated.
  { id: "outreach", kind: "route", title: "Outreach", hint: "Draft + send LP updates, intros, follow-ups in your voice", Icon: Compass, href: "/outreach", group: "Pages", keywords: "outreach email gmail draft send lp update founder dd intro follow up welcome ai clone hil approve send batch campaign" },
  // Wave 99 - Org onboarding wizard. Top-of-list for any new fund or
  // company that just downloaded TARS.
  { id: "onboard-org", kind: "route", title: "Set up your organization", hint: "5-step wizard for new fund / company", Icon: Sparkles, href: "/onboard/org", group: "Pages", keywords: "onboard onboarding org organization fund company setup wizard new install first run team invites playbooks step 1 2 3 4 5" },
  // Wave 101 - Unified HIL approval inbox. Single resolve-all surface
  // for wallet sigs, outreach sends, code edits, paper→live promotions,
  // deletions — anything that fired policy_gate.require_confirm().
  { id: "inbox", kind: "route", title: "Inbox / approvals", hint: "Resolve every pending HIL confirmation", Icon: Stamp, href: "/inbox", group: "Pages", keywords: "inbox hil approve approval queue policy gate confirm deny pending wallet outreach code live trading bulk staged action token" },
  // Wave 102 — file browser. Single surface for every PDF / deck /
  // contract ingested by the attachment pipeline. "Files browser"
  // matches the spec keyword.
  { id: "files",  kind: "route", title: "Files browser", hint: "All PDFs, decks, contracts in one place", Icon: FolderOpen, href: "/files", group: "Pages", keywords: "files browser document attachments pdf deck contract report upload tag category bulk" },
  { id: "files-upload", kind: "action", title: "Upload file", hint: "Open /files with the upload picker focused", Icon: Upload, group: "Actions", keywords: "upload file document attach drag drop import multipart bulk", run: () => { try { window.location.assign("/files?upload=1"); } catch { /* noop */ } } },
  { id: "files-search", kind: "action", title: "Search files", hint: "Full-text search over every ingested attachment", Icon: FolderOpen, group: "Actions", keywords: "search files documents attachments fts5 query find", run: () => { try { window.location.assign("/files?focus=search"); } catch { /* noop */ } } },
  // Wave 103 - Reports surface (LP updates, board packs, KPIs, audit packs).
  { id: "reports", kind: "route", title: "Reports", hint: "Generate PDF / PPTX / XLSX from templates + your data", Icon: Compass, href: "/reports", group: "Pages", keywords: "reports report pdf pptx xlsx docx lp update board pack kpi dashboard portfolio audit deal screen incident postmortem template render generate export" },
  { id: "reports-new", kind: "action", title: "Generate report", hint: "Open /reports with the templates tab focused", Icon: Sparkles, group: "Actions", keywords: "report generate render export pdf pptx xlsx docx new", run: () => { try { window.location.assign("/reports"); } catch { /* noop */ } } },
  { id: "reports-runs", kind: "action", title: "View report runs", hint: "Open /reports runs tab", Icon: Compass, group: "Actions", keywords: "reports runs history download recent generated", run: () => { try { window.location.assign("/reports?tab=runs"); } catch { /* noop */ } } },

  // Sections (anchor on /)
  { id: "domains",   kind: "anchor", title: "Domain packs",    hint: "Traders / Entrepreneur / Researcher / Science", Icon: Hash, href: "/#domains", group: "Sections" },
  { id: "pricing",   kind: "route", title: "Pricing",         hint: "Free / Pro / Business / Lifetime",              Icon: Hash, href: "/pricing", group: "Sections", keywords: "tier subscription cost" },
  { id: "faq",       kind: "route", title: "FAQ",             hint: "Real questions",                                Icon: Hash, href: "/faq",     group: "Sections" },
  { id: "waitlist",  kind: "anchor", title: "Waitlist",        hint: "Be first when the binary drops",                Icon: Hash, href: "/#waitlist", group: "Sections", keywords: "email signup notify launch" },
  { id: "compare",   kind: "route", title: "vs Cursor / Claude Desktop", hint: "Feature matrix",                     Icon: Hash, href: "/compare", group: "Sections", keywords: "comparison difference" },
  { id: "council",   kind: "anchor", title: "Council demo",    hint: "Two-voice deliberation",                        Icon: Hash, href: "/#council", group: "Sections" },

  // Actions
  { id: "copy-install",     kind: "copy",   title: "Copy install command", hint: "Download signed DMG via curl (macOS)", Icon: Download, payload: "curl -fLO https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg && open TARS_8.4.0_aarch64.dmg", group: "Actions" },
  // Wave 96 - Dashboard add/reset shortcuts. Both run inline; the
  // Dashboard page reacts via the localStorage key (next render
  // re-reads the layout).
  { id: "dashboard-add",   kind: "action", title: "Dashboard: add widget", hint: "Open the widget palette on /dashboard", Icon: Sparkles, group: "Actions", keywords: "dashboard add widget palette", run: () => { try { window.location.assign("/dashboard?add=1"); } catch { /* noop */ } } },
  // Wave 98 - Quick draft action. Lands on /outreach where the
  // operator picks a template + recipient.
  { id: "outreach-new", kind: "action", title: "New email draft", hint: "Open /outreach to draft an LP update, intro, or follow-up", Icon: Sparkles, group: "Actions", keywords: "outreach new email draft compose lp update intro follow up gmail send", run: () => { try { window.location.assign("/outreach"); } catch { /* noop */ } } },
  { id: "dashboard-reset", kind: "action", title: "Dashboard: reset layout", hint: "Restore the generic default widget set", Icon: Settings2, group: "Actions", keywords: "dashboard reset clear layout default", run: () => { try { localStorage.removeItem("tars.dashboard.layout"); window.location.assign("/dashboard"); } catch { /* noop */ } } },
  // Wave 92 — Restart any first-run workshop tutorial overlay. Wipes
  // the localStorage flag for /workshop, /workshop/cohort, and
  // /workshop/enterprise, then dispatches the imperative restart event
  // so an already-mounted tour pops back open immediately.
  { id: "restart-workshop-tutorial", kind: "action", title: "Restart workshop tutorial", hint: "Replay the first-run walkthrough on every workshop page", Icon: FlaskRound, group: "Actions", keywords: "workshop tutorial restart reset tour overlay walkthrough onboarding help replay", run: () => { resetWorkshopTutorials(); dispatchRestartTutorial(); } },
  // Wave 101 - Bulk approve from /inbox via Cmd+K. Lands on /inbox?bulk=1
  // which the page reads on mount (the dialog opens after the initial
  // queue fetch completes). Operator still has to double-confirm in the
  // dialog so this never auto-fires.
  { id: "inbox-bulk-approve", kind: "action", title: "Bulk approve all pending", hint: "Open /inbox with the bulk approve dialog ready", Icon: Stamp, group: "Actions", keywords: "inbox hil approve approval bulk queue all pending resolve clear", run: () => { try { window.location.assign("/inbox?bulk=1"); } catch { /* noop */ } } },
  { id: "inbox-pending-count", kind: "action", title: "Show pending HIL count", hint: "Refresh nav badge with current pending approvals", Icon: Stamp, group: "Actions", keywords: "inbox hil pending count badge refresh", run: () => { try { window.location.assign("/inbox"); } catch { /* noop */ } } },

  // External
  { id: "github",    kind: "external", title: "GitHub repo",      hint: "meeet-world/tars",        Icon: Image, href: "https://github.com/meeet-world/tars",        group: "External" },
  { id: "discord",   kind: "external", title: "Discord",          hint: "Community + support",     Icon: Image, href: "https://discord.gg/meeet",                  group: "External" },
  { id: "twitter",   kind: "external", title: "Twitter / X",      hint: "@meeet_world",            Icon: Image, href: "https://x.com/meeet_world",                 group: "External" },

  // Docs — full-text addressable from Cmd+K. Indexed at build time
  // via Vite ?raw imports; one item per `## heading` so the operator
  // jumps to the section, not the top of the document.
  ...indexDoc("Privacy Policy",     "/privacy",  privacyMd,  "privacy gdpr ccpa data cookie sub-processor"),
  ...indexDoc("Terms of Service",   "/terms",    termsMd,    "tos legal license arbitration"),
  ...indexDoc("Security model",     "/security", securityMd, "stride threat crypto envelope recovery"),
  ...indexDoc("FAQ",                "/faq",     faqMd,      "questions help support"),
];

/**
 * indexDoc — slice a markdown body into one CmdItem per `## heading`.
 * Each entry keeps the heading as the title and a short anchor-style
 * id so the route deep-links work today (`/privacy#cookies`) when
 * MarkdownView starts emitting heading anchors. For now the href just
 * navigates to the page — refining is a one-line change later.
 */
function indexDoc(
  pageTitle: string,
  href: string,
  source: string,
  keywords: string,
): CmdItem[] {
  const items: CmdItem[] = [];
  const lines = source.split(/\r?\n/);
  const seen = new Set<string>();
  for (const line of lines) {
    const m = /^##\s+(.+?)\s*$/.exec(line);
    if (!m) continue;
    const heading = m[1].replace(/[`*_]/g, "").trim();
    if (!heading || seen.has(heading)) continue;
    seen.add(heading);
    const slug = heading
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    items.push({
      id: `doc-${slugify(pageTitle)}-${slug}`,
      kind: "route",
      title: heading,
      hint: `${pageTitle} · §`,
      Icon: FileText,
      href: `${href}#${slug}`,
      group: "Docs",
      keywords: `${pageTitle.toLowerCase()} ${keywords} ${heading.toLowerCase()}`,
    });
    if (items.length > 20) break; // cap per-doc to keep palette snappy
  }
  return items;
}

function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

const RECENT_KEY = "tars-cmdk-recent";
const MAX_RECENT = 4;

function loadRecent(): string[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter(s => typeof s === "string").slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

function saveRecent(id: string) {
  if (typeof localStorage === "undefined") return;
  const cur = loadRecent().filter(x => x !== id);
  const next = [id, ...cur].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* private mode */
  }
}

/** Lightweight fuzzy score — matches each query char in order. */
function fuzzyScore(item: CmdItem, q: string): number {
  if (!q) return 0;
  const haystack = (item.title + " " + item.hint + " " + (item.keywords ?? "") + " " + item.group).toLowerCase();
  const needle = q.toLowerCase();
  let i = 0;
  let last = -1;
  let score = 0;
  for (const ch of needle) {
    const idx = haystack.indexOf(ch, last + 1);
    if (idx === -1) return 0;
    score += idx === last + 1 ? 3 : 1; // contiguous bonus
    last = idx;
    i++;
  }
  // Title prefix bonus
  if (item.title.toLowerCase().startsWith(needle)) score += 30;
  if (haystack.includes(" " + needle)) score += 6;
  return score;
}

export function GlobalCommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [recentIds, setRecentIds] = useState<string[]>(() => loadRecent());
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const loc = useLocation();
  const navigate = useNavigate();
  useFocusTrap(dialogRef, open);

  // Don't mount inside /cockpit — that surface owns its own ⌘K.
  const insideCockpit = loc.pathname.startsWith("/cockpit");

  // Global hotkey
  useEffect(() => {
    if (insideCockpit) return;
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen(prev => !prev);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [insideCockpit, open]);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setQuery("");
      setActiveIdx(0);
      return;
    }
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open]);

  // Filter + score + group
  const groups = useMemo(() => {
    let pool: CmdItem[];
    if (query.trim()) {
      pool = ITEMS
        .map(it => ({ it, score: fuzzyScore(it, query.trim()) }))
        .filter(({ score }) => score > 0)
        .sort((a, b) => b.score - a.score)
        .map(({ it }) => it);
    } else {
      // No query: surface recent first, then default order
      const recents = recentIds
        .map(id => ITEMS.find(i => i.id === id))
        .filter((x): x is CmdItem => Boolean(x));
      const seen = new Set(recents.map(r => r.id));
      pool = [...recents, ...ITEMS.filter(i => !seen.has(i.id))];
    }

    // Group while preserving order
    const out: { name: string; items: CmdItem[] }[] = [];
    const recentBlock: CmdItem[] = !query.trim() && recentIds.length
      ? pool.slice(0, recentIds.length).filter(i => recentIds.includes(i.id))
      : [];
    if (recentBlock.length) {
      out.push({ name: "Recent", items: recentBlock });
    }
    const remaining = pool.slice(recentBlock.length);
    const byGroup = new Map<string, CmdItem[]>();
    for (const it of remaining) {
      if (!byGroup.has(it.group)) byGroup.set(it.group, []);
      byGroup.get(it.group)!.push(it);
    }
    for (const [name, items] of byGroup) {
      out.push({ name, items });
    }
    return out;
  }, [query, recentIds]);

  const flat = useMemo(() => groups.flatMap(g => g.items), [groups]);

  // Keep activeIdx in bounds
  useEffect(() => {
    if (activeIdx >= flat.length) setActiveIdx(0);
  }, [flat.length, activeIdx]);

  const close = useCallback(() => setOpen(false), []);

  const choose = useCallback(
    (item: CmdItem) => {
      saveRecent(item.id);
      setRecentIds(loadRecent());
      if (item.kind === "copy" && item.payload) {
        navigator.clipboard?.writeText(item.payload);
        // visual confirm — keep palette open briefly
        setQuery("✓ copied");
        setTimeout(() => {
          setQuery("");
          setOpen(false);
        }, 600);
        return;
      }
      if (item.kind === "action" && item.run) {
        // Wave 92 — fire-and-forget callback (e.g. restart tutorial).
        try {
          item.run();
        } catch {
          /* swallow — keep palette UX snappy */
        }
        setQuery("✓ done");
        setTimeout(() => {
          setQuery("");
          setOpen(false);
        }, 600);
        return;
      }
      if (item.kind === "external" && item.href) {
        window.open(item.href, "_blank", "noopener,noreferrer");
        close();
        return;
      }
      if (item.href) {
        navigate(item.href);
      }
      close();
    },
    [close, navigate],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx(i => Math.min(flat.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx(i => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      const it = flat[activeIdx];
      if (it) {
        e.preventDefault();
        choose(it);
      }
    }
  };

  if (insideCockpit) return null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-label="navigation palette"
          tabIndex={-1}
          onKeyDown={onKeyDown}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(2,4,12,0.72)] px-4 pt-[12vh] backdrop-blur-md"
          onClick={close}
        >
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            onClick={e => e.stopPropagation()}
            initial={{ opacity: 0, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.99 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-xl overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65)] focus:outline-none"
          >
            <BrandHairline variant="static" />

            <header className="flex items-center gap-2 border-b border-line/60 px-4 py-3">
              <Search size={14} strokeWidth={1.6} className="text-ink-3 shrink-0" aria-hidden />
              <input
                ref={inputRef}
                value={query}
                onChange={e => {
                  setQuery(e.target.value);
                  setActiveIdx(0);
                }}
                placeholder="jump to a page · search by name or tag"
                aria-label="navigation query"
                className="flex-1 bg-transparent font-display text-[14px] tracking-[-0.005em] text-ink outline-none placeholder:text-ink-3"
              />
              <button
                type="button"
                onClick={close}
                className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3 hover:text-alert"
                aria-label="close"
              >
                esc
              </button>
            </header>

            <div className="max-h-[55vh] overflow-y-auto">
              {flat.length === 0 ? (
                <p className="px-4 py-8 text-center font-mono-tech text-[10.5px] uppercase tracking-[2.2px] text-ink-3">
                  no match — try a different word
                </p>
              ) : (
                groups.map(g => (
                  <section key={g.name}>
                    <div className="px-4 pt-3 pb-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                      {g.name}
                    </div>
                    <ul role="listbox">
                      {g.items.map(it => {
                        const Icon = it.Icon;
                        const flatIdx = flat.indexOf(it);
                        const active = flatIdx === activeIdx;
                        return (
                          <li key={it.id}>
                            <button
                              type="button"
                              onClick={() => choose(it)}
                              onMouseEnter={() => setActiveIdx(flatIdx)}
                              className={`flex w-full items-center gap-3 border-l-2 px-4 py-2.5 text-left transition-colors ${
                                active
                                  ? "border-accent bg-accent/[0.06]"
                                  : "border-transparent hover:bg-bg-2"
                              }`}
                            >
                              <span
                                className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-accent"
                                style={{
                                  background: active
                                    ? "color-mix(in srgb, var(--color-accent) 18%, transparent)"
                                    : "var(--color-bg-2)",
                                }}
                              >
                                <Icon size={13} strokeWidth={1.7} />
                              </span>
                              <span className="flex-1 min-w-0">
                                <span className="block truncate font-display text-[13.5px] text-ink">
                                  {it.title}
                                </span>
                                <span className="block truncate font-mono-tech text-[10px] uppercase tracking-[1.8px] text-ink-3">
                                  {it.hint}
                                </span>
                              </span>
                              <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
                                {it.kind === "copy" ? "copy" : it.kind === "external" ? "↗" : it.kind === "action" ? "run" : "→"}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))
              )}
            </div>

            <footer className="flex items-center justify-between border-t border-line/40 px-4 py-2 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              <span className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1">
                  <ArrowUp size={10} strokeWidth={2} /><ArrowDown size={10} strokeWidth={2} /> nav
                </span>
                <span className="inline-flex items-center gap-1">
                  <CornerDownLeft size={10} strokeWidth={2} /> open
                </span>
                <span>esc · close</span>
              </span>
              <span className="flex items-center gap-3">
                <span className="hidden items-center gap-1 sm:inline-flex">
                  <kbd className="inline-block min-w-[14px] rounded-[4px] border border-line bg-bg-2/80 px-1 text-center text-[9px] tracking-[1px] text-ink-2">?</kbd>
                  <span>keys</span>
                </span>
                <span>{flat.length} {flat.length === 1 ? "item" : "items"}</span>
              </span>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
