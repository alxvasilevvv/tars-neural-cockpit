import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Wallet,
  Mail,
  ArrowRight,
  Check,
  Loader2,
  Sparkles,
  Plus,
} from "lucide-react";
import { CornerFrame, StatusLozenge } from "@/components/Glyphs";
import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { activateRole, createCustomRole } from "@/lib/api";
// Wave 124 — CustomRoleModal + ROLES data extracted to keep this page <500 LOC.
import CustomRoleModal from "@/components/onboarding/CustomRoleModal";

/**
 * Safe localStorage wrapper. Private/incognito mode throws on write,
 * which used to crash the onboarding flow. Now we silently swallow —
 * the daemon's roles.json + token store remain authoritative; the
 * localStorage seed is just an optimistic boot hint.
 */
function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode / quota exceeded — daemon picks up via API anyway */
  }
}

/**
 * Onboarding — first-run wizard.
 *
 * 3 screens:
 *   1. Sign in    — magic-link via meeet.world (wallet OR email),
 *                   or "skip and stay local".
 *   2. Pick role  — 6 default roles + Custom learnable role.
 *                   (Was "Pick pack" — Phase M / P7 swap. Roles map onto
 *                   pack registry under the hood.)
 *   3. First brief — TARS reads your sources, drafts a one-page briefing.
 *
 * Persists state in localStorage so the daemon can pick it up on first
 * cockpit load. When Cursor ships /api/roles (Phase M / P7 backend),
 * the static ROLES const is replaced with `useEffect → fetchRoles()` —
 * one-line swap.
 */

type Step = 0 | 1 | 2;

// Wave 124 — Role/RoleSlug/ROLES/BRIEF_TICKS extracted to roles.data.ts.
import type { Role, RoleSlug } from "@/components/onboarding/roles.data";
import { ROLES, BRIEF_TICKS } from "@/components/onboarding/roles.data";

export function Onboarding() {
  useDocumentMeta({
    title: "Onboarding",
    description: "Sign in, pick a role, and TARS delivers your first useful brief in 60 seconds.",
    ogImage: "https://tars.meeet.world/og-onboarding.svg",
  });
  const [step, setStep] = useState<Step>(0);
  const [authMode, setAuthMode] = useState<"wallet" | "email" | "skip" | null>(null);
  const [authPending, setAuthPending] = useState(false);
  const [role, setRole] = useState<RoleSlug | null>(null);
  const [customRole, setCustomRole] = useState<{ name: string; description: string } | null>(null);
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [briefIdx, setBriefIdx] = useState(0);
  // Locks role-selection buttons during the in-flight `POST /api/roles/*`
  // call so a fast double-click can't kick off two activations.
  const [roleSubmitting, setRoleSubmitting] = useState(false);
  // Tracks pending timers so we can cancel them on unmount and avoid the
  // "setState on unmounted component" warning + stale localStorage writes.
  const authTimerRef = useRef<number | null>(null);
  const stepTimerRef = useRef<number | null>(null);
  const navigate = useNavigate();
  const t = useT();

  // Cleanup any pending timers when the page unmounts (route change mid-flow).
  useEffect(() => {
    return () => {
      if (authTimerRef.current !== null) window.clearTimeout(authTimerRef.current);
      if (stepTimerRef.current !== null) window.clearTimeout(stepTimerRef.current);
    };
  }, []);

  // ── Auth flow stub — opens meeet.world/auth in new tab and polls
  // localStorage for the token the auth-bridge writes back. ──
  const startAuth = (mode: "wallet" | "email") => {
    setAuthMode(mode);
    setAuthPending(true);
    const url =
      mode === "wallet"
        ? "https://meeet.world/auth?via=wallet&cb=local-7765"
        : "https://meeet.world/auth?via=email&cb=local-7765";
    if (typeof window !== "undefined") {
      window.open(url, "_blank", "noopener,noreferrer");
      // simulate token landing — real flow handled by /auth/callback POST.
      // Cancellable via authTimerRef so unmount mid-auth doesn't leave a
      // stale localStorage write firing after the user navigated away.
      if (authTimerRef.current !== null) window.clearTimeout(authTimerRef.current);
      authTimerRef.current = window.setTimeout(() => {
        safeSetItem("tars_token", "demo-token");
        setAuthPending(false);
        setStep(1);
        authTimerRef.current = null;
      }, 2200);
    }
  };

  const skipAuth = () => {
    safeSetItem("tars_local_only", "1");
    setAuthMode("skip");
    setStep(1);
  };

  const chooseRole = (slug: RoleSlug, payload?: { name: string; description: string }) => {
    if (roleSubmitting) return; // double-submit guard
    setRoleSubmitting(true);
    setRole(slug);
    safeSetItem("tars_role", slug);
    if (payload) {
      // Custom role — persist for the daemon to pick up. Real backend
      // synthesises a system_prompt_overlay; we store the seed.
      safeSetItem("tars_custom_role", JSON.stringify(payload));
    }

    // Best-effort live wire to the daemon. Built-in slugs activate directly;
    // custom-role payload triggers a synthesise + activate two-step. We don't
    // block the UX on either — the localStorage seed above is the source of
    // truth for the cockpit boot, and the daemon will pick this up on next
    // poll either way.
    void (async () => {
      try {
        if (payload && slug === "custom") {
          const created = await createCustomRole({
            name: payload.name,
            description: payload.description,
            backing_packs: [],
          });
          // Backend assigns the canonical slug (`custom-<hex>`); refresh the
          // local seed so the daemon and cockpit agree on what's active.
          safeSetItem("tars_role", created.slug);
          await activateRole(created.slug);
        } else {
          await activateRole(slug);
        }
      } catch {
        /* daemon offline — localStorage seed alone keeps onboarding usable */
      } finally {
        // Re-enable after step transition so the back-button user can pick
        // a different role without being stuck.
        setRoleSubmitting(false);
      }
    })();

    if (stepTimerRef.current !== null) window.clearTimeout(stepTimerRef.current);
    stepTimerRef.current = window.setTimeout(() => {
      setStep(2);
      stepTimerRef.current = null;
    }, 350);
  };

  // Step 2 — animate the brief building list (wire to real /briefing/run later)
  useEffect(() => {
    if (step !== 2) return;
    if (briefIdx >= BRIEF_TICKS.length - 1) return;
    const t = setTimeout(() => setBriefIdx(i => i + 1), 950);
    return () => clearTimeout(t);
  }, [step, briefIdx]);

  const finish = () => navigate("/cockpit");

  // We resolve role -> { displayName, displayDesc, color } here so the
  // step-2 header can show either a translated stock role or the operator's
  // own custom-role copy without juggling TKey fallbacks downstream.
  const activeRole = useMemo<{
    displayName: string;
    color: string;
  } | null>(() => {
    if (role === "custom" && customRole) {
      return {
        displayName: customRole.name || "Custom",
        color: "#F5F5F0",
      };
    }
    const r = ROLES.find(rr => rr.slug === role) ?? ROLES[5];
    return {
      displayName: t(r.nameKey),
      color: r.color,
    };
  }, [role, customRole, t]);

  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      {/* Ambient bg */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(50% 40% at 50% 0%, rgba(99,102,241,0.10), transparent 70%), radial-gradient(40% 35% at 80% 100%, rgba(139,92,246,0.07), transparent 70%)",
        }}
      />

      <section className="mx-auto max-w-[920px] px-8 pt-16 pb-24 md:px-12">
        {/* Stepper header */}
        <div className="mb-10 flex items-center gap-3 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
          {[0, 1, 2].map(i => {
            const isActive = i === step;
            const isPast = i < step;
            return (
              <div key={i} className="flex flex-1 items-center gap-3">
                <span
                  className="grid h-6 w-6 place-items-center rounded-full border tabular-nums transition-colors duration-300"
                  style={{
                    borderColor: isActive || isPast ? "var(--brand-indigo)" : "var(--color-line-strong)",
                    background: isActive ? "color-mix(in srgb, var(--brand-indigo) 18%, transparent)" : "transparent",
                    color: isActive || isPast ? "var(--brand-indigo)" : "var(--color-ink-3)",
                  }}
                >
                  {isPast ? <Check size={11} strokeWidth={2.4} /> : i + 1}
                </span>
                <span style={{ color: isActive || isPast ? "var(--color-ink-2)" : undefined }}>
                  {[t("onboarding.step.signin"), t("onboarding.step.role"), t("onboarding.step.brief")][i]}
                </span>
                {i < 2 && (
                  <span
                    className="h-px flex-1 transition-colors duration-300"
                    style={{ background: isPast ? "var(--brand-indigo)" : "var(--color-line-strong)" }}
                  />
                )}
              </div>
            );
          })}
        </div>

        <AnimatePresence mode="wait">
          {/* ── STEP 0 — sign in ────────────────────────────────────── */}
          {step === 0 && (
            <motion.div
              key="s0"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <h1
                className="font-display font-medium leading-[1] tracking-[-0.02em] text-ink"
                style={{ fontSize: "var(--text-display-md)" }}
              >
                {t("onboarding.s0.title.lead")}{" "}
                <span
                  className="bg-clip-text text-transparent"
                  style={{
                    backgroundImage:
                      "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                  }}
                >
                  {t("onboarding.s0.title.tail")}
                </span>
                .
              </h1>
              <p className="mt-5 max-w-[58ch] text-[14.5px] leading-[1.65] text-ink-2">
                {t("onboarding.s0.body")}
              </p>

              <div className="mt-9 grid grid-cols-1 gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => startAuth("wallet")}
                  disabled={authPending}
                  className="group relative flex items-center gap-4 rounded-[14px] border bg-bg-1 p-5 text-left transition-colors duration-200 hover:border-[color:var(--brand-indigo)]"
                  style={{ borderColor: authMode === "wallet" ? "var(--brand-indigo)" : "var(--color-line-strong)" }}
                >
                  <CornerFrame />
                  <span
                    className="grid h-10 w-10 place-items-center rounded-md"
                    style={{
                      background: "color-mix(in srgb, var(--brand-indigo) 14%, transparent)",
                      color: "var(--brand-indigo)",
                    }}
                  >
                    <Wallet size={18} strokeWidth={1.8} />
                  </span>
                  <div className="flex-1">
                    <div className="font-display text-[15px] tracking-[0.02em] text-ink">
                      {t("onboarding.s0.wallet.title")}
                    </div>
                    <div className="mt-0.5 text-[12px] leading-[1.45] text-ink-2">
                      {t("onboarding.s0.wallet.detail")}
                    </div>
                  </div>
                  {authMode === "wallet" && authPending ? (
                    <Loader2 size={16} className="animate-spin text-accent" />
                  ) : (
                    <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => startAuth("email")}
                  disabled={authPending}
                  className="group relative flex items-center gap-4 rounded-[14px] border bg-bg-1 p-5 text-left transition-colors duration-200 hover:border-[color:var(--brand-violet)]"
                  style={{ borderColor: authMode === "email" ? "var(--brand-violet)" : "var(--color-line-strong)" }}
                >
                  <CornerFrame />
                  <span
                    className="grid h-10 w-10 place-items-center rounded-md"
                    style={{
                      background: "color-mix(in srgb, var(--brand-violet) 14%, transparent)",
                      color: "var(--brand-violet)",
                    }}
                  >
                    <Mail size={18} strokeWidth={1.8} />
                  </span>
                  <div className="flex-1">
                    <div className="font-display text-[15px] tracking-[0.02em] text-ink">
                      {t("onboarding.s0.email.title")}
                    </div>
                    <div className="mt-0.5 text-[12px] leading-[1.45] text-ink-2">
                      {t("onboarding.s0.email.detail")}
                    </div>
                  </div>
                  {authMode === "email" && authPending ? (
                    <Loader2 size={16} className="animate-spin text-accent" />
                  ) : (
                    <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
                  )}
                </button>
              </div>

              <button
                type="button"
                onClick={skipAuth}
                className="mt-6 inline-flex items-center gap-2 rounded-md px-3 py-2 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors hover:text-ink"
              >
                {t("onboarding.s0.skip")}
                <ArrowRight size={12} className="text-ink-3" />
              </button>
            </motion.div>
          )}

          {/* ── STEP 1 — pick role ──────────────────────────────────── */}
          {step === 1 && (
            <motion.div
              key="s1"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <h1
                className="font-display font-medium leading-[1] tracking-[-0.02em] text-ink"
                style={{ fontSize: "var(--text-display-md)" }}
              >
                {t("onboarding.s1.title.lead")}{" "}
                <span
                  className="bg-clip-text text-transparent"
                  style={{
                    backgroundImage:
                      "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                  }}
                >
                  {t("onboarding.s1.title.tail")}
                </span>
                .
              </h1>
              <p className="mt-5 max-w-[58ch] text-[14.5px] leading-[1.65] text-ink-2">
                {t("onboarding.s1.body")}
              </p>

              <ul className="mt-9 grid grid-cols-1 gap-3 md:grid-cols-2">
                {ROLES.map(r => {
                  const selected = role === r.slug;
                  const Icon = r.Icon;
                  return (
                    <li key={r.slug}>
                      <button
                        type="button"
                        onClick={() => chooseRole(r.slug)}
                        disabled={roleSubmitting}
                        aria-busy={roleSubmitting && role === r.slug}
                        className="group relative flex w-full items-center gap-4 rounded-[14px] border bg-bg-1 p-5 text-left transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                        style={{ borderColor: selected ? r.color : "var(--color-line-strong)" }}
                      >
                        <CornerFrame />
                        <span
                          className="grid h-10 w-10 place-items-center rounded-md"
                          style={{
                            background: `color-mix(in srgb, ${r.color} 14%, transparent)`,
                            color: r.color,
                          }}
                        >
                          <Icon size={18} strokeWidth={1.8} />
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span
                              className="font-mono-tech text-[10.5px] uppercase tracking-[2.6px]"
                              style={{ color: r.color }}
                            >
                              {r.num}
                            </span>
                            <span className="font-display text-[15px] tracking-[0.02em] text-ink">
                              {t(r.nameKey)}
                            </span>
                          </div>
                          <div className="mt-1 text-[12.5px] leading-[1.5] text-ink-2">
                            {t(r.descriptionKey)}
                          </div>
                        </div>
                        {selected ? (
                          <Check size={16} style={{ color: r.color }} strokeWidth={2.4} />
                        ) : (
                          <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
                        )}
                      </button>
                    </li>
                  );
                })}

                {/* Custom role card — opens modal */}
                <li className="md:col-span-2">
                  <button
                    type="button"
                    onClick={() => setShowCustomModal(true)}
                    className="group relative flex w-full items-center gap-4 rounded-[14px] border-2 border-dashed bg-bg-1/40 p-5 text-left transition-all duration-200 hover:-translate-y-0.5"
                    style={{
                      borderColor: customRole ? "var(--brand-indigo)" : "var(--color-line-strong)",
                      background: customRole
                        ? "color-mix(in srgb, var(--brand-indigo) 5%, transparent)"
                        : undefined,
                    }}
                  >
                    <CornerFrame />
                    <span
                      className="grid h-10 w-10 place-items-center rounded-md"
                      style={{
                        background:
                          "linear-gradient(135deg, color-mix(in srgb, var(--brand-indigo) 14%, transparent) 0%, color-mix(in srgb, var(--brand-cyan) 14%, transparent) 100%)",
                        color: "var(--color-meeet-cyan, var(--brand-cyan))",
                      }}
                    >
                      <Sparkles size={18} strokeWidth={1.8} />
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className="font-mono-tech text-[10.5px] uppercase tracking-[2.6px]"
                          style={{ color: "var(--brand-indigo)" }}
                        >
                          07
                        </span>
                        <span className="font-display text-[15px] tracking-[0.02em] text-ink">
                          {customRole ? customRole.name : t("onboarding.s1.custom.name")}
                        </span>
                        {!customRole && (
                          <span className="font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                            {t("onboarding.s1.custom.badge")}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 max-w-[64ch] text-[12.5px] leading-[1.5] text-ink-2">
                        {customRole?.description ?? t("onboarding.s1.custom.desc")}
                      </div>
                    </div>
                    <Plus size={16} className="text-ink-3 transition-transform group-hover:rotate-90" />
                  </button>
                </li>
              </ul>

              {customRole && (
                <button
                  type="button"
                  onClick={() => chooseRole("custom", customRole)}
                  disabled={roleSubmitting}
                  aria-busy={roleSubmitting && role === "custom"}
                  className="mt-5 inline-flex items-center gap-2 rounded-md px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                  style={{
                    background: "var(--brand-cta-gradient)",
                    boxShadow:
                      "0 0 0 1px rgba(99,102,241,0.45), 0 12px 32px -10px rgba(99,102,241,0.55)",
                  }}
                >
                  {t("onboarding.s1.custom.continue")}
                  <ArrowRight size={14} strokeWidth={1.7} />
                </button>
              )}
            </motion.div>
          )}

          {/* ── STEP 2 — first brief ────────────────────────────────── */}
          {step === 2 && activeRole && (
            <motion.div
              key="s2"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="mb-3 flex items-center gap-3">
                <span
                  className="grid h-7 w-7 place-items-center rounded-md"
                  style={{
                    background: `color-mix(in srgb, ${activeRole.color} 14%, transparent)`,
                    color: activeRole.color,
                  }}
                >
                  <Sparkles size={14} strokeWidth={1.8} />
                </span>
                <span className="font-mono-tech text-[10.5px] uppercase tracking-[2.6px] text-ink-2">
                  {t("onboarding.s2.role")} <span className="text-ink">{activeRole.displayName}</span>
                </span>
                <StatusLozenge label={t("onboarding.s2.status")} tone="accent" />
              </div>

              <h1
                className="font-display font-medium leading-[1] tracking-[-0.02em] text-ink"
                style={{ fontSize: "var(--text-display-md)" }}
              >
                {t("onboarding.s2.title.lead")}{" "}
                <span
                  className="bg-clip-text text-transparent"
                  style={{
                    backgroundImage:
                      "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                  }}
                >
                  {t("onboarding.s2.title.tail")}
                </span>
                .
              </h1>
              <p className="mt-5 max-w-[58ch] text-[14.5px] leading-[1.65] text-ink-2">
                {t("onboarding.s2.body")}
              </p>

              {/* Build log */}
              <ol className="mt-9 grid gap-3 rounded-[14px] border border-line bg-bg-1 p-5">
                {BRIEF_TICKS.map((line, i) => {
                  const done = i < briefIdx;
                  const active = i === briefIdx;
                  return (
                    <li
                      key={i}
                      className="flex items-baseline gap-3 font-mono-tech text-[11.5px] leading-[1.5] text-ink-2"
                    >
                      <span
                        className="grid h-4 w-4 shrink-0 place-items-center rounded-full"
                        style={{
                          background: done
                            ? "color-mix(in srgb, var(--color-success) 14%, transparent)"
                            : active
                              ? "color-mix(in srgb, var(--brand-indigo) 14%, transparent)"
                              : "transparent",
                          color: done ? "var(--color-success)" : active ? "var(--brand-indigo)" : "var(--color-ink-3)",
                          boxShadow: done
                            ? "inset 0 0 0 1px rgba(52,211,153,0.45)"
                            : "inset 0 0 0 1px var(--color-line-strong)",
                        }}
                      >
                        {done ? (
                          <Check size={9} strokeWidth={2.6} />
                        ) : active ? (
                          <Loader2 size={9} className="animate-spin" strokeWidth={2.4} />
                        ) : (
                          <span className="h-1 w-1 rounded-full bg-current" />
                        )}
                      </span>
                      <span className={done ? "text-ink" : active ? "text-ink" : ""}>{line}</span>
                    </li>
                  );
                })}
              </ol>

              <button
                type="button"
                onClick={finish}
                disabled={briefIdx < BRIEF_TICKS.length - 1}
                className="mt-7 inline-flex items-center gap-2 rounded-md px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                style={{
                  background: "linear-gradient(135deg, var(--brand-indigo) 0%, var(--brand-violet) 100%)",
                  boxShadow:
                    "0 0 0 1px rgba(99,102,241,0.45), 0 12px 32px -10px rgba(99,102,241,0.55)",
                }}
              >
                {t("onboarding.s2.cta")}
                <ArrowRight size={14} strokeWidth={1.7} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* ── Custom role modal ─────────────────────────────────────── */}
      <AnimatePresence>
        {showCustomModal && (
          <CustomRoleModal
            onClose={() => setShowCustomModal(false)}
            onSave={payload => {
              setCustomRole(payload);
              setShowCustomModal(false);
            }}
            initial={customRole ?? undefined}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

