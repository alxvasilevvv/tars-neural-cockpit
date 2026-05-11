/**
 * PitchSlides — Wave 124 split out of /pages/Pitch.tsx (was 942 LOC).
 * Hosts the 12-slide deck data + reusable slide primitives. The page
 * itself keeps the framer-motion shell, keyboard nav, and footer rail.
 *
 * Pure refactor — no behavior change. The page imports `SLIDES` and
 * the `NavBtn` primitive from here.
 */

import { type ReactNode } from "react";
import { CountUpNumber } from "@/components/CountUpNumber";
import {
  ArrowRight,
  Download,
  Lock,
  ShieldCheck,
  GitBranch,
  Cpu,
  Zap,
  Eye,
} from "lucide-react";

export interface SlideDef {
  num: string;
  title: string | ReactNode;
  body: ReactNode;
  /** Eyebrow tag for the upper-left corner. */
  tag: string;
}

export function NavBtn({
  children,
  onClick,
  disabled,
  ariaLabel,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      className="grid h-8 w-8 place-items-center rounded-full text-ink-2 transition-colors hover:bg-white/[0.05] hover:text-ink disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}

function StatGrid({
  cells,
}: {
  cells: { num: string; label: string; color: string }[];
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {cells.map((c, i) => {
        // Parse numeric prefix + non-digit suffix (e.g. "100%" → 100, "%").
        const match = c.num.match(/^(-?\d+(?:\.\d+)?)(.*)$/);
        const numericValue = match ? parseFloat(match[1]) : NaN;
        const suffix = match ? match[2] : "";
        const animatable = Number.isFinite(numericValue);

        return (
          <div
            key={c.label}
            className="rounded-[10px] border border-line bg-bg-1/60 p-4"
          >
            <div
              className="font-display font-medium leading-none tabular-nums"
              style={{ fontSize: "clamp(1.8rem, 3.4vw, 2.6rem)", color: c.color }}
            >
              {animatable ? (
                <CountUpNumber
                  value={numericValue}
                  suffix={suffix}
                  duration={1.4}
                  delay={i * 0.08}
                />
              ) : (
                c.num
              )}
            </div>
            <div className="mt-1.5 font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-2">
              {c.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="grid gap-3 text-[15px] leading-[1.55] text-ink-2">
      {items.map((it, i) => (
        <li key={i} className="grid grid-cols-[18px_1fr] items-baseline gap-3">
          <span className="text-accent">+</span>
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

function ColumnPair({
  left,
  right,
}: {
  left: { title: string; body: ReactNode };
  right: { title: string; body: ReactNode };
}) {
  return (
    <div className="grid grid-cols-1 gap-7 md:grid-cols-2 md:gap-10">
      <div>
        <h3 className="mb-3 font-display text-[16px] tracking-[0.02em] text-ink">
          {left.title}
        </h3>
        <div className="text-[14.5px] leading-[1.6] text-ink-2">{left.body}</div>
      </div>
      <div>
        <h3 className="mb-3 font-display text-[16px] tracking-[0.02em] text-ink">
          {right.title}
        </h3>
        <div className="text-[14.5px] leading-[1.6] text-ink-2">{right.body}</div>
      </div>
    </div>
  );
}

function PriceCard({
  name,
  price,
  sub,
  bullets,
  recommended,
  color,
}: {
  name: string;
  price: string;
  sub: string;
  bullets: string[];
  recommended?: boolean;
  color: string;
}) {
  return (
    <div
      className="relative overflow-hidden rounded-[12px] border bg-bg-1/60 p-5"
      style={{
        borderColor: recommended ? color : "var(--color-line)",
        background: recommended
          ? `linear-gradient(180deg, color-mix(in srgb, ${color} 8%, var(--color-bg-1)) 0%, var(--color-bg-1) 60%)`
          : undefined,
      }}
    >
      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-px"
        style={{ background: color, opacity: recommended ? 1 : 0.35 }}
      />
      <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px]" style={{ color }}>
        {name}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span
          className="font-display font-medium leading-none tabular-nums text-ink"
          style={{ fontSize: "1.8rem" }}
        >
          {price}
        </span>
        <span className="font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
          {sub}
        </span>
      </div>
      <ul className="mt-3 grid gap-1.5 text-[12px] leading-[1.45] text-ink-2">
        {bullets.map((b, i) => (
          <li key={i} className="grid grid-cols-[10px_1fr] items-baseline gap-1.5">
            <span style={{ color }}>·</span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ─── ASCII architecture diagram (referenced from slide 04) ──────────── */

const ARCH_DIAGRAM = `┌────── meeet.world ──────┐
│ identity · billing      │
│ encrypted ingest 1.1.0  │
│ marketplace · relay     │
└─────▲─────────▲─────────┘
      │         │
      │ E2E ciphertext only
      │         │
┌─────┴───┐ ┌───┴──────┐
│ macOS   │ │ Windows  │
│ HOST    │ │ HOST     │
└────▲────┘ └──────────┘
     │ LAN bonjour
┌────┴────────────┐
│ iOS · Android   │
│ thin clients    │
└─────────────────┘`;

/* ─── 12 slides ────────────────────────────────────────────────────── */

export const SLIDES: SlideDef[] = [
  // 1. Title
  {
    num: "00",
    tag: "TARS · meeet.world",
    title: (
      <>
        <span
          className="bg-clip-text text-transparent"
          style={{
            backgroundImage:
              "linear-gradient(95deg, #6366F1 0%, #F5F5F0 55%, #06B6D4 100%)",
          }}
        >
          TARS
        </span>
        <br />
        <span className="text-ink-2">Agent Intelligence.</span>
      </>
    ),
    body: (
      <div className="grid gap-7 md:grid-cols-[1.2fr_1fr] md:gap-10">
        <div>
          <p className="max-w-[52ch] text-[16px] leading-[1.7] text-ink-2">
            The local-first AI agent built for operators. Multi-LLM council,
            Mac actions, signed receipts, $MEEET economy. Ships under the
            meeet.world brand.
          </p>
          <div className="mt-9 grid gap-3">
            <div className="inline-flex items-center gap-2.5 rounded-md border border-line bg-bg-1/60 px-4 py-2.5 font-mono-tech text-[11.5px] text-ink-2">
              <Download size={13} strokeWidth={1.7} className="text-accent" />
              <span style={{ color: "#6366F1" }}>$</span>
              <code className="text-ink">curl -fLO https://github.com/alxvasilevvv/tars-neural-cockpit/releases/download/v8.4.0/TARS_8.4.0_aarch64.dmg && open TARS_8.4.0_aarch64.dmg</code>
            </div>
            <div className="font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3">
              v9.0 · Phase L9 desktop scaffolded · contract 1.1.0
            </div>
          </div>
        </div>
        <div>
          <StatGrid
            cells={[
              { num: "28", label: "AI agents",      color: "#6366F1" },
              { num: "14", label: "Native skills",  color: "#8B5CF6" },
              { num: "6",  label: "LLM providers",  color: "#06B6D4" },
              { num: "4",  label: "Domain packs",   color: "#A78BFA" },
            ]}
          />
        </div>
      </div>
    ),
  },

  // 2. Problem
  {
    num: "01",
    tag: "PROBLEM",
    title: (
      <>
        Operators don't want chat.
        <br />
        <span className="text-ink-2">They want an agent that does the work.</span>
      </>
    ),
    body: (
      <div className="grid gap-9 md:grid-cols-2">
        <div>
          <p className="text-[15px] leading-[1.7] text-ink-2">
            Existing tools split the operator: an IDE-coupled assistant for
            code, a chat client for thinking, a separate inbox triage tool, a
            macro for file moves. None of them touch the operating system or
            run continuously in the background.
          </p>
          <p className="mt-5 text-[15px] leading-[1.7] text-ink-2">
            And every cloud chat bills by the token without showing the
            operator what they're paying for.
          </p>
        </div>
        <Bullets
          items={[
            "Cursor lives in VS Code — code only, no system access.",
            "Claude Desktop is locked to one model and one window.",
            "ChatGPT desktop has no memory ledger or background mode.",
            "Macros automate one app, can't reason across mail / calendar / files.",
            "Cloud bills hidden in monthly statements, no per-action receipts.",
          ]}
        />
      </div>
    ),
  },

  // 3. Solution
  {
    num: "02",
    tag: "SOLUTION",
    title: (
      <>
        Local-first cockpit.
        <br />
        <span
          className="bg-clip-text text-transparent"
          style={{
            backgroundImage:
              "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
          }}
        >
          Eight LLMs, four packs, one core.
        </span>
      </>
    ),
    body: (
      <ColumnPair
        left={{
          title: "What it is",
          body: (
            <Bullets
              items={[
                "A FastAPI daemon on `127.0.0.1` your cockpit talks to.",
                "Memory ledger + cost ledger + receipt chain in SQLite.",
                "Multi-LLM council with two-voice deliberation per action.",
                "Mac Operator: sandbox-exec'd file/web/system actions.",
                "Pluggable domain packs + skill marketplace.",
              ]}
            />
          ),
        }}
        right={{
          title: "What it isn't",
          body: (
            <Bullets
              items={[
                "Not a SaaS — your data stays on your machine.",
                "Not single-vendor — BYO any LLM key, any time.",
                "Not a chat box — actions, receipts, schedules, T2T.",
                "Not opinionated about your stack — MCP both ways.",
                "Not closed — MIT license on the core.",
              ]}
            />
          ),
        }}
      />
    ),
  },

  // 4. Demo
  {
    num: "03",
    tag: "DEMO",
    title: (
      <>
        Three things you couldn't do before.
      </>
    ),
    body: (
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {[
          {
            tag: "DAILY BRIEF",
            title: "60-second briefing",
            body: "Calendar + unread mail + starred repos → one-page brief drafted by the council.",
            color: "#6366F1",
          },
          {
            tag: "MAC ACTION",
            title: "Sort ~/Downloads",
            body: "Sandbox-exec'd file moves with 10-minute undo. Signed receipt anchored.",
            color: "#8B5CF6",
          },
          {
            tag: "T2T DEAL",
            title: "Agent talks to agent",
            body: "Your TARS handshake-signs a deal with a peer's agent, settles in $MEEET escrow.",
            color: "#06B6D4",
          },
        ].map((c, i) => (
          <div
            key={i}
            className="relative overflow-hidden rounded-[12px] border border-line bg-bg-1/60 p-5"
          >
            <div
              aria-hidden
              className="absolute inset-x-0 top-0 h-px"
              style={{ background: c.color, opacity: 0.6 }}
            />
            <div
              className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
              style={{ color: c.color }}
            >
              {c.tag}
            </div>
            <h3 className="mt-2 font-display text-[18px] leading-[1.25] text-ink">
              {c.title}
            </h3>
            <p className="mt-2 text-[13px] leading-[1.55] text-ink-2">{c.body}</p>
          </div>
        ))}
      </div>
    ),
  },

  // 5. Architecture
  {
    num: "04",
    tag: "ARCHITECTURE",
    title: <>One spine. Many devices.</>,
    body: (
      <div className="grid gap-8 md:grid-cols-[1.2fr_1fr] md:gap-12">
        <div className="rounded-[12px] border border-line bg-bg-1/40 p-6 font-mono text-[11px] leading-[1.7] text-ink-2">
          <pre className="whitespace-pre">{ARCH_DIAGRAM}</pre>
        </div>
        <div>
          <Bullets
            items={[
              "Master keyring lives in macOS Keychain or Windows DPAPI.",
              "meeet.world stores ciphertext only — never plaintext.",
              "L5 sync envelope: XChaCha20-Poly1305 + X25519, contract 1.1.0.",
              "Mobile clients are thin: thin-client decryption, no backend on phone.",
              "Recovery seed (24-word BIP-39) shown once on first install.",
            ]}
          />
        </div>
      </div>
    ),
  },

  // 6. Domain packs
  {
    num: "05",
    tag: "DOMAIN PACKS",
    title: (
      <>
        Same core. <span className="text-ink-2">Six crafts.</span>
      </>
    ),
    body: (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {[
          { name: "Founder / CEO", body: "Daily brief from KPI + deals + calendar.", color: "#6366F1" },
          { name: "Trader",        body: "Markets, signals, risk across exchanges.",  color: "#8B5CF6" },
          { name: "Researcher",    body: "arXiv-aware. Citation-graph across projects.", color: "#06B6D4" },
          { name: "Marketer",      body: "Outreach drafts in your voice. Engagement.",  color: "#A78BFA" },
          { name: "Engineer",      body: "Repos indexed, PR queue, code RAG.",         color: "#34D399" },
          { name: "Operator",      body: "Generalist — full cockpit, all packs.",     color: "#F59E0B" },
        ].map((r, i) => (
          <div key={i} className="rounded-[10px] border border-line bg-bg-1/60 p-4">
            <div
              className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
              style={{ color: r.color }}
            >
              {r.name}
            </div>
            <p className="mt-2 text-[12.5px] leading-[1.55] text-ink-2">{r.body}</p>
          </div>
        ))}
        <div
          className="rounded-[10px] border-2 border-dashed border-line bg-bg-1/30 p-4 md:col-span-3"
          style={{ borderColor: "rgba(99,102,241,0.45)" }}
        >
          <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-accent">
            CUSTOM ROLE · AI Clone trained on you
          </div>
          <p className="mt-2 max-w-[64ch] text-[12.5px] leading-[1.55] text-ink-2">
            Describe your work in 200-500 chars. TARS synthesises a system
            prompt overlay. After 50 interactions, the AI Clone matches your
            tone and rhythm — locally.
          </p>
        </div>
      </div>
    ),
  },

  // 7. $MEEET economy
  {
    num: "06",
    tag: "$MEEET ECONOMY",
    title: (
      <>
        Earn while your agent works.
      </>
    ),
    body: (
      <div className="grid gap-7 md:grid-cols-[1fr_1fr]">
        <div>
          <Bullets
            items={[
              "Every signed receipt feeds the reputation graph.",
              "Weekly $MEEET drops proportional to graph weight.",
              "T2T deals settle in $MEEET escrow off-chain, anchored to Solana memo.",
              "Pay subscriptions in $MEEET or USD — same price, same tier.",
              "Lifetime tier: 1,000 $MEEET allocated at signup.",
            ]}
          />
        </div>
        <div>
          <h3 className="mb-4 font-display text-[15px] tracking-[0.02em] text-ink-2">
            Loop
          </h3>
          <ol className="grid gap-2.5 font-mono-tech text-[12px] uppercase tracking-[1.6px] text-ink-2">
            {[
              "1. Agent runs an action → signed receipt",
              "2. Receipt → reputation graph (weighted)",
              "3. meeet.world drops $MEEET weekly",
              "4. Operator spends $MEEET (sub, T2T, marketplace)",
              "5. Marketplace authors earn → new receipts",
            ].map((s, i) => (
              <li
                key={i}
                className="grid grid-cols-[16px_1fr] items-baseline gap-3 rounded-md border border-line bg-bg-1/60 p-3"
              >
                <span className="text-accent">▸</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    ),
  },

  // 8. Security
  {
    num: "07",
    tag: "SECURITY",
    title: <>Local-first by default. Cloud only when you say so.</>,
    body: (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {[
          { Icon: Lock,         label: "Local-first",      hint: "~/.tars/, never leaves" },
          { Icon: ShieldCheck,  label: "Signed receipts",  hint: "Ed25519 hash chain" },
          { Icon: GitBranch,    label: "Open source",      hint: "MIT, on GitHub" },
          { Icon: Cpu,          label: "Sandbox-exec",     hint: "Mac actions whitelisted" },
          { Icon: Eye,          label: "Auditable",        hint: "Solana memo anchor" },
          { Icon: Zap,          label: "Edge LLM",         hint: "Ollama out of the box" },
        ].map((c, i) => {
          const Icon = c.Icon;
          return (
            <div
              key={i}
              className="rounded-[10px] border border-line bg-bg-1/60 p-4"
            >
              <Icon size={18} strokeWidth={1.6} className="text-accent" />
              <div className="mt-2.5 font-display text-[13px] tracking-[0.02em] text-ink">
                {c.label}
              </div>
              <div className="mt-1 font-mono-tech text-[9.5px] uppercase tracking-[2px] text-ink-3">
                {c.hint}
              </div>
            </div>
          );
        })}
      </div>
    ),
  },

  // 9. Pricing
  {
    num: "08",
    tag: "PRICING",
    title: <>Pay for cloud, not for thinking.</>,
    body: (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <PriceCard
          name="00 · Free"
          price="$0"
          sub="MIT · self-hosted"
          color="#06B6D4"
          bullets={[
            "Single device, BYO LLM key",
            "Mac Operator + memory ledger",
            "All 4 packs",
            "Single-voice council",
          ]}
        />
        <PriceCard
          name="01 · Pro"
          price="$19/mo"
          sub="or BYO $9/mo"
          color="#6366F1"
          recommended
          bullets={[
            "$10 cloud LLM budget",
            "Two-voice council · 100/d",
            "T2T 50 deals/mo + AI Clone",
            "$MEEET earn",
          ]}
        />
        <PriceCard
          name="02 · Business"
          price="$79/seat"
          sub="per month"
          color="#8B5CF6"
          bullets={[
            "$40/seat cloud budget pooled",
            "Unlimited T2T + council",
            "Shared sessions + SSO + RBAC",
            "Skill SDK + private market",
          ]}
        />
        <PriceCard
          name="03 · Lifetime"
          price="$299"
          sub="once"
          color="#A78BFA"
          bullets={[
            "All Pro features forever",
            "1,000 $MEEET at signup",
            "Founders' edition badge",
            "Reserved T2T handle",
          ]}
        />
      </div>
    ),
  },

  // 10. Traction / roadmap
  {
    num: "09",
    tag: "TRACTION",
    title: <>Phase L shipped. Phase M in flight.</>,
    body: (
      <div className="grid gap-8 md:grid-cols-2">
        <div>
          <h3 className="mb-3 font-display text-[14px] tracking-[0.02em] text-ink-2">
            Shipped (Phase L)
          </h3>
          <Bullets
            items={[
              "L1 — conversation layer + streaming SSE",
              "L2 — attachments + RAG with citations",
              "L4.1 — six TTS voice personas + mic dictation",
              "L8 — FTS5 cross-thread search + ⌘K palette",
              "L9 — desktop shell scaffolded; downloads manifest live",
              "L5 — pairing endpoints + real X25519 + recovery seed",
            ]}
          />
        </div>
        <div>
          <h3 className="mb-3 font-display text-[14px] tracking-[0.02em] text-ink-2">
            In flight (Phase M)
          </h3>
          <Bullets
            items={[
              "Tier entitlements + cloud-budget cap (P5)",
              "MLM → Entrepreneur rename (P6, frontend done)",
              "Role selection + custom learnable role (P7, UI done)",
              "Machine vision via L2 attachment routing (P8)",
              "tars.meeet.world subdomain (spec for brother delivered)",
              "Pitch deck + legal docs (this deck)",
            ]}
          />
        </div>
      </div>
    ),
  },

  // 11. Team / handoff
  {
    num: "10",
    tag: "TEAM · HANDOFF",
    title: <>Two agents. One product.</>,
    body: (
      <div className="grid gap-6 md:grid-cols-2 md:gap-10">
        <div className="rounded-[12px] border border-line bg-bg-1/60 p-6">
          <div
            className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
            style={{ color: "#6366F1" }}
          >
            CURSOR · functional
          </div>
          <h3 className="mt-2 font-display text-[18px] leading-[1.3] text-ink">
            Backend, contracts, Phase L roadmap.
          </h3>
          <p className="mt-3 text-[13px] leading-[1.6] text-ink-2">
            Owns Python core, MCP, council orchestrator, policy gate,
            playbook runner, vault, real adapters, the whole functional
            spine. Pins contracts in `docs/contracts/`. 270+ pytest tests
            green.
          </p>
        </div>
        <div className="rounded-[12px] border border-line bg-bg-1/60 p-6">
          <div
            className="font-mono-tech text-[10px] uppercase tracking-[2.4px]"
            style={{ color: "#06B6D4" }}
          >
            CLAUDE · design
          </div>
          <h3 className="mt-2 font-display text-[18px] leading-[1.3] text-ink">
            Marketing, docs, brand, cockpit polish.
          </h3>
          <p className="mt-3 text-[13px] leading-[1.6] text-ink-2">
            Owns the v3 marketing surface, MASTER design system, FAQ /
            ToS / Privacy / Security docs, pitch, meeet.world brand
            integration, all UI polish on cockpit chrome. Coordinates
            with Cursor via `docs/AGENT_HANDOFF.md`.
          </p>
        </div>
        <div className="rounded-[12px] border border-line bg-bg-1/60 p-6 md:col-span-2">
          <div className="font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-2">
            BROTHER · meeet.world infra
          </div>
          <p className="mt-2 max-w-[72ch] text-[13px] leading-[1.6] text-ink-2">
            Stands up tars.meeet.world subdomain with end-to-end logging,
            runs the encrypted ingest relay, manages the wallet + magic-
            link auth + $MEEET marketplace. Spec delivered as
            `docs/contracts/TARS_SUBDOMAIN.md`.
          </p>
        </div>
      </div>
    ),
  },

  // 12. Ask / contact
  {
    num: "11",
    tag: "ASK",
    title: (
      <>
        Where we go from here.
      </>
    ),
    body: (
      <div className="grid gap-8 md:grid-cols-[1.2fr_1fr] md:gap-12">
        <div>
          <Bullets
            items={[
              "Investors — pre-seed open. Lifetime tier first 1,000 buyers covers runway.",
              "Operators — install today, MIT free tier, no commitment.",
              "Builders — skill SDK shipping in v9.2; 70/30 revenue share.",
              "Ecosystem — meeet.world account is the spine; we'd love a partnership ping.",
            ]}
          />
        </div>
        <div className="grid gap-3 self-end font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink-2">
          <a href="https://meeet.world" className="inline-flex items-center justify-between gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 hover:text-ink">
            meeet.world <ArrowRight size={12} strokeWidth={1.8} />
          </a>
          <a href="https://github.com/meeet-world/tars" className="inline-flex items-center justify-between gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 hover:text-ink">
            github.com/meeet-world/tars <ArrowRight size={12} strokeWidth={1.8} />
          </a>
          <a href="https://discord.gg/meeet" className="inline-flex items-center justify-between gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 hover:text-ink">
            discord.gg/meeet <ArrowRight size={12} strokeWidth={1.8} />
          </a>
          <a href="mailto:hello@meeet.world" className="inline-flex items-center justify-between gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 hover:text-ink">
            hello@meeet.world <ArrowRight size={12} strokeWidth={1.8} />
          </a>
        </div>
      </div>
    ),
  },
];

export default SLIDES;
