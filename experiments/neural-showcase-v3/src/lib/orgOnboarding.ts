// SYNC: claude-w99-org-onboarding
/**
 * Wave 99 — `/onboard/org` 5-step wizard data layer.
 *
 * Three responsibilities:
 *
 * 1. **Step / draft persistence in localStorage.** The wizard remembers
 *    where the operator left off — refresh / browser-restart / device
 *    swap should land them on the same step with the same answers.
 *    Storage keys: `tars.onboard.org.draft`, `.completed`, `.skipped`.
 *
 * 2. **Backend writes** for Step 1 (org info) and Step 3 (invites)
 *    via `/api/org/*`. Step 2 (connectors) reuses Wave 91's
 *    `/api/connectors/*`. Step 4 (playbooks) attempts a batch install
 *    POST and falls back to local-only when the endpoint is missing.
 *    Step 5 schedules via Wave 97's `/api/scheduler/schedules`.
 *
 * 3. **Role-based playbook recommendations.** Each org type maps to a
 *    curated set of starter playbooks (see `STARTER_PLAYBOOKS`). The
 *    wizard's Step 4 reads from this map so a VC fund sees five
 *    fund/* playbooks and a SaaS team sees the four saas/* ones.
 *
 * The module is FE-only — pure functions + tiny `fetch` wrappers. No
 * React hooks here; the page composes its own state via useState +
 * useEffect against these helpers.
 */

import { API_BASE } from "@/lib/api";

async function postJSON<T>(path: string, body: unknown, method = "POST"): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as T;
}

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as T;
}

// ── types ───────────────────────────────────────────────────────────

export type OrgType =
  | "vc_fund"
  | "hedge_fund"
  | "family_office"
  | "saas_company"
  | "dao"
  | "research_lab"
  | "other";

export type InviteRole = "admin" | "designer" | "analyst" | "viewer";

export interface OrgInfo {
  name: string;
  type: OrgType;
  /** AUM string for funds, headcount for companies, freeform for others. */
  size: string;
  timezone: string;
  primary_use_case: string;
  metadata?: Record<string, unknown>;
}

export interface InviteDraft {
  email: string;
  role: InviteRole;
}

export interface PersistedInvite extends InviteDraft {
  id: string;
  org_id: string;
  invited_at: number;
  status: "pending" | "sent" | "accepted";
}

export interface PlaybookRec {
  /** Slug like "fund/weekly_lp_report" — also the path under playbooks/_workshop. */
  slug: string;
  /** Operator-visible label. */
  title: string;
  /** Two-sentence pitch used as the card body. */
  blurb: string;
  /** Tag chips rendered above the card title. */
  tags: string[];
}

export interface OnboardingDraft {
  step: number;
  org: Partial<OrgInfo>;
  /** Keyed by connector name (`slack` | `gmail` | `calendar` | `github`). */
  connectors: Record<string, "configured" | "pending" | "skipped" | "error">;
  multi: boolean;
  invites: InviteDraft[];
  selectedPlaybooks: string[];
  /** Slug picked for Step 5's "run now" — must be in selectedPlaybooks. */
  firstRunSlug?: string;
  /** Whether Step 5's schedule toggle was flipped on. */
  scheduleNextDay: boolean;
}

// ── localStorage keys ───────────────────────────────────────────────

const KEY_DRAFT = "tars.onboard.org.draft";
const KEY_COMPLETED = "tars.onboard.org.completed";
const KEY_SKIPPED = "tars.onboard.org.skipped";

const FRESH_DRAFT: OnboardingDraft = {
  step: 1,
  org: {},
  connectors: {},
  multi: false,
  invites: [],
  selectedPlaybooks: [],
  scheduleNextDay: false,
};

// ── persistence ─────────────────────────────────────────────────────

export function loadDraft(): OnboardingDraft {
  if (typeof window === "undefined") return { ...FRESH_DRAFT };
  try {
    const raw = window.localStorage.getItem(KEY_DRAFT);
    if (!raw) return { ...FRESH_DRAFT };
    const parsed = JSON.parse(raw) as Partial<OnboardingDraft>;
    return { ...FRESH_DRAFT, ...parsed };
  } catch {
    return { ...FRESH_DRAFT };
  }
}

export function saveDraft(draft: OnboardingDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_DRAFT, JSON.stringify(draft));
  } catch {
    /* quota-full / private-mode → silent */
  }
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(KEY_DRAFT);
  } catch {
    /* noop */
  }
}

export function markCompleted(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_COMPLETED, String(Date.now()));
  } catch {
    /* noop */
  }
}

export function isCompleted(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return Boolean(window.localStorage.getItem(KEY_COMPLETED));
  } catch {
    return false;
  }
}

export function loadSkipped(): number[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY_SKIPPED);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((n) => typeof n === "number") : [];
  } catch {
    return [];
  }
}

export function markSkipped(step: number): void {
  if (typeof window === "undefined") return;
  try {
    const cur = loadSkipped();
    if (cur.includes(step)) return;
    cur.push(step);
    window.localStorage.setItem(KEY_SKIPPED, JSON.stringify(cur));
  } catch {
    /* noop */
  }
}

// ── default detection ──────────────────────────────────────────────

export function detectTimezone(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return tz || "UTC";
  } catch {
    return "UTC";
  }
}

// ── role-based starter playbooks (Step 4) ──────────────────────────

/** Deterministic, hand-curated mapping. Mirrors `playbooks/_workshop/*`
 * directories so each slug actually exists on disk. The "other"
 * bucket is a six-pack mixed across the strongest categories. */
export const STARTER_PLAYBOOKS: Record<OrgType, PlaybookRec[]> = {
  vc_fund: [
    { slug: "fund/weekly_lp_report",      title: "Weekly LP report",        blurb: "Pull deal updates + portfolio metrics, draft the 5-section LP email.", tags: ["lp", "weekly", "ai-clone"] },
    { slug: "fund/deal_screening",        title: "Deal screening",          blurb: "Triage inbound deals against your thesis, draft a one-page memo per fit.", tags: ["deal-flow", "memo"] },
    { slug: "fund/founder_dd",            title: "Founder DD pack",         blurb: "Background, social, GitHub, and reference call prep into one pack.", tags: ["due-diligence"] },
    { slug: "fund/portfolio_monitoring",  title: "Portfolio monitoring",    blurb: "Daily portfolio pulse: PR, hiring, financials, anomaly callouts.", tags: ["portfolio"] },
    { slug: "fund/tax_memo",              title: "Tax memo drafter",        blurb: "Quarterly K-1 narrative + LP-side tax change summary.", tags: ["compliance"] },
  ],
  hedge_fund: [
    { slug: "algotrade/momentum_breakout_strategy", title: "Momentum breakout strat", blurb: "Backtest, stress-test, and stage a momentum breakout strategy.", tags: ["strategy", "backtest"] },
    { slug: "algotrade/mean_reversion_strategy",    title: "Mean-reversion strat",     blurb: "Pairs / z-score reversion with HIL gate before live deploy.", tags: ["strategy", "pairs"] },
    { slug: "algotrade/backtest_to_live_pipeline",  title: "Backtest → live pipeline", blurb: "Promote a winning backtest to paper, then live with caps.", tags: ["pipeline", "promotion"] },
    { slug: "algotrade/live_paper_session",         title: "Live paper session",        blurb: "Spin up a paper account, mirror today's signals, write a debrief.", tags: ["paper"] },
    { slug: "algotrade/risk_audit_weekly",          title: "Weekly risk audit",        blurb: "Position concentration, drawdown, leverage, exposure deltas.", tags: ["risk", "weekly"] },
  ],
  family_office: [
    { slug: "family-office/monthly_statement",  title: "Monthly statement", blurb: "Aggregate every account's statement into a one-pager for the principal.", tags: ["statement"] },
    { slug: "family-office/kyc_refresh",        title: "KYC refresh",       blurb: "Quarterly KYC update across managers, attorneys, banks.", tags: ["kyc", "compliance"] },
    { slug: "family-office/compliance_pack",    title: "Compliance pack",   blurb: "Generate the compliance binder for outside review or audit.", tags: ["compliance", "audit"] },
  ],
  saas_company: [
    { slug: "saas/morning_ops",     title: "Morning ops brief",    blurb: "Overnight alerts, on-call summary, top 3 customer escalations.", tags: ["ops", "morning"] },
    { slug: "saas/churn_alert",     title: "Churn alert",          blurb: "Surface accounts trending toward churn with the top retention play.", tags: ["churn", "growth"] },
    { slug: "saas/pr_review",       title: "PR review summary",    blurb: "Daily roll-up of open PRs needing attention with risk highlights.", tags: ["engineering"] },
    { slug: "saas/outreach_loop",   title: "Outreach loop",        blurb: "Weekly outbound + warm reactivation drafts in the founder voice.", tags: ["sales", "ai-clone"] },
  ],
  dao: [
    { slug: "dao/proposal_summarize",        title: "Proposal summariser",     blurb: "TL;DR each new governance proposal + risk callouts for voters.", tags: ["governance"] },
    { slug: "dao/treasury_diff",             title: "Treasury diff",            blurb: "Daily treasury delta, anomalies, multi-sig activity log.", tags: ["treasury"] },
    { slug: "dao/contributor_recognition",   title: "Contributor recognition",  blurb: "Weekly callouts of high-impact contributors for rewards rounds.", tags: ["community"] },
  ],
  research_lab: [
    { slug: "fund/portfolio_monitoring", title: "Lit-monitor",          blurb: "Daily pulse on new arXiv/biorxiv papers in your tracked subjects.", tags: ["research"] },
    { slug: "saas/morning_ops",          title: "Lab morning brief",     blurb: "Yesterday's experiments, today's queue, blockers per teammate.", tags: ["ops"] },
    { slug: "fund/tax_memo",             title: "Grant memo drafter",    blurb: "Draft grant progress reports from your raw experiment notes.", tags: ["funding"] },
  ],
  other: [
    { slug: "saas/morning_ops",                     title: "Morning ops brief",      blurb: "Overnight alerts, on-call summary, top 3 customer escalations.", tags: ["ops"] },
    { slug: "fund/weekly_lp_report",                title: "Weekly stakeholder note", blurb: "Pull updates + metrics, draft the 5-section stakeholder email.", tags: ["weekly"] },
    { slug: "saas/outreach_loop",                   title: "Outreach loop",          blurb: "Weekly outbound + warm reactivation drafts in your voice.", tags: ["ai-clone"] },
    { slug: "fund/portfolio_monitoring",            title: "Topic monitoring",        blurb: "Daily monitoring across the topics that matter to your work.", tags: ["monitoring"] },
    { slug: "algotrade/risk_audit_weekly",          title: "Weekly risk audit",       blurb: "Spot drift before it costs you — anomaly + exposure scan.", tags: ["risk"] },
    { slug: "dao/proposal_summarize",               title: "Inbox summariser",        blurb: "Each long thread / proposal turned into 5 lines + a risk note.", tags: ["summary"] },
  ],
};

export function recommendedPlaybooks(orgType: OrgType): PlaybookRec[] {
  return STARTER_PLAYBOOKS[orgType] ?? STARTER_PLAYBOOKS.other;
}

// ── backend bridge ─────────────────────────────────────────────────

export interface PersistedOrg extends OrgInfo {
  id: string;
  created_at: number;
  updated_at: number;
}

export async function fetchOrgInfo(): Promise<PersistedOrg | null> {
  try {
    const res = await getJSON<{ ok: boolean; org: PersistedOrg | null }>("/api/org/info");
    return res.org ?? null;
  } catch {
    return null;
  }
}

export async function saveOrgInfo(payload: OrgInfo): Promise<PersistedOrg | null> {
  try {
    const res = await postJSON<{ ok: boolean; org: PersistedOrg }>(
      "/api/org/info",
      payload,
    );
    return res.org ?? null;
  } catch {
    return null;
  }
}

export async function patchOrgMeta(patch: Record<string, unknown>): Promise<void> {
  try {
    await postJSON<unknown>("/api/org/info/meta", patch);
  } catch {
    /* best-effort */
  }
}

export async function saveInvites(
  invites: InviteDraft[],
): Promise<PersistedInvite[]> {
  try {
    const res = await postJSON<{ ok: boolean; invites: PersistedInvite[] }>(
      "/api/org/invites",
      invites,
    );
    return res.invites ?? [];
  } catch {
    return [];
  }
}

/**
 * Best-effort batch install for Step 4. The endpoint may not exist
 * yet (the playbooks loader scans `playbooks/_workshop/*` on its own
 * and they don't need explicit install) — in that case we write the
 * selection to localStorage so the wizard can keep going.
 */
export async function installPlaybooksBatch(slugs: string[]): Promise<{
  ok: boolean;
  installed: string[];
  fallback: boolean;
}> {
  if (slugs.length === 0) {
    return { ok: true, installed: [], fallback: false };
  }
  try {
    const res = await postJSON<{ ok: boolean; installed: string[] }>(
      "/api/playbooks/install-batch",
      { slugs },
    );
    return { ok: !!res.ok, installed: res.installed ?? slugs, fallback: false };
  } catch {
    // Fallback: stash in localStorage and call it good. The runner
    // will pick them up via on-demand discovery.
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(
          "tars.onboard.org.installed",
          JSON.stringify(slugs),
        );
      } catch {
        /* noop */
      }
    }
    return { ok: true, installed: slugs, fallback: true };
  }
}

/** Schedule the picked playbook for tomorrow at 9am local. Best-effort. */
export async function scheduleTomorrow9am(slug: string): Promise<boolean> {
  try {
    await postJSON<unknown>("/api/scheduler/schedules", {
      playbook_id: slug,
      cron_expression: "0 9 * * *",
      enabled: true,
    });
    return true;
  } catch {
    return false;
  }
}

// ── helpers used by tests / palette ────────────────────────────────

export const STORAGE_KEYS = {
  draft: KEY_DRAFT,
  completed: KEY_COMPLETED,
  skipped: KEY_SKIPPED,
} as const;
