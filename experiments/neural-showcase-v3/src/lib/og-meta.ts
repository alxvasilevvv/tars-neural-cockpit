/**
 * Wave 127 — pure helpers shared between the build-time OG validator
 * (scripts/validate-og-cards.mjs) and its vitest contract
 * (lib/og-meta.test.ts).
 *
 * Keeping the rules in one place means the unit tests pin the same
 * thresholds the CI gate enforces, and any future change (e.g.
 * raising the title cap to match a new Twitter format) only needs
 * touching here.
 */

export const TITLE_MAX = 60;
export const DESC_MAX = 200;
export const IMG_MIN_W = 1200;
export const IMG_MIN_H = 630;
export const CANONICAL_HOST = "https://tars.meeet.world";
export const TITLE_SUFFIX = " · TARS · meeet.world";

export interface TitleCheck {
  ok: boolean;
  effective: string;
  length: number;
  suggestion?: string;
}

export function validateTitle(raw: string, rawTitle = false): TitleCheck {
  const suffix = rawTitle ? "" : TITLE_SUFFIX;
  const effective = `${raw}${suffix}`;
  const ok = effective.length <= TITLE_MAX && raw.length > 0;
  let suggestion: string | undefined;
  if (!ok && raw.length > 0) {
    const room = TITLE_MAX - suffix.length - 1;
    suggestion = raw.slice(0, Math.max(0, room)).trim() + "…";
  }
  return { ok, effective, length: effective.length, suggestion };
}

export interface DescCheck {
  ok: boolean;
  length: number;
}

export function validateDescription(raw: string): DescCheck {
  return { ok: raw.length > 0 && raw.length <= DESC_MAX, length: raw.length };
}

export function isAbsoluteOgUrl(url: string): boolean {
  return url.startsWith(CANONICAL_HOST + "/");
}

export interface ImgDims {
  width: number;
  height: number;
}

export function meetsImageDims(dims: ImgDims): boolean {
  return dims.width >= IMG_MIN_W && dims.height >= IMG_MIN_H;
}

/**
 * Parse the opening `<svg ...>` tag for `width` / `height`, falling
 * back to the `viewBox` width/height. Returns zeros when the tag is
 * missing or unparseable so callers can flag a WARN.
 */
export function parseSvgDims(svgHead: string): ImgDims {
  const tag = svgHead.match(/<svg\b[^>]*>/i);
  if (!tag) return { width: 0, height: 0 };
  const attrs = tag[0];
  const w = attrs.match(/\bwidth="(\d+)"/);
  const h = attrs.match(/\bheight="(\d+)"/);
  if (w && h) return { width: +w[1], height: +h[1] };
  const vb = attrs.match(/\bviewBox="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"/);
  if (vb) return { width: +vb[3], height: +vb[4] };
  return { width: 0, height: 0 };
}

/**
 * Suggest the best per-route OG SVG slug given a router path and a
 * list of available file names (e.g. `["og-pricing.svg", "og.svg"]`).
 * Used by the auto-fix branch of the validator and exposed publicly
 * so future tooling can reuse it.
 */
export function suggestOgSlug(routePath: string, available: string[]): string {
  const slug = routePath.replace(/^\//, "").split("/")[0] || "home";
  const exact = available.find((f) => f === `og-${slug}.svg`);
  if (exact) return `/${exact}`;
  const prefix = available.find((f) => f.startsWith(`og-${slug}-`));
  if (prefix) return `/${prefix}`;
  return "/og.svg";
}

export const TWITTER_CARD_VALUE = "summary_large_image" as const;

export function isValidTwitterCard(v: string | null): boolean {
  return v === TWITTER_CARD_VALUE;
}

export function isValidOgType(v: string | null): boolean {
  return v === "website" || v === "article";
}
