/**
 * Split assistant message text so that bracket citations like
 * `[chunk_1]` become navigable pills when they match a known
 * `citation_id` from persisted or live retrieval sources.
 */

const BRACKET_TOKEN_RE = /\[([^\]]+)\]/g;

export type ChunkCitationPart =
  | { kind: "text"; text: string }
  | { kind: "cite"; id: string };

/**
 * Walk ``content`` left-to-right. Any ``[token]`` where ``token`` is in
 * ``citationIds`` becomes a ``cite`` part; otherwise the full bracket
 * span is left as plain ``text`` (model hallucination or future format).
 */
export function splitChunkCitations(
  content: string,
  citationIds: Set<string>,
): ChunkCitationPart[] {
  if (!content) return [];
  const out: ChunkCitationPart[] = [];
  let last = 0;
  const re = new RegExp(BRACKET_TOKEN_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    const start = m.index;
    const full = m[0]!;
    const token = m[1]!;
    if (start > last) {
      out.push({ kind: "text", text: content.slice(last, start) });
    }
    if (citationIds.has(token)) {
      out.push({ kind: "cite", id: token });
    } else {
      out.push({ kind: "text", text: full });
    }
    last = start + full.length;
  }
  if (last < content.length) {
    out.push({ kind: "text", text: content.slice(last) });
  }
  return out;
}
