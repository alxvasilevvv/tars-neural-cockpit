// SYNC: claude-w99-org-onboarding
/**
 * <OrgOnboarding /> — Wave 99.
 *
 * 5-step wizard at /onboard/org that gets a brand-new fund / company
 * from "downloaded TARS" to "first playbook running" in under 30 min.
 *
 * Steps:
 *   1. Org info       → POST /api/org/info
 *   2. Connect tools  → /api/connectors/* (Slack / Gmail / Calendar / GitHub)
 *   3. Invite team    → POST /api/org/invites (recorded as ROADMAP intent)
 *   4. Pick playbooks → role-based recommendations from `STARTER_PLAYBOOKS`
 *   5. First run      → /api/playbooks/run + optional /api/scheduler/schedules
 *
 * State + progress is mirrored into both `localStorage` (instant
 * resume) and the backend org row's metadata (so a different device
 * picks up at the right step). All step transitions are skippable
 * via the rail at the top — the operator can always return.
 *
 * Defensive `initial: opacity: 1` motion wrappers (Wave 70 pattern)
 * keep the page legible if framer hydrates late.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  Circle,
  ExternalLink,
  Mail,
  PartyPopper,
  Plus,
  Rocket,
  Sparkles,
  Trash2,
  Users,
  Zap,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { HelpButton } from "@/components/HelpButton";
import {
  type InviteDraft,
  type InviteRole,
  type OnboardingDraft,
  type OrgInfo,
  type OrgType,
  clearDraft,
  detectTimezone,
  fetchOrgInfo,
  installPlaybooksBatch,
  isCompleted as isOnboardingCompleted,
  loadDraft,
  loadSkipped,
  markCompleted,
  markSkipped,
  patchOrgMeta,
  recommendedPlaybooks,
  saveDraft,
  saveInvites,
  saveOrgInfo,
  scheduleTomorrow9am,
} from "@/lib/orgOnboarding";

// ── step rail ───────────────────────────────────────────────────────

const STEP_LABELS: { id: number; key: string; title: string }[] = [
  { id: 1, key: "org",        title: "Org info" },
  { id: 2, key: "connectors", title: "Connect tools" },
  { id: 3, key: "invites",    title: "Invite team" },
  { id: 4, key: "playbooks",  title: "Pick playbooks" },
  { id: 5, key: "first-run",  title: "First run" },
];

// ── connector grid ──────────────────────────────────────────────────

interface ConnectorCard {
  name: string;
  label: string;
  blurb: string;
  /** Lucide icon stub — keep small to render inside the 48px slot. */
  Icon: typeof Building2;
}

const CONNECTOR_CARDS: ConnectorCard[] = [
  { name: "slack",    label: "Slack",         blurb: "Mentions, DMs, channel posts.",     Icon: Sparkles },
  { name: "gmail",    label: "Gmail",         blurb: "Send + draft from your address.",   Icon: Mail },
  { name: "calendar", label: "Google Calendar", blurb: "Today + upcoming meetings.",       Icon: Circle },
  { name: "github",   label: "GitHub",        blurb: "PRs, issues, code RAG.",            Icon: Zap },
];

// ── org-type dropdown ───────────────────────────────────────────────

const ORG_TYPE_OPTIONS: { value: OrgType; label: string; sizeLabel: string }[] = [
  { value: "vc_fund",       label: "VC fund",        sizeLabel: "AUM (e.g. $50M)" },
  { value: "hedge_fund",    label: "Hedge fund",     sizeLabel: "AUM (e.g. $200M)" },
  { value: "family_office", label: "Family office",  sizeLabel: "AUM (e.g. $1B)" },
  { value: "saas_company",  label: "SaaS company",   sizeLabel: "Team size (e.g. 25)" },
  { value: "dao",           label: "DAO",            sizeLabel: "Treasury (e.g. $10M)" },
  { value: "research_lab",  label: "Research lab",   sizeLabel: "Team size (e.g. 12)" },
  { value: "other",         label: "Other",          sizeLabel: "Size / headcount" },
];

const PRIMARY_USE_CASES = [
  "LP reporting",
  "Deal screening",
  "Portfolio monitoring",
  "Outreach",
  "Compliance",
  "Custom",
];

// ── invite role labels ──────────────────────────────────────────────

const ROLE_LABELS: Record<InviteRole, string> = {
  admin: "Admin",
  designer: "Designer",
  analyst: "Analyst",
  viewer: "Viewer",
};

// ── i18n keys ────────────────────────────────────────────────────────
// All FE copy lives here so a future i18n re-enable picks them up
// without spelunking through JSX.
const COPY = {
  eyebrow:        "Wave 99",
  crumb:          "Org setup",
  title:          "Set up your organization",
  subtitle:       "Five quick steps. The wizard remembers where you left off — refresh, switch devices, come back anytime.",
  skip:           "Skip step",
  back:           "Back",
  next:           "Next",
  saving:         "Saving…",
  startOver:      "Start over",
  step1Heading:   "Tell us about your org",
  step2Heading:   "Connect the tools TARS will read from",
  step3Heading:   "Who else uses TARS in your org?",
  step3Roadmap:   "Multi-tenant workspaces ship in v9.3 — until then, invites are recorded as roadmap. We'll email when ready.",
  step3Multi:     "Will multiple people use TARS in your org?",
  step4Heading:   "Pick your starter playbooks",
  step4Hint:      "We tailored these to your org type. You can install more later from /workshop/materials.",
  step5Heading:   "Run your first playbook",
  step5Hint:      "Pick one of the playbooks you just installed. We'll run it now and show the receipt.",
  done:           "Done!",
  doneSub:        "Your org is set up. Three places to go next:",
} as const;

// ── helpers ─────────────────────────────────────────────────────────

function isEmail(value: string): boolean {
  return /.+@.+\..+/.test(value);
}

function parseInviteBlock(raw: string, defaultRole: InviteRole): InviteDraft[] {
  return raw
    .split(/\r?\n|,/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter(isEmail)
    .map((email) => ({ email: email.toLowerCase(), role: defaultRole }));
}

// ── component ───────────────────────────────────────────────────────

export function OrgOnboarding() {
  useDocumentMeta({
    title: "Set up your org · TARS",
    description:
      "5-step wizard for new funds and companies onboarding to TARS — org info, connectors, team, playbooks, first run.",
      ogImage: "https://tars.meeet.world/og-onboard.svg",
  });
  const navigate = useNavigate();

  // Draft state ------------------------------------------------------
  const [draft, setDraft] = useState<OnboardingDraft>(() => loadDraft());
  const [skipped, setSkippedSteps] = useState<number[]>(() => loadSkipped());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Persist draft on every change ------------------------------------
  useEffect(() => {
    saveDraft(draft);
  }, [draft]);

  // Hydrate from server on mount -------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const remote = await fetchOrgInfo();
      if (cancelled || !remote) return;
      setDraft((d) => ({
        ...d,
        org: {
          ...d.org,
          name: d.org.name ?? remote.name,
          type: (d.org.type ?? (remote.type as OrgType)) as OrgType,
          size: d.org.size ?? remote.size,
          timezone: d.org.timezone ?? remote.timezone,
          primary_use_case: d.org.primary_use_case ?? remote.primary_use_case,
        },
      }));
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-detect timezone if blank ------------------------------------
  useEffect(() => {
    if (!draft.org.timezone) {
      setDraft((d) => ({ ...d, org: { ...d.org, timezone: detectTimezone() } }));
    }
    // run once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Connector polling (Step 2) ---------------------------------------
  useEffect(() => {
    if (draft.step !== 2) return;
    let stopped = false;
    const tick = async () => {
      try {
        const r = await fetch("/api/connectors");
        if (!r.ok) return;
        const body = (await r.json()) as {
          connectors?: Array<{ name: string; configured?: boolean }>;
        };
        if (stopped || !body.connectors) return;
        setDraft((d) => {
          const next = { ...d.connectors };
          for (const row of body.connectors!) {
            if (row.configured) next[row.name] = "configured";
          }
          return { ...d, connectors: next };
        });
      } catch {
        /* offline / no daemon */
      }
    };
    void tick();
    const id = setInterval(tick, 3000);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [draft.step]);

  // Step navigation --------------------------------------------------
  const setStep = useCallback((step: number) => {
    setError(null);
    setDraft((d) => ({ ...d, step }));
  }, []);

  const skipStep = useCallback(
    (step: number) => {
      markSkipped(step);
      setSkippedSteps(loadSkipped());
      setStep(step + 1);
    },
    [setStep],
  );

  const startOver = useCallback(() => {
    if (!window.confirm("Reset wizard and clear saved answers?")) return;
    clearDraft();
    setDraft(loadDraft());
    setSkippedSteps([]);
    setError(null);
  }, []);

  // Step 1 submit ----------------------------------------------------
  const submitStep1 = useCallback(async () => {
    const name = (draft.org.name || "").trim();
    if (!name) {
      setError("Org name required");
      return;
    }
    setBusy("step1");
    setError(null);
    const payload: OrgInfo = {
      name,
      type: (draft.org.type as OrgType) || "other",
      size: draft.org.size || "",
      timezone: draft.org.timezone || detectTimezone(),
      primary_use_case: draft.org.primary_use_case || "",
      metadata: { wizard_step: 1 },
    };
    const saved = await saveOrgInfo(payload);
    setBusy(null);
    if (!saved) {
      // Still let them advance — backend may be disabled. Local draft
      // is the source of truth.
    }
    setStep(2);
  }, [draft.org, setStep]);

  // Step 2 submit ----------------------------------------------------
  const submitStep2 = useCallback(async () => {
    setBusy("step2");
    await patchOrgMeta({
      wizard_step: 2,
      connectors_summary: draft.connectors,
    });
    setBusy(null);
    setStep(3);
  }, [draft.connectors, setStep]);

  // Step 3 submit ----------------------------------------------------
  const submitStep3 = useCallback(async () => {
    setBusy("step3");
    if (draft.multi && draft.invites.length > 0) {
      await saveInvites(draft.invites);
    }
    await patchOrgMeta({
      wizard_step: 3,
      multi: draft.multi,
      invites_count: draft.invites.length,
    });
    setBusy(null);
    setStep(4);
  }, [draft.multi, draft.invites, setStep]);

  // Step 4 submit ----------------------------------------------------
  const submitStep4 = useCallback(async () => {
    setBusy("step4");
    const result = await installPlaybooksBatch(draft.selectedPlaybooks);
    await patchOrgMeta({
      wizard_step: 4,
      installed_playbooks: result.installed,
      install_fallback: result.fallback,
    });
    setBusy(null);
    setStep(5);
  }, [draft.selectedPlaybooks, setStep]);

  // Step 5 finish ----------------------------------------------------
  const finishWizard = useCallback(async () => {
    setBusy("step5");
    if (draft.scheduleNextDay && draft.firstRunSlug) {
      await scheduleTomorrow9am(draft.firstRunSlug);
    }
    await patchOrgMeta({
      wizard_step: 5,
      first_run_slug: draft.firstRunSlug ?? null,
      scheduled: draft.scheduleNextDay,
      completed_at: Date.now() / 1000,
    });
    markCompleted();
    setBusy(null);
    // Stay on this page so the user can hit one of the 3 CTAs.
  }, [draft.scheduleNextDay, draft.firstRunSlug]);

  // Convenience pickers ---------------------------------------------
  const orgType = (draft.org.type as OrgType) || "other";
  const recs = useMemo(() => recommendedPlaybooks(orgType), [orgType]);
  const sizeLabel = useMemo(
    () => ORG_TYPE_OPTIONS.find((o) => o.value === orgType)?.sizeLabel ?? "Size",
    [orgType],
  );
  const completedAlready = isOnboardingCompleted();

  return (
    <div className="mx-auto max-w-3xl px-6 pb-32 pt-6 sm:px-8">
      <div className="flex items-start justify-between gap-3">
        <Breadcrumbs
          items={[
            { label: "Home", to: "/" },
            { label: COPY.crumb },
          ]}
        />
        <HelpButton
          label="What is Org Onboarding?"
          body="A 5-step wizard for new funds and companies: organization details, team invites, playbook templates, connector linkage (Gmail / Slack / Calendar / GitHub), and a smoke run. Drafts save to localStorage so you can step away mid-flow."
        />
      </div>

      <header className="mb-8 mt-4">
        <p className="font-mono-tech text-[10px] uppercase tracking-[3px] text-ink-3">
          {COPY.eyebrow}
        </p>
        <h1 className="mt-2 font-display text-[32px] leading-tight text-ink sm:text-[40px]">
          {COPY.title}
        </h1>
        <p className="mt-3 max-w-prose text-[14px] leading-relaxed text-ink-2">
          {COPY.subtitle}
        </p>
        {completedAlready && (
          <p className="mt-3 inline-flex items-center gap-2 rounded-md border border-line bg-bg-1/40 px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
            <CheckCircle2 className="h-3 w-3 text-accent" /> Wizard already completed — re-running is safe.
          </p>
        )}
      </header>

      <StepRail
        current={draft.step}
        skipped={skipped}
        onJump={(s) => setStep(s)}
      />

      <div className="mt-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={`step-${draft.step}`}
            initial={{ opacity: 1, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          >
            {draft.step === 1 && (
              <Step1
                draft={draft}
                onChange={setDraft}
                onSubmit={submitStep1}
                onSkip={() => skipStep(1)}
                busy={busy === "step1"}
                error={error}
                sizeLabel={sizeLabel}
              />
            )}
            {draft.step === 2 && (
              <Step2
                draft={draft}
                onChange={setDraft}
                onSubmit={submitStep2}
                onSkip={() => skipStep(2)}
                onBack={() => setStep(1)}
                busy={busy === "step2"}
              />
            )}
            {draft.step === 3 && (
              <Step3
                draft={draft}
                onChange={setDraft}
                onSubmit={submitStep3}
                onSkip={() => skipStep(3)}
                onBack={() => setStep(2)}
                busy={busy === "step3"}
              />
            )}
            {draft.step === 4 && (
              <Step4
                draft={draft}
                onChange={setDraft}
                onSubmit={submitStep4}
                onSkip={() => skipStep(4)}
                onBack={() => setStep(3)}
                busy={busy === "step4"}
                recs={recs}
              />
            )}
            {draft.step === 5 && (
              <Step5
                draft={draft}
                onChange={setDraft}
                onFinish={finishWizard}
                onBack={() => setStep(4)}
                busy={busy === "step5"}
                navigate={(href) => navigate(href)}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <footer className="mt-16 flex items-center justify-between border-t border-line/60 pt-4 text-[11px] text-ink-3">
        <button
          type="button"
          onClick={startOver}
          className="font-mono-tech uppercase tracking-[2px] hover:text-ink"
        >
          {COPY.startOver}
        </button>
        <Link to="/workshop/materials" className="hover:text-accent">
          Skip ahead to /workshop/materials
        </Link>
      </footer>
    </div>
  );
}

// ── progress rail ───────────────────────────────────────────────────

function StepRail({
  current,
  skipped,
  onJump,
}: {
  current: number;
  skipped: number[];
  onJump: (step: number) => void;
}) {
  return (
    <ol className="flex items-center gap-3">
      {STEP_LABELS.map((s, idx) => {
        const isActive = s.id === current;
        const isPast = s.id < current;
        const wasSkipped = skipped.includes(s.id);
        return (
          <li key={s.id} className="flex flex-1 items-center gap-2">
            <button
              type="button"
              aria-current={isActive ? "step" : undefined}
              onClick={() => onJump(s.id)}
              className={`group flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left transition-colors ${
                isActive
                  ? "border-accent/50 bg-accent/10 text-accent"
                  : isPast
                    ? "border-line bg-bg-1/60 text-ink-2 hover:border-accent/40 hover:text-accent"
                    : "border-line bg-bg-0/50 text-ink-3"
              }`}
            >
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-mono-tech ${
                  isActive
                    ? "border-accent bg-accent text-bg-0"
                    : isPast
                      ? "border-accent/50 bg-bg-0 text-accent"
                      : "border-line bg-bg-0 text-ink-3"
                }`}
                aria-hidden
              >
                {isPast ? <Check className="h-3 w-3" /> : s.id}
              </span>
              <span className="hidden truncate font-mono-tech text-[10px] uppercase tracking-[2px] sm:inline">
                {s.title}
              </span>
              {wasSkipped && (
                <span className="ml-auto rounded border border-ink-3/30 px-1 font-mono-tech text-[8.5px] uppercase tracking-[1.5px] text-ink-3">
                  skipped
                </span>
              )}
            </button>
            {idx < STEP_LABELS.length - 1 && (
              <span className="hidden h-px w-3 bg-line sm:inline" aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ── Step 1: Org info ───────────────────────────────────────────────

function Step1({
  draft,
  onChange,
  onSubmit,
  onSkip,
  busy,
  error,
  sizeLabel,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onSubmit: () => void;
  onSkip: () => void;
  busy: boolean;
  error: string | null;
  sizeLabel: string;
}) {
  return (
    <section aria-labelledby="step1-h">
      <SectionHeader id="step1-h" title={COPY.step1Heading} icon={<Building2 className="h-4 w-4" />} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Org name" required>
          <input
            type="text"
            value={draft.org.name ?? ""}
            onChange={(e) =>
              onChange((d) => ({ ...d, org: { ...d.org, name: e.target.value } }))
            }
            placeholder="Acme Capital"
            className={fieldCls}
          />
        </Field>
        <Field label="Org type">
          <select
            value={draft.org.type ?? "other"}
            onChange={(e) =>
              onChange((d) => ({
                ...d,
                org: { ...d.org, type: e.target.value as OrgType },
              }))
            }
            className={fieldCls}
          >
            {ORG_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={sizeLabel}>
          <input
            type="text"
            value={draft.org.size ?? ""}
            onChange={(e) =>
              onChange((d) => ({ ...d, org: { ...d.org, size: e.target.value } }))
            }
            placeholder={sizeLabel}
            className={fieldCls}
          />
        </Field>
        <Field label="Time zone">
          <input
            type="text"
            value={draft.org.timezone ?? detectTimezone()}
            onChange={(e) =>
              onChange((d) => ({
                ...d,
                org: { ...d.org, timezone: e.target.value },
              }))
            }
            className={fieldCls}
          />
        </Field>
        <Field label="Primary use case" className="sm:col-span-2">
          <select
            value={draft.org.primary_use_case ?? ""}
            onChange={(e) =>
              onChange((d) => ({
                ...d,
                org: { ...d.org, primary_use_case: e.target.value },
              }))
            }
            className={fieldCls}
          >
            <option value="">Pick one…</option>
            {PRIMARY_USE_CASES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {error && <p className="mt-3 text-sm text-rose-400">{error}</p>}
      <StepActions onSubmit={onSubmit} onSkip={onSkip} busy={busy} />
    </section>
  );
}

// ── Step 2: connectors ─────────────────────────────────────────────

function Step2({
  draft,
  onChange,
  onSubmit,
  onSkip,
  onBack,
  busy,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onSubmit: () => void;
  onSkip: () => void;
  onBack: () => void;
  busy: boolean;
}) {
  const [imapOpen, setImapOpen] = useState(false);
  const [imapForm, setImapForm] = useState({ smtp_host: "", imap_host: "", username: "", password: "" });
  const counted = CONNECTOR_CARDS.filter((c) => draft.connectors[c.name] === "configured").length;

  const startConnect = useCallback(
    async (name: string) => {
      try {
        const r = await fetch(`/api/connectors/${name}/auth-url`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = (await r.json()) as { url?: string };
        if (body.url) {
          window.open(body.url, "_blank", "noopener,noreferrer,width=600,height=720");
          onChange((d) => ({ ...d, connectors: { ...d.connectors, [name]: "pending" } }));
        }
      } catch {
        onChange((d) => ({ ...d, connectors: { ...d.connectors, [name]: "error" } }));
      }
    },
    [onChange],
  );

  const submitImap = useCallback(async () => {
    try {
      // Vault store; backend tolerates missing endpoint and we still
      // mark configured locally so the wizard can advance.
      await fetch("/api/vault/secrets", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ key: "gmail_imap", value: JSON.stringify(imapForm) }),
      });
    } catch {
      /* best-effort */
    }
    onChange((d) => ({ ...d, connectors: { ...d.connectors, gmail: "configured" } }));
    setImapOpen(false);
  }, [imapForm, onChange]);

  return (
    <section aria-labelledby="step2-h">
      <SectionHeader
        id="step2-h"
        title={COPY.step2Heading}
        icon={<Sparkles className="h-4 w-4" />}
        right={
          <span className="rounded-md border border-line bg-bg-1/60 px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
            {counted} of {CONNECTOR_CARDS.length} connected
          </span>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {CONNECTOR_CARDS.map((c) => {
          const status = draft.connectors[c.name] ?? "";
          const configured = status === "configured";
          return (
            <div
              key={c.name}
              className={`flex items-start gap-3 rounded-lg border p-4 transition-colors ${
                configured
                  ? "border-accent/40 bg-accent/5"
                  : "border-line bg-bg-1/40"
              }`}
            >
              <span className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-md border border-line bg-bg-0 text-ink-2">
                <c.Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="font-display text-[15px] text-ink">{c.label}</h3>
                  <span
                    className={`font-mono-tech text-[9.5px] uppercase tracking-[2px] ${
                      configured ? "text-accent" : "text-ink-3"
                    }`}
                  >
                    {configured ? "configured" : status === "pending" ? "waiting…" : status === "error" ? "error" : "not connected"}
                  </span>
                </div>
                <p className="mt-0.5 text-[12.5px] text-ink-2">{c.blurb}</p>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => startConnect(c.name)}
                    className="rounded-md border border-line bg-bg-0 px-2.5 py-1 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 hover:border-accent/40 hover:text-accent"
                  >
                    {configured ? "Reconnect" : "Connect"}
                  </button>
                  {c.name === "gmail" && (
                    <button
                      type="button"
                      onClick={() => setImapOpen(true)}
                      className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3 hover:text-accent"
                    >
                      Use IMAP instead
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {imapOpen && (
        <div className="mt-4 rounded-lg border border-line bg-bg-1/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="font-display text-[14px] text-ink">Gmail IMAP / SMTP credentials</h4>
            <button
              type="button"
              onClick={() => setImapOpen(false)}
              className="rounded p-1 text-ink-3 hover:text-ink"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {(["smtp_host", "imap_host", "username", "password"] as const).map((k) => (
              <input
                key={k}
                type={k === "password" ? "password" : "text"}
                placeholder={k.replace("_", " ")}
                value={imapForm[k]}
                onChange={(e) => setImapForm((f) => ({ ...f, [k]: e.target.value }))}
                className={fieldCls}
              />
            ))}
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={submitImap}
              className="rounded-md border border-accent bg-accent/15 px-3 py-1.5 font-mono-tech text-[11px] uppercase tracking-[2px] text-accent hover:bg-accent/25"
            >
              Save credentials
            </button>
          </div>
        </div>
      )}

      <StepActions onSubmit={onSubmit} onSkip={onSkip} onBack={onBack} busy={busy} />
    </section>
  );
}

// ── Step 3: Invite team ────────────────────────────────────────────

function Step3({
  draft,
  onChange,
  onSubmit,
  onSkip,
  onBack,
  busy,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onSubmit: () => void;
  onSkip: () => void;
  onBack: () => void;
  busy: boolean;
}) {
  const [bulk, setBulk] = useState("");
  const [defaultRole, setDefaultRole] = useState<InviteRole>("viewer");

  const addBulk = useCallback(() => {
    const parsed = parseInviteBlock(bulk, defaultRole);
    if (parsed.length === 0) return;
    onChange((d) => {
      const seen = new Set(d.invites.map((i) => i.email));
      const merged = [...d.invites];
      for (const p of parsed) {
        if (!seen.has(p.email)) merged.push(p);
      }
      return { ...d, invites: merged };
    });
    setBulk("");
  }, [bulk, defaultRole, onChange]);

  return (
    <section aria-labelledby="step3-h">
      <SectionHeader
        id="step3-h"
        title={COPY.step3Heading}
        icon={<Users className="h-4 w-4" />}
        right={
          <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-amber-400">
            ROADMAP
          </span>
        }
      />

      <p className="mb-3 text-[13px] text-ink-2">{COPY.step3Roadmap}</p>

      <fieldset className="mb-4 flex items-center gap-3 text-[13px] text-ink">
        <legend className="sr-only">{COPY.step3Multi}</legend>
        <span className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3">
          {COPY.step3Multi}
        </span>
        {(["yes", "no"] as const).map((opt) => (
          <label key={opt} className="inline-flex items-center gap-1.5">
            <input
              type="radio"
              name="multi"
              checked={(opt === "yes") === draft.multi}
              onChange={() => onChange((d) => ({ ...d, multi: opt === "yes" }))}
            />
            <span className="text-ink-2">{opt === "yes" ? "Yes" : "Solo for now"}</span>
          </label>
        ))}
      </fieldset>

      {draft.multi && (
        <>
          <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_140px_120px]">
            <textarea
              rows={4}
              value={bulk}
              onChange={(e) => setBulk(e.target.value)}
              placeholder={"alice@acme.com\nbob@acme.com"}
              className={`${fieldCls} font-mono`}
            />
            <select
              value={defaultRole}
              onChange={(e) => setDefaultRole(e.target.value as InviteRole)}
              className={fieldCls}
            >
              {(Object.keys(ROLE_LABELS) as InviteRole[]).map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={addBulk}
              className="rounded-md border border-line bg-bg-0 px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-2 hover:border-accent/40 hover:text-accent"
            >
              <Plus className="mr-1 inline h-3 w-3" /> Add
            </button>
          </div>

          {draft.invites.length > 0 ? (
            <ul className="divide-y divide-line/40 rounded-lg border border-line bg-bg-1/40">
              {draft.invites.map((inv, idx) => (
                <li key={inv.email} className="flex items-center gap-2 px-3 py-2 text-[13px]">
                  <Mail className="h-3.5 w-3.5 text-ink-3" />
                  <span className="flex-1 truncate text-ink">{inv.email}</span>
                  <select
                    value={inv.role}
                    onChange={(e) =>
                      onChange((d) => {
                        const next = [...d.invites];
                        next[idx] = { ...next[idx], role: e.target.value as InviteRole };
                        return { ...d, invites: next };
                      })
                    }
                    className="rounded border border-line bg-bg-0 px-1.5 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-2"
                  >
                    {(Object.keys(ROLE_LABELS) as InviteRole[]).map((r) => (
                      <option key={r} value={r}>
                        {ROLE_LABELS[r]}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() =>
                      onChange((d) => ({
                        ...d,
                        invites: d.invites.filter((_, i) => i !== idx),
                      }))
                    }
                    className="rounded p-1 text-ink-3 hover:text-rose-400"
                    aria-label={`Remove ${inv.email}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-3">No invites yet — paste one email per line and click Add.</p>
          )}
        </>
      )}

      <StepActions onSubmit={onSubmit} onSkip={onSkip} onBack={onBack} busy={busy} />
    </section>
  );
}

// ── Step 4: pick playbooks ─────────────────────────────────────────

function Step4({
  draft,
  onChange,
  onSubmit,
  onSkip,
  onBack,
  busy,
  recs,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onSubmit: () => void;
  onSkip: () => void;
  onBack: () => void;
  busy: boolean;
  recs: ReturnType<typeof recommendedPlaybooks>;
}) {
  const toggle = (slug: string) =>
    onChange((d) => {
      const has = d.selectedPlaybooks.includes(slug);
      return {
        ...d,
        selectedPlaybooks: has
          ? d.selectedPlaybooks.filter((s) => s !== slug)
          : [...d.selectedPlaybooks, slug],
      };
    });

  return (
    <section aria-labelledby="step4-h">
      <SectionHeader id="step4-h" title={COPY.step4Heading} icon={<Rocket className="h-4 w-4" />} />
      <p className="mb-4 text-[13px] text-ink-2">{COPY.step4Hint}</p>
      {/* Wave 107 — bundle install shortcut. */}
      <a
        href="/bundles"
        className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-accent/40 bg-accent/5 px-4 py-3 text-[13px] text-ink no-underline hover:border-accent/60"
      >
        <span>
          <strong className="font-display">Install vertical bundle (recommended)</strong>{" "}
          — playbooks + schedules + dashboard + outreach in one click.
        </span>
        <span aria-hidden className="font-mono-tech text-accent">→</span>
      </a>
      <div className="grid gap-3 sm:grid-cols-2">
        {recs.map((rec) => {
          const checked = draft.selectedPlaybooks.includes(rec.slug);
          return (
            <label
              key={rec.slug}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                checked
                  ? "border-accent/50 bg-accent/5"
                  : "border-line bg-bg-1/40 hover:border-accent/30"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(rec.slug)}
                className="mt-1 h-4 w-4 accent-current text-accent"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h3 className="font-display text-[14px] text-ink">{rec.title}</h3>
                  <code className="font-mono-tech text-[10px] text-ink-3">{rec.slug}</code>
                </div>
                <p className="mt-0.5 text-[12.5px] leading-snug text-ink-2">{rec.blurb}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {rec.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded border border-line bg-bg-0 px-1.5 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.5px] text-ink-3"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </label>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-ink-3">
        Selected: {draft.selectedPlaybooks.length} playbook{draft.selectedPlaybooks.length === 1 ? "" : "s"}. They&rsquo;ll be ready to run after this step.
      </p>
      <StepActions onSubmit={onSubmit} onSkip={onSkip} onBack={onBack} busy={busy} disabled={draft.selectedPlaybooks.length === 0} />
    </section>
  );
}

// ── Step 5: first run ──────────────────────────────────────────────

function Step5({
  draft,
  onChange,
  onFinish,
  onBack,
  busy,
  navigate,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onFinish: () => void;
  onBack: () => void;
  busy: boolean;
  navigate: (href: string) => void;
}) {
  const [running, setRunning] = useState<"idle" | "running" | "done" | "error">("idle");
  const [progress, setProgress] = useState<string[]>([]);
  const [receiptId, setReceiptId] = useState<string | null>(null);

  const candidates = draft.selectedPlaybooks;

  const runNow = useCallback(async () => {
    if (!draft.firstRunSlug) return;
    setRunning("running");
    setProgress(["Starting playbook…"]);
    try {
      const r = await fetch("/api/playbooks/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ playbook_slug: draft.firstRunSlug }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = (await r.json()) as { receipt_id?: string; lines?: string[] };
      setProgress((p) => [...p, ...(body.lines ?? ["Done."])]);
      setReceiptId(body.receipt_id ?? null);
      setRunning("done");
    } catch (e) {
      // Backend may not have a runner yet; still let them mark complete.
      setProgress((p) => [...p, `Live runner unavailable: ${(e as Error).message}. Marked locally as run.`]);
      setRunning("done");
    }
  }, [draft.firstRunSlug]);

  return (
    <section aria-labelledby="step5-h">
      <SectionHeader id="step5-h" title={COPY.step5Heading} icon={<Zap className="h-4 w-4" />} />
      {running === "done" ? (
        <DoneScreen
          draft={draft}
          onChange={onChange}
          onFinish={onFinish}
          onBack={onBack}
          busy={busy}
          progress={progress}
          receiptId={receiptId}
          navigate={navigate}
        />
      ) : (
        <>
          <p className="mb-3 text-[13px] text-ink-2">{COPY.step5Hint}</p>
          {candidates.length === 0 ? (
            <p className="rounded-md border border-line bg-bg-1/40 p-3 text-[13px] text-ink-2">
              You skipped Step 4 — go back and pick at least one playbook to run, or click Finish to skip the first run.
            </p>
          ) : (
            <div className="grid gap-2">
              {candidates.map((slug) => (
                <label key={slug} className="flex cursor-pointer items-center gap-2 rounded-md border border-line bg-bg-1/40 p-2 text-[13px]">
                  <input
                    type="radio"
                    name="firstRun"
                    checked={draft.firstRunSlug === slug}
                    onChange={() => onChange((d) => ({ ...d, firstRunSlug: slug }))}
                  />
                  <code className="font-mono-tech text-[11px] text-ink-2">{slug}</code>
                </label>
              ))}
            </div>
          )}

          {progress.length > 0 && (
            <pre className="mt-3 overflow-x-auto rounded-md border border-line bg-bg-1/60 p-3 font-mono-tech text-[11px] text-ink-2">
              {progress.join("\n")}
            </pre>
          )}

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={onBack}
              className="rounded-md border border-line bg-bg-0 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 hover:text-ink"
            >
              <ArrowLeft className="mr-1 inline h-3 w-3" /> {COPY.back}
            </button>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onFinish}
                className="rounded-md border border-line px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 hover:text-ink"
              >
                Skip run, finish
              </button>
              <button
                type="button"
                onClick={runNow}
                disabled={!draft.firstRunSlug || running === "running"}
                className="rounded-md border border-accent bg-accent/15 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-accent hover:bg-accent/25 disabled:opacity-40"
              >
                {running === "running" ? "Running…" : "Run now"} <ArrowRight className="ml-1 inline h-3 w-3" />
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function DoneScreen({
  draft,
  onChange,
  onFinish,
  onBack,
  busy,
  progress,
  receiptId,
  navigate,
}: {
  draft: OnboardingDraft;
  onChange: (updater: (d: OnboardingDraft) => OnboardingDraft) => void;
  onFinish: () => void;
  onBack: () => void;
  busy: boolean;
  progress: string[];
  receiptId: string | null;
  navigate: (href: string) => void;
}) {
  return (
    <div>
      <div className="rounded-lg border border-accent/40 bg-accent/10 p-4">
        <div className="flex items-center gap-2 text-accent">
          <PartyPopper className="h-5 w-5" />
          <span className="font-display text-[18px]">{COPY.done}</span>
        </div>
        <p className="mt-1 text-[13px] text-ink-2">{COPY.doneSub}</p>
        {progress.length > 0 && (
          <pre className="mt-3 overflow-x-auto rounded border border-line bg-bg-0/50 p-3 font-mono-tech text-[10.5px] text-ink-2">
            {progress.join("\n")}
          </pre>
        )}
        {receiptId && (
          <p className="mt-2 text-[12px] text-ink-3">
            Receipt:{" "}
            <Link to={`/cockpit/traces?receipt=${receiptId}`} className="text-accent hover:underline">
              {receiptId}
            </Link>
          </p>
        )}
      </div>

      <label className="mt-4 flex cursor-pointer items-center gap-2 rounded-md border border-line bg-bg-1/40 p-3 text-[13px]">
        <input
          type="checkbox"
          checked={draft.scheduleNextDay}
          onChange={() => onChange((d) => ({ ...d, scheduleNextDay: !d.scheduleNextDay }))}
        />
        <span className="text-ink">Schedule it for tomorrow at 9am?</span>
        <span className="ml-auto font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
          Wave 97 scheduler
        </span>
      </label>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <CTAButton onClick={() => navigate("/dashboard")} icon={<Building2 className="h-4 w-4" />} title="Open Dashboard" subtitle="Your day at a glance" />
        <CTAButton onClick={() => navigate("/workshop/materials")} icon={<Sparkles className="h-4 w-4" />} title="Workshop tutorial" subtitle="Decks · recipes · videos" />
        <CTAButton href="mailto:cohort@meeet.world?subject=Team kickoff request" icon={<Users className="h-4 w-4" />} title="Schedule team kickoff" subtitle="With the meeet team" />
      </div>

      <div className="mt-4 flex justify-between">
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-line bg-bg-0 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 hover:text-ink"
        >
          <ArrowLeft className="mr-1 inline h-3 w-3" /> {COPY.back}
        </button>
        <button
          type="button"
          onClick={onFinish}
          disabled={busy}
          className="rounded-md border border-accent bg-accent/15 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-accent hover:bg-accent/25 disabled:opacity-40"
        >
          {busy ? COPY.saving : "Finish setup"}
        </button>
      </div>
    </div>
  );
}

function CTAButton({
  onClick,
  href,
  icon,
  title,
  subtitle,
}: {
  onClick?: () => void;
  href?: string;
  icon: ReactNode;
  title: string;
  subtitle: string;
}) {
  const cls =
    "flex items-start gap-3 rounded-lg border border-line bg-bg-1/40 p-3 text-left transition-colors hover:border-accent/40 hover:bg-accent/5";
  const inner = (
    <>
      <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-md border border-line bg-bg-0 text-ink-2">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block font-display text-[13px] text-ink">{title}</span>
        <span className="block text-[11.5px] text-ink-2">{subtitle}</span>
      </span>
      <ExternalLink className="ml-auto h-3.5 w-3.5 text-ink-3" />
    </>
  );
  if (href) {
    return (
      <a href={href} className={cls}>
        {inner}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  );
}

// ── shared bits ────────────────────────────────────────────────────

const fieldCls =
  "w-full rounded-md border border-line bg-bg-0 px-3 py-2 text-[13px] text-ink placeholder:text-ink-3 focus:border-accent/60 focus:outline-none";

function Field({ label, required, className, children }: { label: string; required?: boolean; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className ?? ""}`}>
      <span className="mb-1 block font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
        {label}
        {required && <span className="ml-1 text-rose-400">*</span>}
      </span>
      {children}
    </label>
  );
}

function SectionHeader({ id, title, icon, right }: { id: string; title: string; icon: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <h2 id={id} className="flex items-center gap-2 font-display text-[20px] text-ink">
        <span className="flex h-6 w-6 items-center justify-center rounded-md border border-line bg-bg-1/60 text-ink-2">
          {icon}
        </span>
        {title}
      </h2>
      {right}
    </div>
  );
}

function StepActions({
  onSubmit,
  onSkip,
  onBack,
  busy,
  disabled,
}: {
  onSubmit: () => void;
  onSkip: () => void;
  onBack?: () => void;
  busy?: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="rounded-md border border-line bg-bg-0 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-2 hover:text-ink"
          >
            <ArrowLeft className="mr-1 inline h-3 w-3" /> {COPY.back}
          </button>
        )}
        <button
          type="button"
          onClick={onSkip}
          className="font-mono-tech text-[11px] uppercase tracking-[2px] text-ink-3 hover:text-ink"
        >
          {COPY.skip}
        </button>
      </div>
      <button
        type="button"
        onClick={onSubmit}
        disabled={busy || disabled}
        className="rounded-md border border-accent bg-accent/15 px-3 py-2 font-mono-tech text-[11px] uppercase tracking-[2px] text-accent hover:bg-accent/25 disabled:opacity-40"
      >
        {busy ? COPY.saving : COPY.next} <ArrowRight className="ml-1 inline h-3 w-3" />
      </button>
    </div>
  );
}

export default OrgOnboarding;
