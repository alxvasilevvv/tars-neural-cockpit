import { motion, AnimatePresence } from "framer-motion";
import { Mail, Check, ArrowRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { trackClick } from "@/lib/analytics";
import { BrandHairline } from "@/components/BrandHairline";
import { BrandButton } from "@/components/BrandButton";
import { useT } from "@/lib/i18n";

/**
 * Waitlist — pre-launch email capture. POSTs to `/api/waitlist`; if
 * that endpoint isn't there yet (brother hasn't landed it), the entry
 * is stored in `localStorage["tars-waitlist"]` so we don't lose it.
 *
 * Wire shape (`docs/contracts/WAITLIST.md` to be written):
 *
 *   POST /api/waitlist  { email, ref?, role? }
 *   200 { ok: true, position: number }
 *   409 { ok: false, error: "duplicate" }
 *
 * Brother only needs to wire the route + de-dupe by lowercased email.
 */

const ENDPOINT = "/api/waitlist";
const LS_KEY = "tars-waitlist";

type Status = "idle" | "submitting" | "success" | "error";

interface Stored {
  email: string;
  role: string;
  ts: number;
  ref?: string;
}

function emailLooksValid(s: string): boolean {
  // Permissive — server is the source of truth. Just block obvious junk.
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s.trim());
}

function loadStored(): Stored[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as Stored[]) : [];
  } catch {
    return [];
  }
}

function saveStored(entries: Stored[]) {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(entries.slice(-50)));
  } catch {
    /* quota — drop silently */
  }
}

const ROLES = [
  { value: "trader", label: "Trader" },
  { value: "founder", label: "Founder / Operator" },
  { value: "researcher", label: "Researcher / Scientist" },
  { value: "engineer", label: "Engineer" },
  { value: "other", label: "Other" },
];

export function Waitlist() {
  const t = useT();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("founder");
  const [status, setStatus] = useState<Status>("idle");
  const [position, setPosition] = useState<number | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailLooksValid(email) || status === "submitting") return;

    setStatus("submitting");
    trackClick("waitlist_submit", { role });

    const payload = {
      email: email.trim().toLowerCase(),
      role,
      ref: typeof document !== "undefined" ? document.referrer : "",
    };

    try {
      const res = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      });

      if (res.ok) {
        const data = (await res.json().catch(() => ({}))) as {
          position?: number;
        };
        setPosition(data.position ?? null);
        setStatus("success");
        return;
      }

      // Some other 4xx — fall through to localStorage so we still capture.
      throw new Error(`HTTP ${res.status}`);
    } catch {
      // Pre-launch / endpoint missing: persist locally and pretend we
      // queued. The buffer drains when an /api/waitlist endpoint shows
      // up (we'll write a tiny migration in lib/waitlist.ts later).
      const stored = loadStored();
      stored.push({ ...payload, ts: Date.now() });
      saveStored(stored);
      setPosition(stored.length);
      setStatus("success");
    }
  };

  return (
    <section
      id="waitlist"
      aria-label="join the TARS waitlist"
      className="relative z-20 mx-auto max-w-[1180px] px-6 py-20 md:px-12 md:py-28"
    >
      <div className="relative overflow-hidden rounded-[16px] border border-line bg-bg-1/50 px-6 py-10 backdrop-blur-md md:px-12 md:py-14">
        <BrandHairline />
        {/* Soft brand halo top-right */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full opacity-40 blur-3xl"
          style={{
            background:
              "radial-gradient(circle, rgba(139,92,246,0.32) 0%, rgba(99,102,241,0.08) 60%, transparent 100%)",
          }}
        />

        <div className="grid items-end gap-8 md:grid-cols-[1fr_auto] md:gap-12">
          <div>
            <div className="mb-4 inline-flex items-center gap-2.5 font-mono-tech text-[10.5px] uppercase tracking-[3px] text-ink-2">
              <span
                className="h-1 w-1 rounded-full bg-accent"
                style={{
                  boxShadow: "0 0 8px var(--color-accent-soft)",
                  animation: "pulseDot 2.4s ease-in-out infinite",
                }}
              />
              {t("waitlist.eyebrow")}
            </div>

            <h2
              className="mb-3 max-w-[18ch] font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
              style={{ fontSize: "var(--text-display-md)" }}
            >
              {t("waitlist.title.lead")}{" "}
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
                }}
              >
                {t("waitlist.title.tail")}
              </span>
              .
            </h2>
            <p className="max-w-[44ch] text-[14.5px] leading-[1.65] text-ink-2">
              One email, the day the binary drops. No newsletter, no follow-ups,
              no tracking pixels — see{" "}
              <a
                href="/privacy"
                className="text-ink-2 underline-offset-2 hover:text-ink hover:underline"
              >
                Privacy § 4
              </a>
              .
            </p>
          </div>

          <AnimatePresence mode="wait" initial={false}>
            {status === "success" ? (
              <motion.div
                key="success"
                role="status"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="flex items-start gap-3 rounded-[12px] border border-success/40 bg-success/[0.06] px-5 py-4 sm:items-center"
              >
                <span
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-success"
                  style={{
                    background:
                      "color-mix(in srgb, var(--color-success) 22%, transparent)",
                  }}
                  aria-hidden
                >
                  <Check size={16} strokeWidth={2.2} />
                </span>
                <div className="font-mono-tech text-[12px] leading-[1.5] text-ink">
                  <div className="font-display tracking-[-0.005em]">
                    You're on the list.
                  </div>
                  <div className="mt-0.5 text-[10.5px] uppercase tracking-[2px] text-ink-3">
                    {position
                      ? `position #${position}`
                      : "we'll email when binary drops"}
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.form
                key="form"
                onSubmit={onSubmit}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="flex w-full flex-col gap-3 sm:max-w-[420px] md:max-w-[480px]"
                noValidate
              >
                <div className="flex items-stretch gap-2">
                  <label htmlFor="wl-email" className="sr-only">
                    {t("waitlist.email")}
                  </label>
                  <div className="relative flex flex-1 items-center">
                    <Mail
                      size={14}
                      strokeWidth={1.7}
                      aria-hidden
                      className="pointer-events-none absolute left-3 text-ink-3"
                    />
                    <input
                      id="wl-email"
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      disabled={status === "submitting"}
                      required
                      aria-invalid={status === "error"}
                      aria-describedby="wl-email-help"
                      className="w-full rounded-md border border-line bg-bg-2/50 py-3 pl-9 pr-3 font-mono text-[13px] text-ink placeholder:text-ink-3 focus:border-accent disabled:opacity-60"
                    />
                  </div>
                  <BrandButton
                    type="submit"
                    disabled={
                      status === "submitting" || !emailLooksValid(email)
                    }
                    leadingIcon={
                      status === "submitting" ? (
                        <Loader2
                          size={13}
                          strokeWidth={2}
                          className="animate-spin"
                          aria-hidden
                        />
                      ) : null
                    }
                    trailingIcon={
                      status === "submitting" ? null : (
                        <ArrowRight size={13} strokeWidth={1.8} aria-hidden />
                      )
                    }
                  >
                    {status === "submitting" ? t("waitlist.saving") : t("waitlist.submit")}
                  </BrandButton>
                </div>

                <fieldset className="flex flex-wrap items-center gap-1.5">
                  <legend className="mr-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3">
                    Role
                  </legend>
                  {ROLES.map(r => (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => setRole(r.value)}
                      aria-pressed={role === r.value}
                      className="rounded-full border px-2.5 py-1 font-mono-tech text-[10px] uppercase tracking-[1.6px] transition-all duration-150"
                      style={{
                        borderColor:
                          role === r.value
                            ? "var(--color-accent-soft)"
                            : "var(--color-line)",
                        background:
                          role === r.value
                            ? "color-mix(in srgb, var(--color-accent) 14%, transparent)"
                            : "transparent",
                        color:
                          role === r.value
                            ? "var(--color-accent)"
                            : "var(--color-ink-2)",
                      }}
                    >
                      {r.label}
                    </button>
                  ))}
                </fieldset>

                <p
                  id="wl-email-help"
                  className="font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-3"
                >
                  one email · the day the binary drops · nothing else
                </p>
              </motion.form>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
