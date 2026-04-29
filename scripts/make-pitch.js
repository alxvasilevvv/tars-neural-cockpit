#!/usr/bin/env node
/**
 * make-pitch.js — generates `deliverables/TARS_Pitch_2026Q2.pptx`.
 *
 * Mirrors the HTML deck rendered at `/pitch` (Pitch.tsx) — same 12
 * slides, same content, brand triad palette. Run from the repo root
 * after `npm install pptxgenjs`:
 *
 *     npm install --save-dev pptxgenjs
 *     node jarvis/scripts/make-pitch.js
 *
 * Output: `jarvis/deliverables/TARS_Pitch_2026Q2.pptx`.
 */

const path = require("path");
const fs = require("fs");

let pptxgen;
try {
  pptxgen = require("pptxgenjs");
} catch (e) {
  console.error("Missing dependency. Install with: npm install --save-dev pptxgenjs");
  process.exit(1);
}

const OUT_DIR = path.resolve(__dirname, "..", "deliverables");
fs.mkdirSync(OUT_DIR, { recursive: true });
const OUT_PATH = path.join(OUT_DIR, "TARS_Pitch_2026Q2.pptx");

// Brand palette (matches docs/PRODUCT_PHASE_M.md / index.css)
const BG       = "0B0B10";
const INK      = "F5F5F0";
const INK_2    = "B0AEA4";
const INK_3    = "7A786F";
const LINE     = "1A1A22";
const INDIGO   = "6366F1";
const VIOLET   = "8B5CF6";
const CYAN     = "06B6D4";
const VIOLET_S = "A78BFA";
const SUCCESS  = "34D399";
const AMBER    = "F59E0B";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 × 7.5 inches
pres.author = "meeet.world";
pres.title  = "TARS · Agent Intelligence";
pres.subject = "Pitch deck Q2 2026";

const W = 13.3, H = 7.5;
const M = 0.7; // outer margin

/** Common slide chrome — background + brand-triad hairline. */
function frame(slide, num, tag) {
  slide.background = { color: BG };
  // Top hairline
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: W, h: 0.04,
    fill: { color: INDIGO }, line: { color: INDIGO, width: 0 },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: W * 0.3, y: 0, w: W * 0.4, h: 0.04,
    fill: { color: VIOLET }, line: { color: VIOLET, width: 0 },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: W * 0.5, y: 0, w: W * 0.4, h: 0.04,
    fill: { color: CYAN, transparency: 30 }, line: { color: CYAN, width: 0 },
  });
  // Eyebrow
  slide.addText(
    [
      { text: num + " ", options: { color: INDIGO, bold: true } },
      { text: tag,        options: { color: INK_2 } },
    ],
    {
      x: M, y: 0.45, w: W - 2 * M, h: 0.4,
      fontFace: "Consolas", fontSize: 11, charSpacing: 2.4, margin: 0,
    },
  );
  // Footer rule
  slide.addShape(pres.shapes.LINE, {
    x: M, y: H - 0.7, w: W - 2 * M, h: 0,
    line: { color: LINE, width: 1 },
  });
}

function footer(slide, slideIndex, total) {
  const baseTextOpts = {
    fontFace: "Consolas", fontSize: 9, color: INK_3, charSpacing: 2.2, margin: 0,
  };
  slide.addText("← back to home", { ...baseTextOpts, x: M, y: H - 0.5, w: 3.0, h: 0.3 });
  slide.addText("meeet.world · TARS · 2026 Q2", {
    ...baseTextOpts, x: W / 2 - 2, y: H - 0.5, w: 4, h: 0.3, align: "center",
  });
  slide.addText(
    `${String(slideIndex).padStart(2, "0")} / ${String(total).padStart(2, "0")}`,
    { ...baseTextOpts, x: W - M - 1.5, y: H - 0.5, w: 1.5, h: 0.3, align: "right" },
  );
}

function title(slide, text, opts = {}) {
  slide.addText(text, {
    x: M, y: 1.05, w: W - 2 * M, h: 1.7,
    fontFace: "Cambria", fontSize: opts.fontSize ?? 50, bold: true,
    color: INK, charSpacing: -0.5, valign: "top", margin: 0,
  });
}

function body(slide, runs, opts = {}) {
  slide.addText(runs, {
    x: M, y: opts.y ?? 2.7, w: opts.w ?? W - 2 * M, h: opts.h ?? 4,
    fontFace: "Calibri", fontSize: opts.fontSize ?? 16, color: INK_2,
    paraSpaceAfter: 8, valign: "top", margin: 0,
    ...opts,
  });
}

function statCard(slide, x, y, w, h, num, label, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill: { color: "11111A" },
    line: { color: LINE, width: 1 },
  });
  slide.addText(num, {
    x: x + 0.2, y: y + 0.2, w: w - 0.4, h: 0.85,
    fontFace: "Cambria", fontSize: 36, bold: true, color, margin: 0,
  });
  slide.addText(label, {
    x: x + 0.2, y: y + 1.1, w: w - 0.4, h: 0.3,
    fontFace: "Consolas", fontSize: 9, color: INK_2, charSpacing: 2.2, margin: 0,
  });
}

function bulletRuns(items) {
  return items.map((t, i) => ({
    text: t,
    options: { bullet: { code: "002B" }, color: INK_2, paraSpaceAfter: 6,
               breakLine: i < items.length - 1 },
  }));
}

const TOTAL = 12;
let slideIdx = 0;
const next = (num, tag) => {
  slideIdx += 1;
  const s = pres.addSlide();
  frame(s, num, tag);
  footer(s, slideIdx, TOTAL);
  return s;
};

/* ─── 1. Title ─────────────────────────────────────────── */
{
  const s = next("00", "TARS · meeet.world");
  s.addText("TARS", {
    x: M, y: 0.95, w: 7.0, h: 1.6,
    fontFace: "Cambria", fontSize: 110, bold: true,
    color: INDIGO, charSpacing: -2, margin: 0,
  });
  s.addText("Agent Intelligence.", {
    x: M, y: 2.55, w: 9.0, h: 0.9,
    fontFace: "Cambria", fontSize: 36, color: INK_2, margin: 0,
  });
  body(s,
    "The local-first AI agent built for operators. Multi-LLM council, " +
    "Mac actions, signed receipts, $MEEET economy. Ships under the meeet.world brand.",
    { y: 3.5, w: 7.5, fontSize: 16 },
  );
  // Install pill
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 4.55, w: 6.5, h: 0.5,
    fill: { color: "11111A" }, line: { color: INDIGO, width: 1 },
  });
  s.addText(
    [
      { text: "$ ", options: { color: INDIGO, bold: true } },
      { text: "curl -fsSL meeet.world/install.sh | bash", options: { color: INK } },
    ],
    {
      x: M + 0.2, y: 4.55, w: 6.3, h: 0.5,
      fontFace: "Consolas", fontSize: 13, valign: "middle", margin: 0,
    },
  );
  s.addText("v9.0  ·  Phase L9 desktop scaffolded  ·  contract 1.1.0", {
    x: M, y: 5.2, w: 7.0, h: 0.3,
    fontFace: "Consolas", fontSize: 9, color: INK_3, charSpacing: 2.2, margin: 0,
  });
  // Stat grid (right side)
  const sx = 8.4, sy = 1.05, sw = 2.2, sh = 1.5, gap = 0.2;
  statCard(s, sx,            sy,            sw, sh, "28", "AI agents",     INDIGO);
  statCard(s, sx + sw + gap, sy,            sw, sh, "14", "Native skills", VIOLET);
  statCard(s, sx,            sy + sh + gap, sw, sh, "6",  "LLM providers", CYAN);
  statCard(s, sx + sw + gap, sy + sh + gap, sw, sh, "4",  "Domain packs",  VIOLET_S);
}

/* ─── 2. Problem ─────────────────────────────────────────── */
{
  const s = next("01", "PROBLEM");
  title(s, "Operators don't want chat.\nThey want an agent that does the work.", { fontSize: 38 });
  body(s,
    "Existing tools split the operator: an IDE-coupled assistant for code, a chat client for thinking, " +
    "a separate inbox triage tool, a macro for file moves. None of them touch the operating system or " +
    "run continuously in the background. And every cloud chat bills by the token without showing what " +
    "you're paying for.",
    { y: 3.8, w: 6.5, fontSize: 15 },
  );
  s.addText(
    bulletRuns([
      "Cursor lives in VS Code — code only, no system access.",
      "Claude Desktop is locked to one model and one window.",
      "ChatGPT desktop has no memory ledger or background mode.",
      "Macros automate one app, can't reason across mail / calendar / files.",
      "Cloud bills hidden in monthly statements, no per-action receipts.",
    ]),
    { x: 7.5, y: 3.0, w: 5.2, h: 4.0, fontFace: "Calibri", fontSize: 14, color: INK_2, paraSpaceAfter: 8, margin: 0 },
  );
}

/* ─── 3. Solution ────────────────────────────────────────── */
{
  const s = next("02", "SOLUTION");
  title(s, "Local-first cockpit.\nEight LLMs, four packs, one core.", { fontSize: 40 });
  s.addText("What it is", {
    x: M, y: 4.0, w: 5.5, h: 0.4,
    fontFace: "Cambria", fontSize: 16, bold: true, color: INK, margin: 0,
  });
  s.addText(
    bulletRuns([
      "FastAPI daemon on 127.0.0.1 the cockpit talks to.",
      "Memory ledger + cost ledger + receipt chain in SQLite.",
      "Multi-LLM council with two-voice deliberation per action.",
      "Mac Operator: sandbox-exec'd file/web/system actions.",
      "Pluggable domain packs + skill marketplace.",
    ]),
    { x: M, y: 4.5, w: 5.5, h: 2.6, fontFace: "Calibri", fontSize: 14, color: INK_2, paraSpaceAfter: 6, margin: 0 },
  );
  s.addText("What it isn't", {
    x: 7.0, y: 4.0, w: 5.5, h: 0.4,
    fontFace: "Cambria", fontSize: 16, bold: true, color: INK, margin: 0,
  });
  s.addText(
    bulletRuns([
      "Not a SaaS — your data stays on your machine.",
      "Not single-vendor — BYO any LLM key, any time.",
      "Not a chat box — actions, receipts, schedules, T2T.",
      "Not opinionated about your stack — MCP both ways.",
      "Not closed — MIT license on the core.",
    ]),
    { x: 7.0, y: 4.5, w: 5.5, h: 2.6, fontFace: "Calibri", fontSize: 14, color: INK_2, paraSpaceAfter: 6, margin: 0 },
  );
}

/* ─── 4. Demo ────────────────────────────────────────────── */
{
  const s = next("03", "DEMO");
  title(s, "Three things you couldn't do before.", { fontSize: 38 });
  const cards = [
    { tag: "DAILY BRIEF", title: "60-second briefing", body: "Calendar + unread mail + starred repos → one-page brief drafted by the council.", color: INDIGO },
    { tag: "MAC ACTION",  title: "Sort ~/Downloads",   body: "Sandbox-exec'd file moves with 10-minute undo. Signed receipt anchored.",   color: VIOLET },
    { tag: "T2T DEAL",    title: "Agent talks to agent", body: "Your TARS handshake-signs a deal with a peer's, settles in $MEEET escrow.", color: CYAN },
  ];
  const cardW = (W - 2 * M - 0.4) / 3, cardH = 3.4, cardY = 3.4;
  cards.forEach((c, i) => {
    const x = M + i * (cardW + 0.2);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cardY, w: cardW, h: cardH,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cardY, w: cardW, h: 0.04,
      fill: { color: c.color, transparency: 40 }, line: { color: c.color, width: 0 },
    });
    s.addText(c.tag, {
      x: x + 0.25, y: cardY + 0.25, w: cardW - 0.5, h: 0.3,
      fontFace: "Consolas", fontSize: 10, color: c.color, charSpacing: 2.4, margin: 0,
    });
    s.addText(c.title, {
      x: x + 0.25, y: cardY + 0.6, w: cardW - 0.5, h: 0.7,
      fontFace: "Cambria", fontSize: 20, bold: true, color: INK, margin: 0,
    });
    s.addText(c.body, {
      x: x + 0.25, y: cardY + 1.4, w: cardW - 0.5, h: 1.8,
      fontFace: "Calibri", fontSize: 13, color: INK_2, margin: 0,
    });
  });
}

/* ─── 5. Architecture ────────────────────────────────────── */
{
  const s = next("04", "ARCHITECTURE");
  title(s, "One spine.  Many devices.", { fontSize: 44 });
  // ASCII-ish architecture box
  const arch =
`┌────── meeet.world ──────┐
│ identity · billing      │
│ encrypted ingest 1.1.0  │
│ marketplace · relay     │
└─────▲─────────▲─────────┘
      │         │
      │ E2E ciphertext only
      │         │
┌─────┴───┐ ┌───┴──────┐
│ macOS   │ │ Windows  │
│ HOST    │ │ HOST     │
└────▲────┘ └──────────┘
     │ LAN bonjour
┌────┴────────────┐
│ iOS · Android   │
│ thin clients    │
└─────────────────┘`;
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: 3.0, w: 7.5, h: 4.0,
    fill: { color: "11111A" }, line: { color: LINE, width: 1 },
  });
  s.addText(arch, {
    x: M + 0.2, y: 3.1, w: 7.3, h: 3.8,
    fontFace: "Consolas", fontSize: 12, color: INK_2, valign: "top", margin: 0,
  });
  s.addText(
    bulletRuns([
      "Master keyring lives in macOS Keychain or Windows DPAPI.",
      "meeet.world stores ciphertext only — never plaintext.",
      "L5 sync envelope: XChaCha20-Poly1305 + X25519, contract 1.1.0.",
      "Mobile clients are thin: thin-client decryption, no backend on phone.",
      "Recovery seed (24-word BIP-39) shown once on first install.",
    ]),
    { x: 9.0, y: 3.0, w: 3.7, h: 4.0, fontFace: "Calibri", fontSize: 13, color: INK_2, paraSpaceAfter: 8, margin: 0 },
  );
}

/* ─── 6. Domain packs / roles ────────────────────────────── */
{
  const s = next("05", "DOMAIN PACKS / ROLES");
  title(s, "Same core.  Six crafts.", { fontSize: 44 });
  const roles = [
    { name: "Founder / CEO",  body: "Daily brief from KPI + deals + calendar.",      color: INDIGO },
    { name: "Trader",         body: "Markets, signals, risk across exchanges.",       color: VIOLET },
    { name: "Researcher",     body: "arXiv-aware. Citation-graph across projects.",   color: CYAN },
    { name: "Marketer",       body: "Outreach drafts in your voice.",                 color: VIOLET_S },
    { name: "Engineer",       body: "Repos indexed, PR queue, code RAG.",             color: SUCCESS },
    { name: "Operator",       body: "Generalist — full cockpit, all packs.",          color: AMBER },
  ];
  const cw = (W - 2 * M - 0.4) / 3, ch = 1.6, cy0 = 3.0;
  roles.forEach((r, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * (cw + 0.2), y = cy0 + row * (ch + 0.2);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cw, h: ch,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addText(r.name, {
      x: x + 0.2, y: y + 0.2, w: cw - 0.4, h: 0.3,
      fontFace: "Consolas", fontSize: 10, color: r.color, charSpacing: 2.4, margin: 0,
    });
    s.addText(r.body, {
      x: x + 0.2, y: y + 0.6, w: cw - 0.4, h: 0.9,
      fontFace: "Calibri", fontSize: 13, color: INK_2, margin: 0,
    });
  });
  // Custom row
  const cx = M, cy = cy0 + 2 * (ch + 0.2);
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx, y: cy, w: W - 2 * M, h: 1.2,
    fill: { color: "0F0F18" }, line: { color: INDIGO, width: 1, dashType: "dash" },
  });
  s.addText("CUSTOM ROLE  ·  AI Clone trained on you", {
    x: cx + 0.2, y: cy + 0.15, w: W - 2 * M - 0.4, h: 0.3,
    fontFace: "Consolas", fontSize: 10, color: INDIGO, charSpacing: 2.4, margin: 0,
  });
  s.addText(
    "Describe your work in 200-500 chars. TARS synthesises a system prompt overlay. " +
    "After 50 interactions, the AI Clone matches your tone and rhythm — locally.",
    { x: cx + 0.2, y: cy + 0.55, w: W - 2 * M - 0.4, h: 0.6,
      fontFace: "Calibri", fontSize: 13, color: INK_2, margin: 0 },
  );
}

/* ─── 7. $MEEET economy ──────────────────────────────────── */
{
  const s = next("06", "$MEEET ECONOMY");
  title(s, "Earn while your agent works.", { fontSize: 44 });
  s.addText(
    bulletRuns([
      "Every signed receipt feeds the reputation graph.",
      "Weekly $MEEET drops proportional to graph weight.",
      "T2T deals settle in $MEEET escrow off-chain, anchored to Solana memo.",
      "Pay subscriptions in $MEEET or USD — same price, same tier.",
      "Lifetime tier: 1,000 $MEEET allocated at signup.",
    ]),
    { x: M, y: 3.0, w: 6.5, h: 4.0, fontFace: "Calibri", fontSize: 14, color: INK_2, paraSpaceAfter: 8, margin: 0 },
  );
  // Loop steps
  s.addText("Loop", {
    x: 7.5, y: 3.0, w: 5.0, h: 0.4,
    fontFace: "Cambria", fontSize: 16, bold: true, color: INK_2, margin: 0,
  });
  const loop = [
    "1. Agent runs an action → signed receipt",
    "2. Receipt → reputation graph (weighted)",
    "3. meeet.world drops $MEEET weekly",
    "4. Operator spends $MEEET (sub, T2T, marketplace)",
    "5. Marketplace authors earn → new receipts",
  ];
  loop.forEach((step, i) => {
    const y = 3.55 + i * 0.55;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 7.5, y, w: 5.0, h: 0.45,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addText(step, {
      x: 7.65, y, w: 4.85, h: 0.45,
      fontFace: "Consolas", fontSize: 11, color: INK_2,
      charSpacing: 1.6, valign: "middle", margin: 0,
    });
  });
}

/* ─── 8. Security ────────────────────────────────────────── */
{
  const s = next("07", "SECURITY");
  title(s, "Local-first by default.\nCloud only when you say so.", { fontSize: 38 });
  const cards = [
    { label: "Local-first",     hint: "~/.tars/, never leaves" },
    { label: "Signed receipts", hint: "Ed25519 hash chain" },
    { label: "Open source",     hint: "MIT, on GitHub" },
    { label: "Sandbox-exec",    hint: "Mac actions whitelisted" },
    { label: "Auditable",       hint: "Solana memo anchor" },
    { label: "Edge LLM",        hint: "Ollama out of the box" },
  ];
  const cw = (W - 2 * M - 0.5) / 3, ch = 1.5, cy0 = 4.0;
  cards.forEach((c, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * (cw + 0.25), y = cy0 + row * (ch + 0.25);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cw, h: ch,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addText(c.label, {
      x: x + 0.25, y: y + 0.3, w: cw - 0.5, h: 0.5,
      fontFace: "Cambria", fontSize: 16, bold: true, color: INK, margin: 0,
    });
    s.addText(c.hint, {
      x: x + 0.25, y: y + 0.85, w: cw - 0.5, h: 0.3,
      fontFace: "Consolas", fontSize: 10, color: INK_3, charSpacing: 2.2, margin: 0,
    });
  });
}

/* ─── 9. Pricing ─────────────────────────────────────────── */
{
  const s = next("08", "PRICING");
  title(s, "Pay for cloud, not for thinking.", { fontSize: 40 });
  const tiers = [
    { name: "00 · Free",      price: "$0",       sub: "MIT · self-hosted", color: CYAN,    bullets: ["Single device, BYO LLM key", "Mac Operator + memory", "All 4 packs", "Single-voice council"] },
    { name: "01 · Pro",       price: "$19/mo",   sub: "or BYO $9/mo",      color: INDIGO,  bullets: ["$10 cloud LLM budget", "Two-voice council 100/d", "T2T 50 deals/mo + Clone", "$MEEET earn"], recommended: true },
    { name: "02 · Business",  price: "$79/seat", sub: "per month",         color: VIOLET,  bullets: ["$40/seat budget pooled", "Unlimited T2T + council", "Shared sessions + SSO", "Skill SDK + private mkt"] },
    { name: "03 · Lifetime",  price: "$299",     sub: "once",              color: VIOLET_S, bullets: ["All Pro forever", "1,000 $MEEET at signup", "Founders' edition badge", "Reserved T2T handle"] },
  ];
  const cw = (W - 2 * M - 0.45) / 4, ch = 4.2, cy = 3.1;
  tiers.forEach((t, i) => {
    const x = M + i * (cw + 0.15);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cy, w: cw, h: ch,
      fill: { color: t.recommended ? "151522" : "11111A" },
      line: { color: t.recommended ? t.color : LINE, width: t.recommended ? 1.5 : 1 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cy, w: cw, h: 0.04,
      fill: { color: t.color, transparency: t.recommended ? 0 : 50 },
      line: { color: t.color, width: 0 },
    });
    s.addText(t.name, {
      x: x + 0.2, y: cy + 0.2, w: cw - 0.4, h: 0.3,
      fontFace: "Consolas", fontSize: 10, color: t.color, charSpacing: 2.4, margin: 0,
    });
    s.addText(t.price, {
      x: x + 0.2, y: cy + 0.6, w: cw - 0.4, h: 0.7,
      fontFace: "Cambria", fontSize: 28, bold: true, color: INK, margin: 0,
    });
    s.addText(t.sub, {
      x: x + 0.2, y: cy + 1.3, w: cw - 0.4, h: 0.3,
      fontFace: "Consolas", fontSize: 9, color: INK_3, charSpacing: 2, margin: 0,
    });
    s.addText(
      t.bullets.map((b, bi) => ({
        text: b,
        options: { bullet: { code: "002B" }, color: INK_2, paraSpaceAfter: 4,
                   breakLine: bi < t.bullets.length - 1 },
      })),
      { x: x + 0.2, y: cy + 1.85, w: cw - 0.4, h: 2.2,
        fontFace: "Calibri", fontSize: 11, color: INK_2, margin: 0 },
    );
  });
}

/* ─── 10. Traction / roadmap ─────────────────────────────── */
{
  const s = next("09", "TRACTION");
  title(s, "Phase L shipped.  Phase M in flight.", { fontSize: 40 });
  s.addText("Shipped (Phase L)", {
    x: M, y: 3.5, w: 5.5, h: 0.4,
    fontFace: "Cambria", fontSize: 14, bold: true, color: INK, margin: 0,
  });
  s.addText(
    bulletRuns([
      "L1 — conversation layer + streaming SSE",
      "L2 — attachments + RAG with citations",
      "L4.1 — six TTS voice personas + mic dictation",
      "L8 — FTS5 cross-thread search + ⌘K palette",
      "L9 — desktop shell scaffolded; downloads manifest live",
      "L5 — pairing + real X25519 + recovery seed",
    ]),
    { x: M, y: 4.0, w: 5.5, h: 3.0, fontFace: "Calibri", fontSize: 13, color: INK_2, paraSpaceAfter: 6, margin: 0 },
  );
  s.addText("In flight (Phase M)", {
    x: 7.0, y: 3.5, w: 5.5, h: 0.4,
    fontFace: "Cambria", fontSize: 14, bold: true, color: INK, margin: 0,
  });
  s.addText(
    bulletRuns([
      "Tier entitlements + cloud-budget cap (P5)",
      "MLM → Entrepreneur rename (P6)",
      "Role selection + custom learnable role (P7)",
      "Machine vision via L2 attachments (P8)",
      "tars.meeet.world subdomain (spec done)",
      "Pitch deck + legal docs (this deck)",
    ]),
    { x: 7.0, y: 4.0, w: 5.5, h: 3.0, fontFace: "Calibri", fontSize: 13, color: INK_2, paraSpaceAfter: 6, margin: 0 },
  );
}

/* ─── 11. Team / handoff ─────────────────────────────────── */
{
  const s = next("10", "TEAM · HANDOFF");
  title(s, "Two agents.  One product.", { fontSize: 44 });
  const teams = [
    { tag: "CURSOR · functional", title: "Backend, contracts, Phase L roadmap.",
      body: "Owns Python core, MCP, council orchestrator, policy gate, playbook runner, vault, real adapters. Pins contracts in docs/contracts/. 270+ pytest tests green.",
      color: INDIGO },
    { tag: "CLAUDE · design", title: "Marketing, docs, brand, cockpit polish.",
      body: "Owns the v3 marketing surface, MASTER design system, FAQ / ToS / Privacy / Security docs, pitch, meeet.world brand integration, all UI polish on cockpit chrome.",
      color: CYAN },
  ];
  const cw = (W - 2 * M - 0.3) / 2, ch = 2.8, cy = 3.2;
  teams.forEach((t, i) => {
    const x = M + i * (cw + 0.3);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: cy, w: cw, h: ch,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addText(t.tag, {
      x: x + 0.3, y: cy + 0.25, w: cw - 0.6, h: 0.3,
      fontFace: "Consolas", fontSize: 10, color: t.color, charSpacing: 2.4, margin: 0,
    });
    s.addText(t.title, {
      x: x + 0.3, y: cy + 0.65, w: cw - 0.6, h: 0.7,
      fontFace: "Cambria", fontSize: 18, bold: true, color: INK, margin: 0,
    });
    s.addText(t.body, {
      x: x + 0.3, y: cy + 1.4, w: cw - 0.6, h: 1.3,
      fontFace: "Calibri", fontSize: 13, color: INK_2, margin: 0,
    });
  });
  // Brother row
  const by = 6.15;
  s.addShape(pres.shapes.RECTANGLE, {
    x: M, y: by, w: W - 2 * M, h: 0.9,
    fill: { color: "11111A" }, line: { color: LINE, width: 1 },
  });
  s.addText("BROTHER · meeet.world infra", {
    x: M + 0.3, y: by + 0.15, w: W - 2 * M - 0.6, h: 0.3,
    fontFace: "Consolas", fontSize: 10, color: INK_2, charSpacing: 2.4, margin: 0,
  });
  s.addText(
    "Stands up tars.meeet.world subdomain with end-to-end logging, runs the encrypted ingest relay, " +
    "manages wallet + magic-link auth + $MEEET marketplace. Spec at docs/contracts/TARS_SUBDOMAIN.md.",
    { x: M + 0.3, y: by + 0.45, w: W - 2 * M - 0.6, h: 0.5,
      fontFace: "Calibri", fontSize: 12, color: INK_2, margin: 0 },
  );
}

/* ─── 12. Ask / contact ──────────────────────────────────── */
{
  const s = next("11", "ASK");
  title(s, "Where we go from here.", { fontSize: 44 });
  s.addText(
    bulletRuns([
      "Investors — pre-seed open. Lifetime tier first 1,000 buyers covers runway.",
      "Operators — install today, MIT free tier, no commitment.",
      "Builders — skill SDK shipping in v9.2; 70/30 revenue share.",
      "Ecosystem — meeet.world account is the spine; partnership pings welcome.",
    ]),
    { x: M, y: 3.0, w: 7.5, h: 3.0, fontFace: "Calibri", fontSize: 14, color: INK_2, paraSpaceAfter: 8, margin: 0 },
  );
  // Contact stack
  const links = [
    { label: "meeet.world",                  url: "https://meeet.world" },
    { label: "github.com/meeet-world/tars",  url: "https://github.com/meeet-world/tars" },
    { label: "discord.gg/meeet",             url: "https://discord.gg/meeet" },
    { label: "hello@meeet.world",            url: "mailto:hello@meeet.world" },
  ];
  links.forEach((l, i) => {
    const y = 3.2 + i * 0.7;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 9.0, y, w: 3.7, h: 0.55,
      fill: { color: "11111A" }, line: { color: LINE, width: 1 },
    });
    s.addText(l.label, {
      x: 9.2, y, w: 3.3, h: 0.55,
      fontFace: "Consolas", fontSize: 11, color: INK_2,
      charSpacing: 2, valign: "middle", margin: 0,
      hyperlink: { url: l.url, tooltip: l.label },
    });
    s.addText("→", {
      x: 12.5, y, w: 0.2, h: 0.55,
      fontFace: "Consolas", fontSize: 12, color: INK_3, valign: "middle", margin: 0,
    });
  });
}

pres.writeFile({ fileName: OUT_PATH }).then(filename => {
  console.log("✓ Wrote " + filename);
});
