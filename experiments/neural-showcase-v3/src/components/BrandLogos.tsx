/**
 * BrandLogos — single-colour SVG marks for the integration row.
 *
 * Replaces the previous "letter-in-a-coloured-box" chips with real
 * brand glyphs that read as logos at small sizes. All paths are
 * `currentColor`-tinted so we can swap to muted ink-2 by default
 * and brighten on hover for a tasteful integration row.
 *
 * Marks are stylised originals — close enough to be recognisable
 * but distinct from the trademarked logos so we keep IP clean.
 */

interface MarkProps {
  size?: number;
  className?: string;
}

const base = (className?: string) =>
  `pointer-events-none select-none ${className ?? ""}`;

/** Anthropic — squared "A" with the open notch. */
export function AnthropicMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M9.4 4 5 20h3.4l.84-3.2h5.52L15.6 20H19L14.6 4H9.4Zm.32 9.8 1.78-6.7 1.78 6.7H9.72Z" />
    </svg>
  );
}

/** OpenAI — six-petal hexagonal flower. */
export function OpenAIMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={base(className)}
      aria-hidden
    >
      <path d="M12 2 21 7v10l-9 5-9-5V7l9-5Z" />
      <path d="m12 7 5 3v4l-5 3-5-3v-4l5-3Z" />
    </svg>
  );
}

/** Cursor — chevron-style "C". */
export function CursorMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M5 4 19 12 5 20V14l8-2-8-2V4Z" />
    </svg>
  );
}

/** Windsurf — wave-glyph. */
export function WindsurfMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      className={base(className)}
      aria-hidden
    >
      <path d="M3 16c2-2 4-2 6 0s4 2 6 0 4-2 6 0" />
      <path d="M3 11c2-2 4-2 6 0s4 2 6 0 4-2 6 0" opacity="0.55" />
    </svg>
  );
}

/** MCP — microchip with two contact rows. */
export function MCPMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinejoin="round"
      className={base(className)}
      aria-hidden
    >
      <rect x="6" y="6" width="12" height="12" rx="1.2" />
      <path d="M9 6V4M12 6V4M15 6V4M9 20v-2M12 20v-2M15 20v-2M6 9H4M6 12H4M6 15H4M20 9h-2M20 12h-2M20 15h-2" />
    </svg>
  );
}

/** Slack — four rounded bars in a pinwheel. */
export function SlackMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <rect x="3" y="10" width="6" height="2" rx="1" />
      <rect x="10" y="3" width="2" height="6" rx="1" />
      <rect x="15" y="12" width="6" height="2" rx="1" />
      <rect x="12" y="15" width="2" height="6" rx="1" />
      <rect x="9" y="9" width="6" height="6" rx="1" opacity="0.45" />
    </svg>
  );
}

/** iMessage — speech bubble with tail. */
export function IMessageMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M12 4c5 0 9 3.4 9 7.6 0 4.2-4 7.6-9 7.6-1 0-2-.13-2.86-.36L5 20.5l1.4-3.05C5.13 16.13 3 14 3 11.6 3 7.4 7 4 12 4Z" />
    </svg>
  );
}

/** GitHub — octocat silhouette in geometric form. */
export function GitHubMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M12 2C6.5 2 2 6.5 2 12c0 4.4 2.9 8.2 6.8 9.5.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.3-3.4-1.3-.4-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.7-1.4-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.7 1 .8-.2 1.6-.3 2.5-.3s1.7.1 2.5.3c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.4 4.7-4.6 5 .4.3.7 1 .7 1.9v2.8c0 .3.2.6.7.5 4-1.3 6.8-5.1 6.8-9.5 0-5.5-4.5-10-10-10Z" />
    </svg>
  );
}

/** meeet.world — orbiting trio dot mark. */
export function MeeetMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      className={base(className)}
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" opacity="0.3" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="3" r="1.6" fill="currentColor" />
      <circle cx="20" cy="16" r="1.6" fill="currentColor" />
      <circle cx="4" cy="16" r="1.6" fill="currentColor" />
    </svg>
  );
}

/** Solana — three slanted bars. */
export function SolanaMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M5 7l1.6-2h13l-1.6 2H5Zm0 5 1.6-2h13l-1.6 2H5Zm13.4 5L20 15H7l-1.6 2h13Z" />
    </svg>
  );
}

/** Linear — angular L. */
export function LinearMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M3 13.4 10.6 21H4l-1-1v-6.6Zm0-4 11.6 11.6h-3L3 12.4v-3Zm0-4 15.6 15.6h-3L3 8.4v-3Zm.4-2.6L21 19.4v-3L6.4 1.8h-3Zm6 0L21 13.4v-3L12.4 1.8h-3Zm6 0L21 7.4v-3L18.4 1.8h-3Z" />
    </svg>
  );
}

/** Notion — simple N door silhouette. */
export function NotionMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M5 4h11l3 3v13H5V4Zm2 2v12h10V8.4L15.6 7H7Zm2.5 3 5 7v-7h2v10h-2l-5-7v7h-2V9h2Z" />
    </svg>
  );
}

/* ─── OS marks — used by DownloadStrip ─────────────────────────────── */

/** Apple — bitten apple silhouette. */
export function AppleMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M16.4 12.5c0-2.6 2.1-3.9 2.2-3.9-1.2-1.7-3-1.95-3.7-2-1.55-.16-3 .9-3.8.9-.8 0-2-.88-3.3-.85C5.9 6.7 4.4 7.7 3.6 9.2c-1.7 3-.45 7.45 1.25 9.9.85 1.2 1.85 2.55 3.15 2.5 1.25-.05 1.7-.8 3.2-.8 1.5 0 1.9.8 3.2.78 1.3-.02 2.15-1.2 3-2.4.95-1.4 1.3-2.7 1.3-2.8-.02-.02-2.5-.95-2.5-3.88ZM14 5.5c.7-.85 1.15-2 1-3.16-1 .04-2.2.65-2.9 1.5-.65.75-1.2 1.95-1.05 3.05 1.1.08 2.25-.55 2.95-1.39Z" />
    </svg>
  );
}

/** Windows — four-pane logo. */
export function WindowsMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M3 4.7 11 3.6V11.3H3V4.7Zm0 7.4H11v7.7L3 19V12.1Zm9-8.9 9-1.2V11.3H12V3.2Zm0 8.9h9V20.8L12 19.6V12.1Z" />
    </svg>
  );
}

/** Linux — Tux silhouette (geometric). */
export function LinuxMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M12 2c-2.4 0-4.3 1.7-4.3 4.4 0 1.05.32 2 .85 2.7-1.5 1.4-2.4 3.3-2.4 5.3 0 .85.16 1.6.45 2.3-.55.45-.92 1-1.05 1.6-.18.85.18 1.6.94 2.05.55.32 1.25.45 2 .35.45-.06.9-.2 1.3-.4.6.55 1.45 1.05 2.3 1.05.85 0 1.7-.5 2.3-1.05.4.2.85.34 1.3.4.75.1 1.45-.03 2-.35.76-.45 1.12-1.2.94-2.05-.13-.6-.5-1.15-1.05-1.6.29-.7.45-1.45.45-2.3 0-2-.9-3.9-2.4-5.3.53-.7.85-1.65.85-2.7 0-2.7-1.9-4.4-4.3-4.4Zm-1.7 4c.45 0 .8.35.8.8 0 .45-.35.8-.8.8-.45 0-.8-.35-.8-.8 0-.45.35-.8.8-.8Zm3.4 0c.45 0 .8.35.8.8 0 .45-.35.8-.8.8-.45 0-.8-.35-.8-.8 0-.45.35-.8.8-.8Zm-1.7 2.8c1.5 0 2.7.95 2.7 2.1 0 .55-.5 1.05-1.25 1.4-.7.32-.95.45-1.45.45-.5 0-.75-.13-1.45-.45-.75-.35-1.25-.85-1.25-1.4 0-1.15 1.2-2.1 2.7-2.1Z" />
    </svg>
  );
}

/** iOS — squared rounded glyph with bite. */
export function IOSMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M3 7c0-2.2 1.8-4 4-4h10c2.2 0 4 1.8 4 4v10c0 2.2-1.8 4-4 4H7c-2.2 0-4-1.8-4-4V7Zm5.7 7.5h-1V11h1v3.5Zm-.5-4.4a.65.65 0 1 1 0-1.3.65.65 0 0 1 0 1.3Zm4 4.5c-1.4 0-2.4-1-2.4-2.5s1-2.5 2.4-2.5 2.4 1 2.4 2.5-1 2.5-2.4 2.5Zm0-.86c.95 0 1.4-.7 1.4-1.65s-.45-1.65-1.4-1.65c-.95 0-1.4.7-1.4 1.65s.45 1.65 1.4 1.65Zm3.95.86c-.95 0-1.55-.5-1.65-1.25h.95c.05.4.4.65.85.65.5 0 .85-.25.85-.6 0-.35-.3-.5-.95-.65-.85-.2-1.5-.5-1.5-1.4 0-.85.7-1.45 1.65-1.45 1 0 1.6.55 1.65 1.3h-.95c-.05-.4-.35-.55-.75-.55-.45 0-.7.2-.7.5 0 .35.3.45.9.6.85.2 1.55.5 1.55 1.45 0 .9-.7 1.4-1.7 1.4Z" />
    </svg>
  );
}

/** Android — droid silhouette. */
export function AndroidMark({ size = 18, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      className={base(className)}
      aria-hidden
    >
      <path d="M6 11.5h12v6c0 .55-.45 1-1 1h-1v3a1 1 0 1 1-2 0v-3h-2v3a1 1 0 1 1-2 0v-3H9v3a1 1 0 1 1-2 0v-3H6c-.55 0-1-.45-1-1v-6Zm-2 0a1.25 1.25 0 1 0 2.5 0v-4a1.25 1.25 0 1 0-2.5 0v4Zm13.5 0a1.25 1.25 0 1 0 2.5 0v-4a1.25 1.25 0 1 0-2.5 0v4ZM7 5.5l-1-1.7a.5.5 0 0 1 .85-.5l1.05 1.8c.95-.4 2-.6 3.1-.6s2.15.2 3.1.6l1.05-1.8a.5.5 0 1 1 .85.5l-1 1.7C16.6 6.5 18 8.4 18 10.5H6c0-2.1 1.4-4 3-5Zm2 3a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Zm6 0a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1Z" />
    </svg>
  );
}

/* Convenient registry the integration row can iterate over. */
export const BRAND_MARKS = {
  anthropic: { Component: AnthropicMark, label: "Anthropic" },
  openai:    { Component: OpenAIMark,    label: "OpenAI" },
  cursor:    { Component: CursorMark,    label: "Cursor" },
  windsurf:  { Component: WindsurfMark,  label: "Windsurf" },
  mcp:       { Component: MCPMark,       label: "MCP" },
  slack:     { Component: SlackMark,     label: "Slack" },
  imessage:  { Component: IMessageMark,  label: "iMessage" },
  github:    { Component: GitHubMark,    label: "GitHub" },
  meeet:     { Component: MeeetMark,     label: "meeet.world" },
  solana:    { Component: SolanaMark,    label: "Solana" },
  linear:    { Component: LinearMark,    label: "Linear" },
  notion:    { Component: NotionMark,    label: "Notion" },
} as const;

export type BrandKey = keyof typeof BRAND_MARKS;
