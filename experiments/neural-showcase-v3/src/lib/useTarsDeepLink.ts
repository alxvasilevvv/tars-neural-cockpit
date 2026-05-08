import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

/**
 * useTarsDeepLink — listens for `tars://…` URLs delivered by the
 * Tauri shell (Wave 59 desktop polish) and routes them into React
 * Router. The Rust side (`desktop/src-tauri/src/main.rs`) emits the
 * `tars://deeplink` event with a `string[]` payload (some platforms
 * batch URLs); we route the FIRST URL and ignore the rest — secondary
 * deep links can re-fire on the next user action.
 *
 * Supported routes (extend as needed):
 *
 *   tars://onboarding             → /onboarding
 *   tars://onboarding?role=founder→ /onboarding?role=founder
 *   tars://thread/abc123          → /cockpit?thread=abc123
 *   tars://cockpit                → /cockpit
 *   tars://settings               → /cockpit?panel=settings (TODO when route exists)
 *   tars://login                  → /onboarding (magic-link landing)
 *
 * Anything else is no-op'd with a console.warn so we can spot drift
 * in the field. Browser builds (Vite dev / production web) skip the
 * listener entirely — `window.__TAURI__` is undefined there.
 *
 * Mount once, in App's <AppShell />.
 */
export function useTarsDeepLink() {
  const navigate = useNavigate();

  useEffect(() => {
    // Browser-only build (no Tauri runtime) — skip the listener
    // entirely so we don't try to import @tauri-apps/api in a Vite
    // chunk that will never need it.
    const isTauri =
      typeof window !== "undefined" &&
      typeof (window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ !==
        "undefined";
    if (!isTauri) return;

    let unlisten: (() => void) | null = null;
    let mounted = true;

    (async () => {
      try {
        const { listen } = await import(
          /* @vite-ignore */ "@tauri-apps/api/event"
        );
        const off = await listen<string[]>("tars://deeplink", (event) => {
          const url = (event.payload || [])[0];
          if (!url) return;
          const path = parseTarsUrl(url);
          if (path) {
            navigate(path, { replace: false });
          } else {
            // Unknown verb — log so we can spot it in the operator
            // console without crashing the route.
            console.warn("[tars] unknown deep-link:", url);
          }
        });
        if (mounted) {
          unlisten = off;
        } else {
          off();
        }
      } catch (err) {
        // @tauri-apps/api may be missing in some build configurations;
        // not a hard error.
        console.warn("[tars] deep-link listener init failed:", err);
      }
    })();

    return () => {
      mounted = false;
      if (unlisten) unlisten();
    };
  }, [navigate]);
}

/**
 * Translate `tars://verb[/path][?query]` into a React Router path.
 * Returns `null` for unknown verbs.
 */
export function parseTarsUrl(raw: string): string | null {
  // URL constructor handles the scheme + path + search parsing for us.
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "tars:") return null;

  // `tars://onboarding` parses with hostname="onboarding" and pathname="/".
  // `tars://thread/abc123` parses with hostname="thread" and pathname="/abc123".
  const verb = (url.hostname || "").toLowerCase();
  const subpath = url.pathname.replace(/^\/+/, "");
  const search = url.search; // includes leading '?' or empty

  switch (verb) {
    case "onboarding":
    case "login":
      // login is an alias for the magic-link landing page.
      return `/onboarding${search}`;
    case "cockpit":
      return `/cockpit${search}`;
    case "thread": {
      if (!subpath) return "/cockpit";
      const threadId = encodeURIComponent(subpath);
      const sep = search ? "&" : "?";
      return `/cockpit${search}${sep}thread=${threadId}`;
    }
    case "settings":
      // Wave 62: standalone /settings page with About + Updater +
      // Keyboard reference. (Older Wave 59 routed via /cockpit?panel=
      // before the page existed.)
      return `/settings`;
    default:
      return null;
  }
}
