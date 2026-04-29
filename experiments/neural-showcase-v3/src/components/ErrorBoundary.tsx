import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw, MessageSquare } from "lucide-react";

/**
 * Global ErrorBoundary — catches React render errors anywhere under
 * <main>. Renders a brand-styled fallback rather than a blank screen
 * or React's default "Application error" string. Includes a Reload
 * button and a Discord link so the operator has a way out.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <App content />
 *   </ErrorBoundary>
 *
 * Errors are logged to `console.error` so they show up in DevTools.
 * If we ever add a real telemetry endpoint, this is where the
 * `report()` call goes — currently a no-op so we don't lie about
 * having error reporting.
 */

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  componentStack: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, componentStack: null };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[TARS] React render error", error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? null });
  }

  reset = () => {
    this.setState({ error: null, componentStack: null });
  };

  reload = () => {
    if (typeof window !== "undefined") window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;

    const message = this.state.error.message || String(this.state.error);
    const path = typeof window !== "undefined" ? window.location.pathname : "/";

    return (
      <div className="relative min-h-[100vh] bg-bg-0 px-6 pt-20 md:px-12 md:pt-28">
        {/* Brand-triad hairline */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, #EF4444 30%, #8B5CF6 50%, #06B6D4 70%, transparent 100%)",
          }}
        />

        <div className="mx-auto max-w-[680px]">
          <div className="mb-6 flex items-center gap-3 font-mono-tech text-[11px] uppercase tracking-[3px] text-ink-2">
            <AlertTriangle size={13} strokeWidth={1.6} className="text-alert" />
            <span style={{ color: "#EF4444" }}>500</span>
            <span aria-hidden>·</span>
            <span>render error</span>
          </div>

          <h1
            className="mb-4 font-display font-medium leading-[0.96] tracking-[-0.02em] text-ink"
            style={{ fontSize: "clamp(2.4rem, 5vw, 3.6rem)" }}
          >
            Something went sideways{" "}
            <span style={{ color: "#EF4444" }}>·</span> we caught it.
          </h1>

          <p className="mb-2 max-w-[60ch] text-[14.5px] leading-[1.65] text-ink-2">
            The cockpit hit a render error on{" "}
            <code className="rounded bg-bg-2 px-1.5 py-0.5 font-mono text-[0.92em] text-ink">
              {path}
            </code>
            . Your data is fine — this is a UI-side fault. Reload
            usually fixes it.
          </p>

          <pre
            className="mb-7 mt-5 overflow-x-auto rounded-md border border-line bg-bg-1/70 p-4 font-mono text-[12px] leading-[1.55] text-ink-2"
            aria-label="error message"
          >
            {message}
          </pre>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={this.reload}
              className="group inline-flex items-center gap-2 rounded-md px-5 py-3 font-mono-tech text-[11px] uppercase tracking-[2.4px] text-white transition-all duration-200 hover:-translate-y-0.5"
              style={{
                background: "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
                boxShadow:
                  "0 0 0 1px rgba(99,102,241,0.45), 0 12px 32px -10px rgba(99,102,241,0.55)",
              }}
            >
              <RotateCcw size={13} strokeWidth={1.7} />
              Reload page
            </button>
            <button
              type="button"
              onClick={this.reset}
              className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              Try again
            </button>
            <a
              href="https://discord.gg/meeet"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-2 rounded-md border border-line bg-bg-1/60 px-4 py-3 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              <MessageSquare size={11} strokeWidth={1.7} />
              Report on Discord
            </a>
          </div>

          {this.state.componentStack && (
            <details className="mt-10 rounded-md border border-line bg-bg-1/40 p-4">
              <summary className="cursor-pointer font-mono-tech text-[10px] uppercase tracking-[2.2px] text-ink-3 hover:text-ink-2">
                component stack
              </summary>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-[11px] leading-[1.55] text-ink-3">
                {this.state.componentStack}
              </pre>
            </details>
          )}
        </div>
      </div>
    );
  }
}
