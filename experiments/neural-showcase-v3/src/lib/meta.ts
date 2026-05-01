import { useEffect } from "react";

/**
 * useDocumentMeta — minimal SEO + share-card primitive that updates
 * `document.title` and friends when a route mounts. We don't ship
 * react-helmet-async because the v3 surface is small enough that one
 * imperative effect handles every page.
 *
 * For full SSR / per-route OG card overrides we'll later teach the
 * brother's edge worker to inject these at HTML send time. Today the
 * client-side update covers the analytics + browser-tab-title use
 * case and is a no-op for crawlers (they read the static tags in
 * index.html).
 */

const DEFAULT = {
  title: "TARS — Neural Cockpit · meeet.world",
  description:
    "Local-first AI agent for Mac. Multi-LLM council, Mac operator, persistent memory, $MEEET economy. Install with one curl.",
  ogImage: "https://tars.meeet.world/og.svg",
};

export interface PageMeta {
  /** Page-specific title. Suffix " · meeet.world" appended automatically. */
  title?: string;
  description?: string;
  /** Override the og:image; pass an absolute URL. */
  ogImage?: string;
  /** Set to true to skip the " · meeet.world" suffix (for marketing pages). */
  rawTitle?: boolean;
}

function setMeta(name: string, attr: "name" | "property", value: string) {
  if (typeof document === "undefined") return;
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", value);
}

export function useDocumentMeta(meta: PageMeta) {
  useEffect(() => {
    const title = meta.title
      ? meta.rawTitle
        ? meta.title
        : `${meta.title} · TARS · meeet.world`
      : DEFAULT.title;
    const description = meta.description ?? DEFAULT.description;
    const ogImage = meta.ogImage ?? DEFAULT.ogImage;

    const prevTitle = document.title;
    document.title = title;
    setMeta("description", "name", description);
    setMeta("og:title", "property", title);
    setMeta("og:description", "property", description);
    setMeta("og:image", "property", ogImage);
    setMeta("twitter:title", "name", title);
    setMeta("twitter:description", "name", description);
    setMeta("twitter:image", "name", ogImage);

    return () => {
      // Restore default title on unmount so AppShell's <Routes/>
      // transitions don't leave a stale tab title between pages.
      document.title = prevTitle;
    };
  }, [meta.title, meta.description, meta.ogImage, meta.rawTitle]);
}
