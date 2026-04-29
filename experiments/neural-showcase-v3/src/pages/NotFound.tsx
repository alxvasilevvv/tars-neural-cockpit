import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, Home, Search, FileQuestion, Stamp } from "lucide-react";
import { motion } from "framer-motion";
import { useDocumentMeta } from "@/lib/meta";
import { BrandHairline } from "@/components/BrandHairline";

/**
 * /404 — proper "not found" page rather than silently falling back to
 * Landing. Renders the requested path so the operator can see what was
 * looked up, plus four "did you mean" deep links to the most-visited
 * pages.
 */
export function NotFound() {
  const loc = useLocation();
  useDocumentMeta({
    title: "404 — route not found",
    description: "The cockpit didn't find that page. Try Home, Install, Cockpit, or Built with TARS.",
  });
  return (
    <div className="relative min-h-[calc(100vh-72px)]">
      <BrandHairline />

      <section className="mx-auto max-w-[760px] px-6 pb-28 pt-20 md:px-12 md:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Eyebrow */}
          <div className="mb-6 flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <FileQuestion size={13} strokeWidth={1.6} className="text-accent" />
            <span style={{ color: "var(--brand-indigo)" }}>404</span>
            <span aria-hidden>·</span>
            <span>route not found</span>
          </div>

          {/* Title */}
          <h1
            className="mb-4 font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "var(--text-display-lg)" }}
          >
            That page{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(95deg, var(--brand-indigo) 0%, var(--brand-violet) 50%, var(--brand-cyan) 100%)",
              }}
            >
              doesn't exist
            </span>
            .
          </h1>

          <p className="mb-7 max-w-[60ch] text-[15px] leading-[1.65] text-ink-2">
            The cockpit looked for{" "}
            <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono text-[0.92em] text-ink">
              {loc.pathname}
            </code>{" "}
            and didn't find it. If you followed an outdated link, ping us in
            Discord — we'll add a redirect.
          </p>

          {/* "Did you mean" links */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DeepLink to="/" Icon={Home} title="Home" body="Hero, packs, pricing, FAQ." />
            <DeepLink to="/install" Icon={ArrowLeft} title="Install" body="One-curl setup, OS-detected." flip />
            <DeepLink to="/cockpit" Icon={Search} title="Cockpit" body="Live operator console." />
            <DeepLink to="/build-with" Icon={Stamp} title="Built with TARS" body="Embed badge for your repo." />
            <DeepLink to="/pitch" Icon={FileQuestion} title="Pitch" body="12-slide investor deck." />
            <DeepLink to="/docs" Icon={FileQuestion} title="Docs" body="Public API reference." />
          </div>

          {/* Bottom strip */}
          <div className="mt-10 grid items-center gap-3 border-t border-line pt-6 font-mono-tech text-[10px] uppercase tracking-[2.4px] text-ink-3 md:grid-cols-[1fr_auto] md:gap-6">
            <span>
              File a redirect at{" "}
              <a
                href="https://github.com/meeet-world/tars/issues"
                className="text-ink-2 transition-colors hover:text-ink"
                target="_blank"
                rel="noopener"
              >
                github
              </a>{" "}
              or {" "}
              <a
                href="https://discord.gg/meeet"
                className="text-ink-2 transition-colors hover:text-ink"
                target="_blank"
                rel="noopener"
              >
                discord
              </a>
              .
            </span>
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-ink transition-colors hover:text-accent"
            >
              <ArrowLeft size={11} strokeWidth={1.8} /> back to home
            </Link>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

function DeepLink({
  to,
  Icon,
  title,
  body,
  flip,
}: {
  to: string;
  Icon: typeof Home;
  title: string;
  body: string;
  flip?: boolean;
}) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-4 rounded-[12px] border border-line bg-bg-1/60 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-line-strong"
    >
      <span
        className="grid h-9 w-9 place-items-center rounded-md text-accent"
        style={{
          background: "color-mix(in srgb, var(--color-accent) 12%, transparent)",
          boxShadow: "inset 0 0 0 1px rgba(99,102,241,0.32)",
          transform: flip ? "scaleX(-1)" : undefined,
        }}
      >
        <Icon size={16} strokeWidth={1.7} />
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-display text-[14px] tracking-[0.02em] text-ink">{title}</div>
        <div className="mt-0.5 truncate font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3">
          {body}
        </div>
      </div>
    </Link>
  );
}
