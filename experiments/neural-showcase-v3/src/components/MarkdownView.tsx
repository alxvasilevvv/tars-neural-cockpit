import { useMemo } from "react";

/**
 * MarkdownView — minimal Markdown renderer.
 *
 * Handles the subset used in our legal/security docs:
 *   # / ## / ### / #### headings
 *   **bold**, *italic*, `inline code`
 *   [link text](url) — http(s) auto-target=_blank
 *   - lists, 1. ordered lists
 *   > blockquotes
 *   --- horizontal rules
 *   | table | rows |
 *   ``` fenced code blocks
 *   plain paragraphs
 *
 * Pure React, no dangerouslySetInnerHTML, no external deps.
 * Pass `source={MARKDOWN_STRING}` and the component renders styled
 * prose using Tailwind tokens already in the project.
 */

interface Props {
  source: string;
  className?: string;
}

type Block =
  | { type: "h"; level: number; text: string }
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "quote"; text: string }
  | { type: "hr" }
  | { type: "code"; lang: string; body: string }
  | { type: "table"; header: string[]; rows: string[][] };

function parse(source: string): Block[] {
  const lines = source.split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // Fenced code
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        body.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      out.push({ type: "code", lang, body: body.join("\n") });
      continue;
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line)) {
      out.push({ type: "hr" });
      i++;
      continue;
    }

    // Headings
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      out.push({ type: "h", level: h[1].length, text: h[2] });
      i++;
      continue;
    }

    // Blockquote — fold consecutive `> ` lines
    if (line.startsWith("> ")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) {
        buf.push(lines[i].slice(2));
        i++;
      }
      out.push({ type: "quote", text: buf.join(" ") });
      continue;
    }

    // Unordered list
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ""));
        i++;
      }
      out.push({ type: "ul", items });
      continue;
    }

    // Ordered list
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i++;
      }
      out.push({ type: "ol", items });
      continue;
    }

    // Table — header row | --- | data rows
    if (line.includes("|") && i + 1 < lines.length && /^\|?[\s|:-]+\|?$/.test(lines[i + 1])) {
      const splitRow = (l: string) =>
        l
          .replace(/^\||\|$/g, "")
          .split("|")
          .map(c => c.trim());
      const header = splitRow(line);
      const rows: string[][] = [];
      i += 2; // skip header + separator
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push({ type: "table", header, rows });
      continue;
    }

    // Empty line — skip
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph — fold consecutive non-empty non-special lines
    const buf: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^#{1,4}\s/.test(lines[i]) &&
      !lines[i].startsWith("```") &&
      !lines[i].startsWith("> ") &&
      !/^[-*]\s+/.test(lines[i]) &&
      !/^\d+\.\s+/.test(lines[i]) &&
      !/^---+\s*$/.test(lines[i])
    ) {
      buf.push(lines[i]);
      i++;
    }
    if (buf.length) out.push({ type: "p", text: buf.join(" ") });
  }
  return out;
}

/** Inline formatting: **bold**, *italic*, `code`, [link](url) */
function renderInline(text: string): React.ReactNode {
  // Tokenise — order matters: code → link → bold → italic
  const out: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < text.length) {
    // Inline code
    if (text[i] === "`") {
      const end = text.indexOf("`", i + 1);
      if (end > i) {
        out.push(
          <code
            key={key++}
            className="rounded bg-bg-2 px-1 py-0.5 font-mono text-[0.92em] text-ink"
          >
            {text.slice(i + 1, end)}
          </code>,
        );
        i = end + 1;
        continue;
      }
    }
    // Link [text](url)
    if (text[i] === "[") {
      const close = text.indexOf("]", i + 1);
      if (close > i && text[close + 1] === "(") {
        const paren = text.indexOf(")", close + 2);
        if (paren > close) {
          const label = text.slice(i + 1, close);
          const href = text.slice(close + 2, paren);
          const ext = /^https?:/.test(href);
          out.push(
            <a
              key={key++}
              href={href}
              {...(ext ? { target: "_blank", rel: "noopener" } : {})}
              className="text-accent underline-offset-4 transition-colors hover:underline"
            >
              {renderInline(label)}
            </a>,
          );
          i = paren + 1;
          continue;
        }
      }
    }
    // Bold **
    if (text[i] === "*" && text[i + 1] === "*") {
      const end = text.indexOf("**", i + 2);
      if (end > i) {
        out.push(
          <strong key={key++} className="font-medium text-ink">
            {renderInline(text.slice(i + 2, end))}
          </strong>,
        );
        i = end + 2;
        continue;
      }
    }
    // Italic *
    if (text[i] === "*" && text[i + 1] !== "*") {
      const end = text.indexOf("*", i + 1);
      if (end > i) {
        out.push(
          <em key={key++} className="italic">
            {renderInline(text.slice(i + 1, end))}
          </em>,
        );
        i = end + 1;
        continue;
      }
    }
    // Plain — gather until next special char
    let j = i;
    while (j < text.length && !"`[*".includes(text[j])) j++;
    out.push(<span key={key++}>{text.slice(i, j)}</span>);
    i = j === i ? i + 1 : j;
  }
  return out;
}

export function MarkdownView({ source, className }: Props) {
  const blocks = useMemo(() => parse(source), [source]);
  return (
    <div className={`mx-auto max-w-[64ch] ${className ?? ""}`}>
      {blocks.map((b, i) => {
        switch (b.type) {
          case "h": {
            const sizes = {
              1: "mt-0 mb-6 text-[clamp(2rem,4.4vw,3.2rem)] leading-[1.05] tracking-[-0.02em]",
              2: "mt-10 mb-4 text-[24px] leading-[1.2] tracking-[-0.01em]",
              3: "mt-7 mb-3 text-[18px] leading-[1.3] tracking-[-0.005em]",
              4: "mt-5 mb-2 text-[15px] leading-[1.35]",
            }[b.level as 1 | 2 | 3 | 4];
            const Tag = `h${b.level}` as "h1" | "h2" | "h3" | "h4";
            // Emit anchor IDs on h2/h3 so deep-link / TOC jumps work
            // (`/changelog#shipped`). h1 is the document title, no anchor.
            const id = b.level >= 2 ? slugifyHeading(b.text) : undefined;
            return (
              <Tag
                key={i}
                id={id}
                className={`group relative scroll-mt-24 font-display font-medium text-ink ${sizes}`}
              >
                {renderInline(b.text)}
                {id && (
                  <a
                    href={`#${id}`}
                    aria-label={`Anchor link · ${b.text}`}
                    className="ml-2 inline-block align-middle font-mono-tech text-[13px] text-ink-3 opacity-0 transition-opacity duration-150 hover:text-accent group-hover:opacity-100 focus-visible:opacity-100"
                  >
                    #
                  </a>
                )}
              </Tag>
            );
          }
          case "p":
            return (
              <p key={i} className="mb-4 text-[14.5px] leading-[1.7] text-ink-2">
                {renderInline(b.text)}
              </p>
            );
          case "ul":
            return (
              <ul key={i} className="mb-5 space-y-2 text-[14.5px] leading-[1.65] text-ink-2">
                {b.items.map((it, j) => (
                  <li key={j} className="grid grid-cols-[14px_1fr] items-baseline gap-2">
                    <span className="text-accent">·</span>
                    <span>{renderInline(it)}</span>
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={i} className="mb-5 space-y-2 text-[14.5px] leading-[1.65] text-ink-2">
                {b.items.map((it, j) => (
                  <li
                    key={j}
                    className="grid grid-cols-[24px_1fr] items-baseline gap-2 font-mono-tech"
                  >
                    <span className="tabular-nums text-accent">{j + 1}.</span>
                    <span className="font-sans">{renderInline(it)}</span>
                  </li>
                ))}
              </ol>
            );
          case "quote":
            return (
              <blockquote
                key={i}
                className="mb-5 border-l-2 pl-4 text-[14px] italic leading-[1.6] text-ink-2"
                style={{ borderColor: "var(--color-meeet-violet, #8B5CF6)" }}
              >
                {renderInline(b.text)}
              </blockquote>
            );
          case "hr":
            return (
              <hr
                key={i}
                className="my-10 border-0 border-t border-line"
                aria-hidden
              />
            );
          case "code":
            return (
              <pre
                key={i}
                className="mb-5 overflow-x-auto rounded-md border border-line bg-bg-1/70 p-4 font-mono text-[12.5px] leading-[1.55] text-ink-2"
              >
                <code className={`language-${b.lang || "text"}`}>{b.body}</code>
              </pre>
            );
          case "table":
            return (
              <div
                key={i}
                className="mb-6 overflow-x-auto rounded-md border border-line"
              >
                <table className="w-full border-collapse text-left">
                  <thead className="border-b border-line bg-bg-1/60">
                    <tr>
                      {b.header.map((h, j) => (
                        <th
                          key={j}
                          className="px-4 py-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2px] text-ink-3"
                        >
                          {renderInline(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, ri) => (
                      <tr
                        key={ri}
                        className="border-b border-line last:border-b-0"
                      >
                        {row.map((cell, ci) => (
                          <td
                            key={ci}
                            className="px-4 py-2.5 text-[13px] leading-[1.5] text-ink-2"
                          >
                            {renderInline(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}

/**
 * slugifyHeading — produce a URL-safe anchor id from a heading.
 * Lowercase, ASCII letters/digits/dashes only, deduped dashes.
 * Cyrillic and other non-ASCII characters are stripped — pages with
 * RU headings simply won't get auto-deep-link anchors yet, which is
 * acceptable until the docs side starts emitting localised URLs.
 */
export function slugifyHeading(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * extractHeadings — tiny helper for callers that want a TOC sidebar.
 * Returns one entry per `## ` and `### ` heading found in `source`,
 * with level + slug + text. Skips h1 (document title).
 */
export function extractHeadings(
  source: string,
): { level: 2 | 3; text: string; id: string }[] {
  const lines = source.split(/\r?\n/);
  const out: { level: 2 | 3; text: string; id: string }[] = [];
  let inFence = false;
  for (const raw of lines) {
    const line = raw;
    if (line.startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const m = /^(##|###)\s+(.+?)\s*$/.exec(line);
    if (!m) continue;
    const level = m[1].length === 2 ? 2 : 3;
    const text = m[2].replace(/[`*_]/g, "").trim();
    if (!text) continue;
    out.push({ level: level as 2 | 3, text, id: slugifyHeading(text) });
  }
  return out;
}
