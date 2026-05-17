/*
 * Token preview — single page that renders every MASTER token in
 * isolation. The point is verification, not aesthetics: when Claude
 * (W307) or operator changes a hex / font / spacing, this page tells
 * you what actually changed before the cockpit shell does.
 *
 * Renders into the page-level container passed in from main.ts. No
 * external state, no framework — just DOM construction.
 */

interface Swatch {
  token: string;
  use: string;
  /** Inline preview value — usually the same as the CSS var, but
   * may be a rgba/hex literal for documentation. */
  preview: string;
}

const SURFACE_SWATCHES: Swatch[] = [
  { token: "--color-bg-0", use: "Page background (OLED black).", preview: "#000000" },
  { token: "--color-bg-1", use: "Raised surfaces (cards, footer).", preview: "#0B0B10" },
  { token: "--color-bg-2", use: "Sub-surfaces / highlight strips.", preview: "#14141B" },
];

const INK_SWATCHES: Swatch[] = [
  { token: "--color-ink", use: "Primary text.", preview: "#F5F5F0" },
  { token: "--color-ink-2", use: "Secondary text & metadata.", preview: "#A09E96" },
  // W308 step 1 (W307 verdict): promoted to #8A867B (4.62:1 on bg-1).
  { token: "--color-ink-3", use: "Tertiary / labels. WCAG AA on bg-1.", preview: "#8A867B" },
];

const LINE_SWATCHES: Swatch[] = [
  { token: "--color-line", use: "Hairlines & card borders.", preview: "rgba(245,245,240,0.06)" },
  { token: "--color-line-strong", use: "Card hover.", preview: "rgba(245,245,240,0.12)" },
  { token: "--color-line-hot", use: "Active hairline / focus.", preview: "rgba(202,138,4,0.32)" },
];

const ACCENT_SWATCHES: Swatch[] = [
  { token: "--color-accent", use: "The single primary accent (gold).", preview: "#CA8A04" },
  { token: "--color-accent-soft", use: "Subtle glow & rims.", preview: "rgba(202,138,4,0.55)" },
  { token: "--color-accent-deep", use: "Tinted backplate.", preview: "rgba(202,138,4,0.12)" },
];

const HUD_SWATCHES: Swatch[] = [
  { token: "--color-hud", use: "HUD wireframe lines & 3D rings (sparingly).", preview: "#00FFFF" },
  { token: "--color-hud-soft", use: "HUD glow.", preview: "rgba(0,255,255,0.32)" },
];

const FUNCTIONAL_SWATCHES: Swatch[] = [
  { token: "--color-alert", use: "Live / warn telemetry only.", preview: "#EF4444" },
  { token: "--color-success", use: "Success states only.", preview: "#34D399" },
];

const SECTIONS: { title: string; swatches: Swatch[] }[] = [
  { title: "Surfaces", swatches: SURFACE_SWATCHES },
  { title: "Ink", swatches: INK_SWATCHES },
  { title: "Hairlines", swatches: LINE_SWATCHES },
  { title: "Accent (gold)", swatches: ACCENT_SWATCHES },
  { title: "HUD (cyan, sparingly)", swatches: HUD_SWATCHES },
  { title: "Functional", swatches: FUNCTIONAL_SWATCHES },
];

const TYPE_SAMPLES: { label: string; cls: string; text: string }[] = [
  { label: ".t-display", cls: "t-display", text: "TARS COCKPIT" },
  { label: ".t-greeting", cls: "t-greeting", text: "Good morning, Operator." },
  { label: ".t-h1", cls: "t-h1", text: "Neural cockpit, local-first." },
  { label: ".t-h2", cls: "t-h2", text: "Multi-model consensus you can trust." },
  { label: ".t-h3", cls: "t-h3", text: "Section heading" },
  {
    label: ".t-body",
    cls: "t-body",
    text:
      "Body paragraph in Fira Code. Ligatures on. Line-height 1.65. Max width 64ch. " +
      "Long enough to verify wrapping behaves and the contrast meets the 7:1 target " +
      "against `--color-bg-1` cards.",
  },
  { label: ".t-small", cls: "t-small", text: "Caption / metadata at 13px." },
  { label: ".t-label", cls: "t-label", text: "HUD · NAV · TICKER · 11PX" },
  { label: ".t-num", cls: "t-num t-body", text: "01 · 99.8% · 142.07 · 1,309,415" },
];

const SANCTIONED_GLYPHS: string[] = ["▣", "◇", "◆", "═", "╳", "◯", "▾", "▸"];

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function clear(node: HTMLElement): void {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function renderHeader(): HTMLElement {
  const header = el("header", "preview-header");

  const eyebrow = el("p", "t-label", "TARS · W308 step 0 · tokens preview");
  eyebrow.style.color = "var(--color-accent)";

  const title = el("h1", "t-display", "Cockpit token grid");
  title.style.lineHeight = "var(--line-tight)";

  const sub = el(
    "p",
    "t-body",
    "Every MASTER §3–§6 token rendered in isolation. Edit `src/styles/tokens.css` and reload — what shifts here also shifts in the cockpit shell. The drift smoke test (`pytest tests/test_cockpit_tokens_sync.py`) guards against MASTER.md ↔ tokens.css disagreement.",
  );
  sub.style.color = "var(--color-ink-2)";

  header.append(eyebrow, title, sub);
  return header;
}

function renderSwatchSection(title: string, swatches: Swatch[]): HTMLElement {
  const section = el("section", "surface");
  section.append(el("h2", "t-h2", title));

  const grid = el("div", "swatch-grid");
  for (const s of swatches) {
    const card = el("div", "swatch");
    const chip = el("div", "swatch__chip");
    chip.style.background = `var(${s.token})`;
    chip.setAttribute("aria-hidden", "true");

    const meta = el("div", "swatch__meta");
    meta.append(
      el("code", "swatch__token", s.token),
      el("span", "swatch__preview t-small", s.preview),
      el("p", "swatch__use t-small", s.use),
    );

    card.append(chip, meta);
    grid.append(card);
  }

  section.append(grid);
  return section;
}

function renderTypography(): HTMLElement {
  const section = el("section", "surface");
  section.append(el("h2", "t-h2", "Typography scale"));

  const list = el("div", "type-list");
  for (const sample of TYPE_SAMPLES) {
    const row = el("div", "type-row");
    row.append(
      el("code", "type-row__label t-small", sample.label),
      el("p", `type-row__sample ${sample.cls}`, sample.text),
    );
    list.append(row);
  }

  section.append(list);
  return section;
}

function renderCtaPair(): HTMLElement {
  const section = el("section", "surface");
  section.append(el("h2", "t-h2", "CTA pair (black on gold — hard rule)"));

  section.append(
    el(
      "p",
      "t-small",
      "Text on `--color-accent` MUST be `--cta-text-on-accent` (#000000). 9.62:1 contrast (AAA). The `.cta` class enforces this; do not hand-roll gold buttons.",
    ),
  );

  const row = el("div", "cta-row");
  const primary = el("button", "cta", "Start session");
  primary.type = "button";
  const ghost = el("button", "cta cta--ghost", "Cancel");
  ghost.type = "button";
  row.append(primary, ghost);
  section.append(row);

  return section;
}

function renderGlyphSet(): HTMLElement {
  const section = el("section", "surface");
  section.append(el("h2", "t-h2", "Sanctioned mono glyphs"));
  section.append(
    el(
      "p",
      "t-small",
      "Approved icon substitutes (Fira Code). Use `.glyph` class. Never use emoji as icons (MASTER §3 anti-pattern).",
    ),
  );

  const row = el("div", "glyph-row");
  for (const g of SANCTIONED_GLYPHS) {
    const cell = el("span", "glyph-cell");
    cell.append(el("span", "glyph", g), el("code", "t-small", `U+${g.codePointAt(0)!.toString(16).toUpperCase()}`));
    row.append(cell);
  }
  section.append(row);
  return section;
}

function renderMotion(): HTMLElement {
  const section = el("section", "surface");
  section.append(el("h2", "t-h2", "Motion contract"));

  section.append(
    el(
      "p",
      "t-small",
      "W308 step 1: `--motion-pulse` slowed from 1.6s → 3.6s (ambient = all-good). 1.6s reserved for `--motion-alert-pulse` (genuine alert states). Both honour prefers-reduced-motion: reduce.",
    ),
  );

  const live = el("div", "live-row");
  const dot = el("span", "live-dot");
  dot.setAttribute("aria-hidden", "true");
  live.append(
    dot,
    el(
      "p",
      "t-small",
      "Health pulse — `--motion-pulse` (3.6s ease-in-out). Slower than UI-affordance pulses by design.",
    ),
  );

  const alert = el("div", "live-row");
  const alertDot = el("span", "live-dot live-dot--alert");
  alertDot.setAttribute("aria-hidden", "true");
  alert.append(
    alertDot,
    el(
      "p",
      "t-small",
      "Alert pulse — `--motion-alert-pulse` (1.6s ease-in-out). Reserved for genuine warn states only.",
    ),
  );

  section.append(live, alert);

  const budget = el("div", "budget-row");
  budget.append(
    el("code", "t-label", "MOTION-BUDGET-MAX"),
    el("span", "budget-val t-h2 t-num", "2"),
    el("p", "t-small", "Max simultaneous infinite animations per view (cockpit shell). Marketing surfaces may exceed; per-surface contract documented in MASTER §6."),
  );
  section.append(budget);

  return section;
}

function injectPreviewStyles(): void {
  const css = `
    .preview-header { display: flex; flex-direction: column; gap: var(--space-md); }
    .swatch-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: var(--space-md);
      margin-block-start: var(--space-md);
    }
    .swatch {
      display: flex;
      gap: var(--space-md);
      align-items: flex-start;
      padding: var(--space-sm);
      border: var(--hairline);
      border-radius: var(--radius-sm);
      background: var(--color-bg-2);
    }
    .swatch__chip {
      inline-size: 56px;
      block-size: 56px;
      border-radius: var(--radius-xs);
      border: var(--hairline-strong);
      flex-shrink: 0;
    }
    .swatch__meta { display: flex; flex-direction: column; gap: 2px; min-inline-size: 0; }
    .swatch__token { color: var(--color-ink); font-size: var(--type-small); }
    .swatch__preview { color: var(--color-accent); font-variant-numeric: tabular-nums; }
    .swatch__use { margin-block-start: var(--space-xs); }
    .type-list { display: flex; flex-direction: column; gap: var(--space-lg); margin-block-start: var(--space-md); }
    .type-row { display: grid; grid-template-columns: 120px 1fr; gap: var(--space-md); align-items: baseline; }
    @media (max-width: 640px) {
      .type-row { grid-template-columns: 1fr; }
    }
    .type-row__label { color: var(--color-ink-3); align-self: start; padding-block-start: 0.4em; }
    .type-row__sample { color: var(--color-ink); }
    .live-row { display: flex; align-items: center; gap: var(--space-sm); margin-block-start: var(--space-md); }
    .live-dot {
      inline-size: 10px; block-size: 10px; border-radius: var(--radius-pill);
      background: var(--color-success);
      box-shadow: 0 0 8px var(--color-success);
      animation: live-pulse var(--motion-pulse) infinite;
    }
    .live-dot--alert {
      background: var(--color-alert);
      box-shadow: 0 0 8px var(--color-alert);
      animation: live-pulse var(--motion-alert-pulse) infinite;
    }
    @keyframes live-pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%      { opacity: 0.55; transform: scale(0.85); }
    }
    .cta-row { display: flex; gap: var(--space-sm); margin-block-start: var(--space-md); flex-wrap: wrap; }
    .glyph-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
      gap: var(--space-sm);
      margin-block-start: var(--space-md);
    }
    .glyph-cell {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: var(--space-xs);
      padding: var(--space-sm);
      border: var(--hairline);
      border-radius: var(--radius-sm);
      background: var(--color-bg-2);
    }
    .glyph-cell .glyph { font-size: 1.6rem; color: var(--color-ink); }
    .glyph-cell code { color: var(--color-ink-3); font-size: 10px; }
    .budget-row {
      display: grid;
      grid-template-columns: max-content max-content 1fr;
      align-items: center;
      gap: var(--space-md);
      margin-block-start: var(--space-lg);
      padding-block-start: var(--space-md);
      border-block-start: var(--hairline);
    }
    .budget-val { color: var(--color-accent); }
    @media (max-width: 640px) {
      .budget-row { grid-template-columns: 1fr; }
    }
  `;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.append(style);
}

export function mountTokensPreview(root: HTMLElement): void {
  injectPreviewStyles();
  clear(root);
  root.append(renderHeader());
  for (const section of SECTIONS) {
    root.append(renderSwatchSection(section.title, section.swatches));
  }
  root.append(
    renderTypography(),
    renderCtaPair(),
    renderGlyphSet(),
    renderMotion(),
  );
}
