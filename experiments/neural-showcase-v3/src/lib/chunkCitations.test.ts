import { describe, expect, it } from "vitest";

import { splitChunkCitations } from "./chunkCitations";

describe("splitChunkCitations", () => {
  it("returns single text for empty", () => {
    expect(splitChunkCitations("", new Set())).toEqual([]);
  });

  it("leaves unknown bracket spans as text", () => {
    const parts = splitChunkCitations("see [chunk_9] maybe", new Set(["chunk_1"]));
    expect(parts).toEqual([
      { kind: "text", text: "see " },
      { kind: "text", text: "[chunk_9]" },
      { kind: "text", text: " maybe" },
    ]);
  });

  it("splits known citation into cite part", () => {
    const ids = new Set(["chunk_1", "chunk_2"]);
    const parts = splitChunkCitations("A [chunk_1] and [chunk_2].", ids);
    expect(parts).toEqual([
      { kind: "text", text: "A " },
      { kind: "cite", id: "chunk_1" },
      { kind: "text", text: " and " },
      { kind: "cite", id: "chunk_2" },
      { kind: "text", text: "." },
    ]);
  });

  it("supports hyphenated / uuid-like citation ids when in set", () => {
    const id = "chunk_a1b2c3";
    const parts = splitChunkCitations(`Ref [${id}] done`, new Set([id]));
    expect(parts).toEqual([
      { kind: "text", text: "Ref " },
      { kind: "cite", id },
      { kind: "text", text: " done" },
    ]);
  });

  it("handles adjacent citations", () => {
    const parts = splitChunkCitations("[chunk_1][chunk_2]", new Set(["chunk_1", "chunk_2"]));
    expect(parts).toEqual([
      { kind: "cite", id: "chunk_1" },
      { kind: "cite", id: "chunk_2" },
    ]);
  });

  it("handles text with no brackets", () => {
    expect(splitChunkCitations("plain", new Set())).toEqual([{ kind: "text", text: "plain" }]);
  });
});
