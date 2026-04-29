import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { sound } from "@/lib/sound";
import { KineticText } from "@/components/KineticText";
import { SparklesCore } from "@/components/ui/sparkles";
import { DownloadStrip } from "@/components/DownloadStrip";
import { MeeetWorldStrip } from "@/components/MeeetWorldStrip";
import { useT } from "@/lib/i18n";

export function Footer() {
  const t = useT();
  return (
    <footer
      id="cockpit"
      className="relative z-20 mt-12 grid grid-cols-1 items-end gap-10 border-t border-line bg-gradient-to-b from-transparent to-bg-0/85 px-8 pb-20 pt-24 md:px-14"
    >
      {/* Decorative tracking line */}
      <div
        aria-hidden
        className="absolute left-0 right-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, var(--color-line-strong) 14%, var(--color-line-hot) 50%, var(--color-line-strong) 86%, transparent)",
        }}
      />

      {/* Massive kinetic CTA */}
      <Link
        to="/cockpit"
        onClick={() => sound.click()}
        className="group block w-full"
      >
        <div className="grid grid-cols-1 items-end gap-6 md:grid-cols-[1fr_auto]">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-[clamp(3rem,12vw,11rem)] font-medium uppercase leading-[0.92] tracking-[0.04em] text-ink"
          >
            <span className="relative inline-block">
              {/* Liquid metal layer underneath */}
              <span
                aria-hidden
                className="absolute inset-0 -z-10 bg-clip-text text-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                style={{
                  backgroundImage:
                    "linear-gradient(118deg, transparent 30%, var(--color-accent) 48%, var(--color-hud) 56%, transparent 70%)",
                  backgroundSize: "240% 100%",
                  backgroundPosition: "left",
                  WebkitBackgroundClip: "text",
                  animation: "tars-shimmer 1.6s ease-in-out infinite",
                }}
              >
                <KineticText text={t("footer.cta")} />
              </span>
              <span className="relative">
                <KineticText text={t("footer.cta")} />
              </span>
            </span>
          </motion.div>

          <motion.span
            whileHover={{ x: 6 }}
            transition={{ type: "spring", stiffness: 240, damping: 22 }}
            className="inline-grid h-16 w-16 place-items-center rounded-full border border-line-strong text-ink-2 transition-all duration-200 group-hover:border-accent group-hover:bg-accent-deep group-hover:text-accent"
          >
            <ArrowRight size={20} strokeWidth={1.6} />
          </motion.span>
        </div>
      </Link>

      {/* Sparkles "magic line" — Aceternity Default signature with
          meeet.world brand triad. Indigo → violet → cyan horizon. */}
      <div className="relative -mb-2 mt-6 h-20 w-full">
        {/* Brand horizon line — indigo → violet → cyan */}
        <div
          aria-hidden
          className="absolute left-1/2 top-1/2 h-px w-3/4 -translate-x-1/2 -translate-y-1/2"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #6366F1 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
            boxShadow:
              "0 0 12px rgba(99,102,241,0.55), 0 0 24px rgba(139,92,246,0.32)",
          }}
        />
        {/* Sparkles concentrated around the line — violet */}
        <div className="absolute inset-0">
          <SparklesCore
            id="footer-sparkles"
            background="transparent"
            minSize={0.5}
            maxSize={1.4}
            particleDensity={120}
            particleColor="#8B5CF6"
            speed={1.4}
            className="h-full w-full"
          />
        </div>
        {/* Side fades — bring particles to concentrate behind the line */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 50% 80% at 50% 50%, transparent 0%, rgba(0,0,0,0.55) 70%, rgba(0,0,0,0.95) 100%)",
          }}
        />
      </div>

      {/* Conversion row — DownloadStrip footer + meeet front-door */}
      <div className="grid grid-cols-1 items-center gap-4 border-t border-line pt-10 md:grid-cols-[1fr_auto] md:gap-8">
        <DownloadStrip variant="footer" />
        <MeeetWorldStrip variant="footer" />
      </div>

      {/* Link grid — 4 columns: Product · Resources · Company · Connect */}
      <div className="grid grid-cols-2 gap-10 border-t border-line pt-12 md:grid-cols-4">
        <FooterColumn
          title={t("footer.col.product")}
          links={[
            { label: "Open cockpit",  href: "/cockpit" },
            { label: "Domain packs",  href: "#domains" },
            { label: "Meet TARS",     href: "#meet-tars" },
            { label: "Roadmap",       href: "/roadmap" },
            { label: "Changelog",     href: "/changelog" },
          ]}
        />
        <FooterColumn
          title={t("footer.col.resources")}
          links={[
            { label: "Documentation", href: "https://docs.meeet.world", external: true },
            { label: "Pitch deck",    href: "/pitch" },
            { label: "Install guide", href: "/install" },
            { label: "API reference", href: "/docs" },
            { label: "Skill SDK",      href: "https://docs.meeet.world/skill-sdk", external: true },
            { label: "Built with TARS", href: "/build-with" },
          ]}
        />
        <FooterColumn
          title={t("footer.col.company")}
          links={[
            { label: "meeet.world",   href: "https://meeet.world", external: true },
            { label: "Privacy",       href: "/privacy" },
            { label: "Terms",         href: "/terms" },
            { label: "Security",      href: "/security" },
            { label: "Status",        href: "/status" },
            { label: "Press kit",     href: "/press" },
          ]}
        />
        <FooterColumn
          title={t("footer.col.connect")}
          links={[
            { label: "Discord",       href: "https://discord.gg/meeet", external: true },
            { label: "GitHub",        href: "https://github.com/meeet-world/tars", external: true },
            { label: "Twitter / X",   href: "https://x.com/meeet_world", external: true },
            { label: "YouTube",       href: "https://youtube.com/@meeet_world", external: true },
            { label: "support@",      href: "mailto:support@meeet.world", external: true },
          ]}
        />
      </div>

      {/* Bottom bar — telemetry + copyright */}
      <div className="mt-12 grid gap-2 border-t border-line pt-6 text-left font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 md:grid-cols-3">
        <span className="flex items-center gap-2">
          <span
            className="h-1 w-1 rounded-full"
            style={{
              background: "var(--color-success)",
              boxShadow: "0 0 6px rgba(52,211,153,0.5)",
              animation: "pulseDot 2.4s ease-in-out infinite",
            }}
          />
          {t("footer.systems")}
        </span>
        <span className="md:text-center">{t("footer.trace")}</span>
        <span className="md:text-right">{t("footer.legal")}</span>
      </div>
    </footer>
  );
}

interface FooterLink {
  label: string;
  href: string;
  external?: boolean;
}

function FooterColumn({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <div>
      <div className="mb-4 font-mono-tech text-[10px] uppercase tracking-[2.6px] text-ink-3">
        {title}
      </div>
      <ul className="space-y-2.5">
        {links.map((l) => (
          <li key={l.label}>
            <a
              href={l.href}
              {...(l.external ? { target: "_blank", rel: "noopener" } : {})}
              className="inline-block cursor-pointer font-mono-tech text-[12px] text-ink-2 transition-colors duration-200 hover:text-ink"
            >
              {l.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
