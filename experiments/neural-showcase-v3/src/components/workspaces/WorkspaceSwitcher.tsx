import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

/**
 * <WorkspaceSwitcher /> — top-nav dropdown to switch the current
 * workspace context (Wave 110 — record-only).
 *
 * In v9.1.0 single-tenant mode the dropdown:
 *
 * - Always shows "Personal" + any user-created workspaces.
 * - Persists the selected workspace id in localStorage as
 *   ``tars.workspace.current``.
 * - Installs a global ``fetch`` interceptor that adds the
 *   ``X-Workspace-Id`` header to every same-origin request — but
 *   the backend does NOT scope queries on it yet (Wave 9.3 will).
 *
 * Hidden when only the default "personal" workspace exists, since a
 * one-row dropdown is just visual noise.
 */
const STORAGE_KEY = "tars.workspace.current";
const WORKSPACE_HEADER = "X-Workspace-Id";

interface WorkspaceLite {
  id: string;
  slug: string;
  name: string;
}

let interceptorInstalled = false;
function installFetchInterceptor() {
  if (interceptorInstalled || typeof window === "undefined") return;
  if (!window.fetch) return;
  const original = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    let url: string;
    if (typeof input === "string") {
      url = input;
    } else if (input instanceof URL) {
      url = input.toString();
    } else {
      url = (input as Request).url;
    }
    // Same-origin only — never leak the workspace id to third parties.
    let isSameOrigin = true;
    try {
      const u = new URL(url, window.location.origin);
      isSameOrigin = u.origin === window.location.origin;
    } catch {
      isSameOrigin = url.startsWith("/");
    }
    if (!isSameOrigin) {
      return original(input, init);
    }
    let workspaceId = "personal";
    try {
      workspaceId = window.localStorage.getItem(STORAGE_KEY) || "personal";
    } catch {
      /* no localStorage — fall through */
    }
    const headers = new Headers(init?.headers || (input as Request)?.headers);
    if (!headers.has(WORKSPACE_HEADER)) {
      headers.set(WORKSPACE_HEADER, workspaceId);
    }
    return original(input, { ...(init || {}), headers });
  };
  interceptorInstalled = true;
}

export function WorkspaceSwitcher({
  workspaces,
}: {
  workspaces: WorkspaceLite[];
}) {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState<string>("personal");
  const ref = useRef<HTMLDivElement>(null);

  // Install interceptor once on mount.
  useEffect(() => {
    installFetchInterceptor();
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setCurrent(stored);
    } catch {
      /* noop */
    }
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  if (workspaces.length < 2) return null;

  const currentWs =
    workspaces.find((w) => w.id === current) ?? workspaces[0];

  function pick(id: string) {
    setCurrent(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* noop */
    }
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-md border border-line/60 bg-bg-1/40 px-2 py-1 font-mono-tech text-[10.5px] uppercase tracking-[1.5px] text-ink-2 hover:border-[color:var(--brand-indigo)]/60"
      >
        ws · {currentWs.slug}
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 z-50 mt-1.5 min-w-[180px] overflow-hidden rounded-md border border-line bg-bg-1 shadow-xl"
          >
            {workspaces.map((w) => (
              <li key={w.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={w.id === current}
                  onClick={() => pick(w.id)}
                  className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-[12px] transition-colors hover:bg-bg-2/60 ${
                    w.id === current ? "text-ink" : "text-ink-2"
                  }`}
                >
                  <span>{w.name}</span>
                  <span className="font-mono-tech text-[10px] text-ink-3">
                    {w.slug}
                  </span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

export default WorkspaceSwitcher;
