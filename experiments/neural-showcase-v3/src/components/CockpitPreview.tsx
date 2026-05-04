import { motion } from "framer-motion";
import { ArrowUpRight, Zap, Activity, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import type { TKey } from "@/lib/i18n";
import { useT } from "@/lib/i18n";

const COCKPIT_PHASE_IDS = ["routing", "tool", "drafting", "done"] as const;

/**
 * CockpitPreview — visual mockup of the operator runtime.
 *
 * Shows the user what they'll see at /cockpit after install. Three call-out
 * annotations point at the briefing card, the watch-me-work phase bar, and
 * the awareness stream sidebar.
 *
 * Pure CSS / SVG mockup — no live data, but visually accurate to the real
 * cockpit at /cockpit (which Cursor's Cockpit.tsx renders for real).
 */

export function CockpitPreview() {
  const tt = useT();

  const navRows = [
    { slug: "traders" as const, n: 12, color: "#6366F1", active: true },
    { slug: "business" as const, n: 8, color: "#8B5CF6" },
    { slug: "entrepreneur" as const, n: 6, color: "#06B6D4" },
    { slug: "science" as const, n: 9, color: "#A78BFA" },
  ];

  const phaseState: { done: boolean; active: boolean }[] = [
    { done: true, active: false },
    { done: true, active: false },
    { done: false, active: true },
    { done: false, active: false },
  ];

  const tiles = [
    { icon: "▣", labelKey: "cockpitPreview.tile1.label" as TKey, detailKey: "cockpitPreview.tile1.detail" as TKey },
    { icon: "◇", labelKey: "cockpitPreview.tile2.label" as TKey, detailKey: "cockpitPreview.tile2.detail" as TKey },
    { icon: "◆", labelKey: "cockpitPreview.tile3.label" as TKey, detailKey: "cockpitPreview.tile3.detail" as TKey },
    { icon: "═", labelKey: "cockpitPreview.tile4.label" as TKey, detailKey: "cockpitPreview.tile4.detail" as TKey },
  ];

  const awarenessRows = [
    { Icon: Zap, tagKey: "cockpitPreview.row1.tag" as TKey, bodyKey: "cockpitPreview.row1.body" as TKey },
    { Icon: Activity, tagKey: "cockpitPreview.row2.tag" as TKey, bodyKey: "cockpitPreview.row2.body" as TKey },
    { Icon: FileText, tagKey: "cockpitPreview.row3.tag" as TKey, bodyKey: "cockpitPreview.row3.body" as TKey },
    { Icon: Zap, tagKey: "cockpitPreview.row4.tag" as TKey, bodyKey: "cockpitPreview.row4.body" as TKey },
    { Icon: Activity, tagKey: "cockpitPreview.row5.tag" as TKey, bodyKey: "cockpitPreview.row5.body" as TKey },
  ];

  return (
    <section
      id="cockpit-preview"
      className="relative z-20 mx-auto max-w-[1280px] overflow-hidden px-6 py-24 md:px-12 md:py-32"
    >
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        className="mb-12 flex flex-col items-start gap-3 md:flex-row md:items-end md:justify-between"
      >
        <div>
          <div className="mb-3 inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-2">
            <span
              className="h-1 w-1 rounded-full"
              style={{
                background: "var(--color-meeet-cyan)",
                boxShadow: "0 0 8px var(--color-meeet-cyan-soft)",
              }}
            />
            {tt("cockpitPreview.eyebrow")}
          </div>
          <h2
            className="font-display font-medium leading-[0.94] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2rem, 4.4vw, 3.6rem)" }}
          >
            {tt("cockpitLive.title.prefix")}{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, #6366F1 0%, #8B5CF6 50%, #06B6D4 100%)",
              }}
            >
              {tt("cockpitLive.title.gradient")}
            </span>
            .
          </h2>
        </div>
        <Link
          to="/cockpit"
          className="group inline-flex items-center gap-2 rounded-md border border-line bg-white/[0.02] px-4 py-2.5 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-ink transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
        >
          {tt("cockpitLive.cta.openReal")}
          <ArrowUpRight
            size={14}
            strokeWidth={1.8}
            className="transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          />
        </Link>
      </motion.div>

      {/* Cockpit chrome mockup */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 1, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
        className="relative overflow-hidden rounded-[16px] border border-line-strong bg-bg-1/80 shadow-[0_32px_120px_-30px_rgba(99,102,241,0.45)] backdrop-blur-sm"
      >
        {/* Top hairline accent */}
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        {/* Window header */}
        <div className="flex items-center justify-between border-b border-line bg-bg-0/60 px-5 py-3">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" />
            <span className="ml-3 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
              {tt("cockpitPreview.chromeTitle")}
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2">
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5"
              style={{
                background: "rgba(52,211,153,0.12)",
                color: "var(--color-success)",
                boxShadow: "inset 0 0 0 1px rgba(52,211,153,0.4)",
              }}
            >
              <span
                className="h-1 w-1 rounded-full bg-success"
                style={{
                  boxShadow: "0 0 6px rgba(52,211,153,0.7)",
                  animation: "pulseDot 2s ease-in-out infinite",
                }}
              />
              {tt("cockpitPreview.live")}
            </span>
          </div>
        </div>

        {/* Cockpit body — 3 columns: nav + briefing + awareness */}
        <div className="grid grid-cols-1 gap-px bg-line lg:grid-cols-[200px_1fr_280px]">
          {/* Left — domain nav */}
          <div className="bg-bg-1/80 px-5 py-6">
            <div className="mb-4 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
              {tt("cockpitPreview.domainPacks")}
            </div>
            <ul className="space-y-1.5">
              {navRows.map((d) => (
                <li
                  key={d.slug}
                  className="flex items-center gap-2.5 rounded-md px-2.5 py-2 font-mono-tech text-[11px]"
                  style={{
                    background: d.active ? `${d.color}1F` : "transparent",
                    boxShadow: d.active ? `inset 0 0 0 1px ${d.color}3F` : "none",
                  }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      background: d.color,
                      boxShadow: d.active ? `0 0 6px ${d.color}` : "none",
                    }}
                  />
                  <span className={d.active ? "text-ink" : "text-ink-2"}>
                    {tt(`domains.${d.slug}.name` as TKey)}
                  </span>
                  <span className="ml-auto text-[9.5px] text-ink-3">
                    {tt("cockpitPreview.actions", { n: d.n })}
                  </span>
                </li>
              ))}
            </ul>

            <div className="mt-7 mb-3 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
              {tt("cockpitPreview.connectors")}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["GitHub", "Slack", "Calendar", "iMessage", "Mac"].map((c) => (
                <span
                  key={c}
                  className="rounded-md border border-line bg-bg-0/40 px-2 py-0.5 font-mono-tech text-[9.5px] uppercase tracking-[1.4px] text-ink-2"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* Centre — briefing + chat */}
          <div className="relative bg-bg-1/40 px-6 py-6">
            {/* Watch-Me-Work phase bar */}
            <div className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-line bg-bg-0/50 px-3 py-1 font-mono-tech text-[9.5px] uppercase tracking-[2px]">
              {COCKPIT_PHASE_IDS.map((pid, i) => {
                const p = phaseState[i]!;
                const label = tt(`cockpitPreview.phase.${pid}` as TKey);
                return (
                  <span key={pid} className="flex items-center gap-1.5">
                    {i > 0 && <span className="text-ink-3">·</span>}
                    <span
                      className="h-1 w-1 rounded-full"
                      style={{
                        background: p.done
                          ? "var(--color-success)"
                          : p.active
                            ? "var(--color-meeet-violet)"
                            : "var(--color-ink-3)",
                        boxShadow: p.active
                          ? "0 0 6px var(--color-meeet-violet-soft)"
                          : "none",
                        animation: p.active ? "pulseDot 1.4s ease-in-out infinite" : "none",
                      }}
                    />
                    <span
                      className={
                        p.done
                          ? "text-success"
                          : p.active
                            ? "text-ink"
                            : "text-ink-3"
                      }
                    >
                      {label}
                    </span>
                  </span>
                );
              })}
            </div>

            {/* Daily briefing card */}
            <div className="mb-5 rounded-[12px] border border-line bg-bg-0/60 p-5 backdrop-blur-sm">
              <div className="mb-1 font-display text-[18px] font-medium leading-tight text-ink">
                {tt("cockpitPreview.greeting")}
              </div>
              <div className="font-mono-tech text-[11px] tracking-[0.4px] text-ink-2">
                {tt("cockpitPreview.briefMeta")}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                {tiles.map((it) => (
                  <div
                    key={it.labelKey}
                    className="rounded-md border border-line bg-bg-1/60 px-3 py-2.5"
                  >
                    <div className="mb-0.5 flex items-center gap-1.5">
                      <span
                        className="font-mono-tech text-[12px] font-bold"
                        style={{ color: "var(--color-meeet-violet)" }}
                      >
                        {it.icon}
                      </span>
                      <span className="font-mono-tech text-[10.5px] font-semibold text-ink">
                        {tt(it.labelKey)}
                      </span>
                    </div>
                    <div className="font-mono-tech text-[9.5px] leading-[1.45] text-ink-2">
                      {tt(it.detailKey)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Chat input mock */}
            <div
              className="flex items-center gap-2 rounded-md border bg-bg-0/60 px-4 py-3 font-mono-tech text-[12.5px] backdrop-blur-sm"
              style={{ borderColor: "rgba(99,102,241,0.32)" }}
            >
              <span style={{ color: "var(--color-meeet-indigo)" }}>$</span>
              <span className="flex-1 truncate text-ink-2">
                {tt("cockpitPreview.chatPlaceholder")}
              </span>
              <span
                aria-hidden
                className="h-3.5 w-[2px] bg-ink"
                style={{ animation: "pulseDot 1.05s steps(2) infinite" }}
              />
            </div>
          </div>

          {/* Right — awareness stream */}
          <div className="bg-bg-1/60 px-4 py-5">
            <div className="mb-4 flex items-center justify-between">
              <div className="font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
                {tt("cockpitPreview.awarenessLabel")}
              </div>
              <span
                className="rounded-full px-2 py-0.5 font-mono-tech text-[9px] uppercase tracking-[1.4px]"
                style={{
                  background: "var(--color-meeet-cyan-deep)",
                  color: "var(--color-meeet-cyan)",
                }}
              >
                {tt("cockpitPreview.newBadge")}
              </span>
            </div>

            <ul className="space-y-2">
              {awarenessRows.map((o, i) => (
                <li
                  key={i}
                  className="rounded-md border border-line bg-bg-0/40 px-3 py-2.5"
                >
                  <div className="mb-1 flex items-center gap-1.5">
                    <o.Icon
                      size={11}
                      strokeWidth={1.8}
                      style={{ color: "var(--color-meeet-cyan)" }}
                    />
                    <span className="font-mono-tech text-[9.5px] uppercase tracking-[1.4px] text-ink-3">
                      {tt(o.tagKey)}
                    </span>
                  </div>
                  <div className="font-mono-tech text-[10.5px] leading-[1.4] text-ink-2">
                    {tt(o.bodyKey)}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
