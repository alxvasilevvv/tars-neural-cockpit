import"./cockpit-Bqv5P_F3.js";const p=[{token:"--color-bg-0",use:"Page background (OLED black).",preview:"#000000"},{token:"--color-bg-1",use:"Raised surfaces (cards, footer).",preview:"#0B0B10"},{token:"--color-bg-2",use:"Sub-surfaces / highlight strips.",preview:"#14141B"}],d=[{token:"--color-ink",use:"Primary text.",preview:"#F5F5F0"},{token:"--color-ink-2",use:"Secondary text & metadata.",preview:"#A09E96"},{token:"--color-ink-3",use:"Tertiary / labels. WCAG AA on bg-1.",preview:"#8A867B"}],u=[{token:"--color-line",use:"Hairlines & card borders.",preview:"rgba(245,245,240,0.06)"},{token:"--color-line-strong",use:"Card hover.",preview:"rgba(245,245,240,0.12)"},{token:"--color-line-hot",use:"Active hairline / focus.",preview:"rgba(202,138,4,0.32)"}],m=[{token:"--color-accent",use:"The single primary accent (gold).",preview:"#CA8A04"},{token:"--color-accent-soft",use:"Subtle glow & rims.",preview:"rgba(202,138,4,0.55)"},{token:"--color-accent-deep",use:"Tinted backplate.",preview:"rgba(202,138,4,0.12)"}],g=[{token:"--color-hud",use:"HUD wireframe lines & 3D rings (sparingly).",preview:"#00FFFF"},{token:"--color-hud-soft",use:"HUD glow.",preview:"rgba(0,255,255,0.32)"}],h=[{token:"--color-alert",use:"Live / warn telemetry only.",preview:"#EF4444"},{token:"--color-success",use:"Success states only.",preview:"#34D399"}],v=[{title:"Surfaces",swatches:p},{title:"Ink",swatches:d},{title:"Hairlines",swatches:u},{title:"Accent (gold)",swatches:m},{title:"HUD (cyan, sparingly)",swatches:g},{title:"Functional",swatches:h}],b=[{label:".t-display",cls:"t-display",text:"TARS COCKPIT"},{label:".t-greeting",cls:"t-greeting",text:"Good morning, Operator."},{label:".t-h1",cls:"t-h1",text:"Neural cockpit, local-first."},{label:".t-h2",cls:"t-h2",text:"Multi-model consensus you can trust."},{label:".t-h3",cls:"t-h3",text:"Section heading"},{label:".t-body",cls:"t-body",text:"Body paragraph in Fira Code. Ligatures on. Line-height 1.65. Max width 64ch. Long enough to verify wrapping behaves and the contrast meets the 7:1 target against `--color-bg-1` cards."},{label:".t-small",cls:"t-small",text:"Caption / metadata at 13px."},{label:".t-label",cls:"t-label",text:"HUD · NAV · TICKER · 11PX"},{label:".t-num",cls:"t-num t-body",text:"01 · 99.8% · 142.07 · 1,309,415"}],w=["▣","◇","◆","═","╳","◯","▾","▸"];function e(t,a,o){const r=document.createElement(t);return a&&(r.className=a),o!==void 0&&(r.textContent=o),r}function f(t){for(;t.firstChild;)t.removeChild(t.firstChild)}function y(){const t=e("header","preview-header"),a=e("p","t-label","TARS · W308 step 0 · tokens preview");a.style.color="var(--color-accent)";const o=e("h1","t-display","Cockpit token grid");o.style.lineHeight="var(--line-tight)";const r=e("p","t-body","Every MASTER §3–§6 token rendered in isolation. Edit `src/styles/tokens.css` and reload — what shifts here also shifts in the cockpit shell. The drift smoke test (`pytest tests/test_cockpit_tokens_sync.py`) guards against MASTER.md ↔ tokens.css disagreement.");return r.style.color="var(--color-ink-2)",t.append(a,o,r),t}function k(t,a){const o=e("section","surface");o.append(e("h2","t-h2",t));const r=e("div","swatch-grid");for(const s of a){const n=e("div","swatch"),i=e("div","swatch__chip");i.style.background=`var(${s.token})`,i.setAttribute("aria-hidden","true");const l=e("div","swatch__meta");l.append(e("code","swatch__token",s.token),e("span","swatch__preview t-small",s.preview),e("p","swatch__use t-small",s.use)),n.append(i,l),r.append(n)}return o.append(r),o}function x(){const t=e("section","surface");t.append(e("h2","t-h2","Typography scale"));const a=e("div","type-list");for(const o of b){const r=e("div","type-row");r.append(e("code","type-row__label t-small",o.label),e("p",`type-row__sample ${o.cls}`,o.text)),a.append(r)}return t.append(a),t}function S(){const t=e("section","surface");t.append(e("h2","t-h2","CTA pair (black on gold — hard rule)")),t.append(e("p","t-small","Text on `--color-accent` MUST be `--cta-text-on-accent` (#000000). 9.62:1 contrast (AAA). The `.cta` class enforces this; do not hand-roll gold buttons."));const a=e("div","cta-row"),o=e("button","cta","Start session");o.type="button";const r=e("button","cta cta--ghost","Cancel");return r.type="button",a.append(o,r),t.append(a),t}function _(){const t=e("section","surface");t.append(e("h2","t-h2","Sanctioned mono glyphs")),t.append(e("p","t-small","Approved icon substitutes (Fira Code). Use `.glyph` class. Never use emoji as icons (MASTER §3 anti-pattern)."));const a=e("div","glyph-row");for(const o of w){const r=e("span","glyph-cell");r.append(e("span","glyph",o),e("code","t-small",`U+${o.codePointAt(0).toString(16).toUpperCase()}`)),a.append(r)}return t.append(a),t}function A(){const t=e("section","surface");t.append(e("h2","t-h2","Motion contract")),t.append(e("p","t-small","W308 step 1: `--motion-pulse` slowed from 1.6s → 3.6s (ambient = all-good). 1.6s reserved for `--motion-alert-pulse` (genuine alert states). Both honour prefers-reduced-motion: reduce."));const a=e("div","live-row"),o=e("span","live-dot");o.setAttribute("aria-hidden","true"),a.append(o,e("p","t-small","Health pulse — `--motion-pulse` (3.6s ease-in-out). Slower than UI-affordance pulses by design."));const r=e("div","live-row"),s=e("span","live-dot live-dot--alert");s.setAttribute("aria-hidden","true"),r.append(s,e("p","t-small","Alert pulse — `--motion-alert-pulse` (1.6s ease-in-out). Reserved for genuine warn states only.")),t.append(a,r);const n=e("div","budget-row");return n.append(e("code","t-label","MOTION-BUDGET-MAX"),e("span","budget-val t-h2 t-num","2"),e("p","t-small","Max simultaneous infinite animations per view (cockpit shell). Marketing surfaces may exceed; per-surface contract documented in MASTER §6.")),t.append(n),t}function T(){const t=`
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
  `,a=document.createElement("style");a.textContent=t,document.head.append(a)}function C(t){T(),f(t),t.append(y());for(const a of v)t.append(k(a.title,a.swatches));t.append(x(),S(),_(),A())}const c=document.getElementById("preview-root");if(!c)throw new Error("[cockpit:preview] #preview-root not found in preview.html — refusing to boot.");C(c);
//# sourceMappingURL=cockpit-CkdrDMKe.js.map
