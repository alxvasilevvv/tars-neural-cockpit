import { motion } from "framer-motion";
import { Lock, FileSignature, GitBranch, Cpu, Eye, Zap } from "lucide-react";
import { useT, type TKey } from "@/lib/i18n";

/**
 * TrustStrip — six trust badges on a single horizontal hairline strip.
 *
 * Visible right after MeetTars. Closes the trust gap that v3 lacked
 * (no local-first / open-source / signed-receipts / sandboxed signal).
 */

interface Badge {
  Icon: typeof Lock;
  /** Translation keys; resolved at render via useT(). */
  labelKey: TKey;
  detailKey: TKey;
}

const BADGES: Badge[] = [
  { Icon: Lock,           labelKey: "trust.local.label",       detailKey: "trust.local.detail" },
  { Icon: FileSignature,  labelKey: "trust.signed.label",      detailKey: "trust.signed.detail" },
  { Icon: GitBranch,      labelKey: "trust.opensource.label",  detailKey: "trust.opensource.detail" },
  { Icon: Cpu,            labelKey: "trust.sandboxed.label",   detailKey: "trust.sandboxed.detail" },
  { Icon: Eye,            labelKey: "trust.auditable.label",   detailKey: "trust.auditable.detail" },
  { Icon: Zap,            labelKey: "trust.edge.label",        detailKey: "trust.edge.detail" },
];

export function TrustStrip() {
  const t = useT();
  return (
    <section className="relative z-20 mx-auto max-w-[1280px] px-6 pb-16 pt-8 md:px-12 md:pb-20">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="rounded-[14px] border border-line bg-bg-1/60 backdrop-blur-sm"
      >
        {/* Top hairline accent — meeet brand triad gradient */}
        <div
          aria-hidden
          className="h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        <ul className="grid grid-cols-2 divide-line sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
          {BADGES.map((b, i) => (
            <motion.li
              key={b.labelKey}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 + i * 0.05 }}
              className="flex items-start gap-3 px-5 py-5"
            >
              <span
                className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-md"
                style={{
                  background: "var(--color-meeet-indigo-deep)",
                  color: "var(--color-meeet-indigo)",
                  boxShadow: "inset 0 0 0 1px var(--color-meeet-indigo-soft)",
                }}
              >
                <b.Icon size={14} strokeWidth={1.8} />
              </span>
              <div className="min-w-0">
                <div className="font-mono-tech text-[10.5px] uppercase tracking-[1.6px] text-ink">
                  {t(b.labelKey)}
                </div>
                <div className="mt-1 text-[12px] leading-[1.45] text-ink-2">
                  {t(b.detailKey)}
                </div>
              </div>
            </motion.li>
          ))}
        </ul>
      </motion.div>
    </section>
  );
}
