/**
 * TARS marketing-surface service worker.
 *
 * Strategy:
 *   - Pre-cache `/`, `/install`, OG cards, badge SVGs, manifest, favicon
 *     on install — minimal critical bundle so the brand reads even
 *     fully offline.
 *   - For navigation requests: network-first with offline fallback to
 *     the cached `/` document. Crawlers + first paint stay correct.
 *   - For static assets (svg/png/font/css/js): stale-while-revalidate.
 *     Visitors get instant repeat-load; the SW silently refreshes the
 *     cache in the background.
 *   - For the live download manifest (`/api/product/downloads`):
 *     network-first with a 2.5s timeout, fall back to the last
 *     successful response so the Hero CTA still renders OS-tailored
 *     buttons under flaky connectivity.
 *   - Never cache /api/log, /api/waitlist, or any POST. Those are
 *     side-effect endpoints; offline behaviour is handled in-app
 *     (toast/buffer fallbacks already shipped).
 *
 * The cache name is versioned so cutting a release invalidates older
 * blobs. Bump on every visual/content change of the precache set.
 */

// Wave 129 (2026-05-12) — bumped to v9.0.4 to invalidate stale caches
// + add /cowork to the offline precache list. Cowork is the new
// multiplayer agent-session surface (shared sessions, presence, T2T
// handoff). We want the entry page available offline so a user landing
// on /cowork without a network gets the branded fallback rather than
// the generic offline screen.
//
// Wave 115 history kept for reference:
//   v9.0.3 — invalidated stale caches holding broken Workshop bundle
//   (Wave 114 hotfix). Wave 87 renamed og-cresco.svg →
//   og-workshop-enterprise.svg + redirected /workshop/cresco →
//   /workshop/enterprise — old precache list referenced the deleted
//   file and got 404 on install (Promise.allSettled saved it from
//   total failure but stale clients still served broken HTML).
const VERSION = "tars-v9.0.4";
const PRECACHE = `${VERSION}-precache`;
const RUNTIME = `${VERSION}-runtime`;

const PRECACHE_URLS = [
  "/",
  "/install",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/og.svg",
  "/og-build-with.svg",
  "/og-pitch.svg",
  "/og-install.svg",
  "/og-cockpit.svg",
  "/og-workshop.svg",
  // Wave 87 + 112 — Cresco rebranded to Enterprise + 9 new B2B route OGs.
  "/og-workshop-enterprise.svg",
  "/og-dashboard.svg",
  "/og-onboard.svg",
  "/og-reports.svg",
  "/og-marketplace.svg",
  "/og-compliance.svg",
  "/og-inbox.svg",
  "/og-files.svg",
  "/og-workspaces.svg",
  "/og-perf.svg",
  // Wave 129 — Cowork OG card.
  "/og-cowork.svg",
  "/badge/built-with-tars.svg",
  "/badge/built-with-tars-light.svg",
  "/badge/built-with-tars-compact.svg",
  "/badge/built-with-tars-compact-light.svg",
  "/robots.txt",
  "/sitemap.xml",
  // Wave 85 + 87 — workshop surface offline-first. /workshop/cresco
  // removed (Wave 87 redirect to /workshop/enterprise). Wave 88/89 added
  // /workshop/assess + /workshop/cohort — those are facilitator surfaces
  // worth precaching for conference-WiFi resilience.
  "/workshop",
  "/workshop/enterprise",
  "/workshop/roi",
  "/workshop/materials",
  "/workshop/assess",
  "/workshop/cohort",
  // Wave 129 — Cowork landing page offline-ready. The :slug sub-routes
  // aren't precached (dynamic + need backend), but landing reads from
  // cache instantly. The mock fallback in lib/cowork.ts keeps the demo
  // session interactive even with no network.
  "/cowork",
];

// Wave 85 — runtime caching escape hatches.
//
// Embedded video iframes (Loom + YouTube) and the Cal.com office-hours
// widget MUST NOT be cached:
//   - The video bytes themselves are huge.
//   - The hosts already CDN-edge globally.
//   - Caching their HTML breaks Loom's cookie-bound auth check and
//     the Cal.com slot-availability roundtrip.
const VIDEO_HOST_PATTERNS = [
  /(^|\.)loom\.com$/i,
  /(^|\.)youtube\.com$/i,
  /(^|\.)youtu\.be$/i,
  /(^|\.)cal\.com$/i,
];

function isSkippedHost(url) {
  return VIDEO_HOST_PATTERNS.some((re) => re.test(url.hostname));
}

// On install — open the precache and pull every static URL. We use
// `addAll` with `cache: "reload"` so dev iteration doesn't serve a
// stale chrome cache.
self.addEventListener("install", event => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(PRECACHE);
      // Best-effort precache — partial failure shouldn't reject install
      await Promise.allSettled(
        PRECACHE_URLS.map(u =>
          cache
            .add(new Request(u, { cache: "reload" }))
            .catch(() => undefined),
        ),
      );
      await self.skipWaiting();
    })(),
  );
});

// On activate — drop old caches.
self.addEventListener("activate", event => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter(k => k !== PRECACHE && k !== RUNTIME)
          .map(k => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Wave 85 — explicit skip for video / calendar embed origins. Their
  // requests are cross-origin so the next check would already pass
  // through, but we keep this short-circuit at the top so future
  // refactors that flip the cross-origin gate don't accidentally
  // start caching Loom bytes.
  if (isSkippedHost(url)) return;

  // Don't touch cross-origin requests (fonts.googleapis.com etc.)
  if (url.origin !== self.location.origin) return;

  // Side-effect endpoints — pass through, never cache.
  if (
    url.pathname.startsWith("/api/log") ||
    url.pathname.startsWith("/api/waitlist") ||
    url.pathname.startsWith("/api/pairing") ||
    url.pathname.startsWith("/api/wallet")
  ) {
    return;
  }

  // Live download manifest — network-first with 2.5s timeout fallback.
  if (url.pathname === "/api/product/downloads") {
    event.respondWith(networkFirstWithTimeout(req, 2500));
    return;
  }

  // Wave 85 — workshop materials assets (PDFs + SVGs under /assets/).
  // Pure stale-while-revalidate: large, immutable-ish files (decks,
  // handouts, diagrams) where the brand reads instantly from cache
  // and the SW silently picks up new versions in the background.
  if (
    url.pathname.startsWith("/assets/") &&
    /\.(?:pdf|svg)$/i.test(url.pathname)
  ) {
    event.respondWith(staleWhileRevalidate(req));
    return;
  }

  // Navigation — network-first with offline fallback to cached `/`.
  if (req.mode === "navigate") {
    event.respondWith(navigationStrategy(req));
    return;
  }

  // Static assets — stale-while-revalidate.
  if (
    /\.(?:svg|png|jpg|jpeg|webp|avif|woff2?|ttf|css|js|mjs|json|xml|txt)$/i.test(
      url.pathname,
    )
  ) {
    event.respondWith(staleWhileRevalidate(req));
  }
});

async function navigationStrategy(req) {
  try {
    const fresh = await fetch(req);
    // Cache the successful navigation for offline fallback.
    const cache = await caches.open(RUNTIME);
    cache.put(req, fresh.clone()).catch(() => undefined);
    return fresh;
  } catch {
    // Wave 85 — if the failed navigation was a precached workshop
    // route, serve the cached document directly (don't fall through
    // to the generic root). This means /workshop/materials still
    // shows the materials hub when offline, not the landing page.
    const url = new URL(req.url);
    const precache = await caches.open(PRECACHE);
    if (PRECACHE_URLS.includes(url.pathname)) {
      const exact = await precache.match(url.pathname);
      if (exact) return exact;
    }
    const cached = await precache.match("/");
    if (cached) return cached;
    return new Response(
      "<!doctype html><meta charset=utf-8><title>TARS · offline</title>" +
        "<style>body{background:#000;color:#f5f5f0;font:14px/1.6 ui-monospace,monospace;padding:6vh 6vw}h1{font:500 32px/1 'Share Tech Mono',monospace;letter-spacing:.04em}</style>" +
        "<h1>TARS — offline</h1><p>This page isn't cached and the network is unreachable. Reconnect and try again.</p>",
      { headers: { "content-type": "text/html; charset=utf-8" } },
    );
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(RUNTIME);
  const cached = await cache.match(req);
  const network = fetch(req)
    .then(res => {
      if (res && res.ok) cache.put(req, res.clone()).catch(() => undefined);
      return res;
    })
    .catch(() => null);
  return cached || (await network) || new Response("", { status: 504 });
}

async function networkFirstWithTimeout(req, ms) {
  const cache = await caches.open(RUNTIME);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ms);
  try {
    const res = await fetch(req, { signal: controller.signal });
    clearTimeout(timeout);
    if (res && res.ok) cache.put(req, res.clone()).catch(() => undefined);
    return res;
  } catch {
    clearTimeout(timeout);
    const cached = await cache.match(req);
    if (cached) return cached;
    return new Response('{"ok":false,"error":"offline"}', {
      status: 503,
      headers: { "content-type": "application/json" },
    });
  }
}

// Allow the page to ask for an immediate update via postMessage.
self.addEventListener("message", event => {
  if (event.data === "skipWaiting") self.skipWaiting();
});
