// SYNC: claude-w102-files
/**
 * <TagChipEditor /> — Wave 102.
 *
 * Inline tag editor used by /files. Renders existing tags as
 * dismissible chips and a small input for adding new ones. Tags are
 * free-form strings up to 32 chars; we trim + dedupe locally and
 * push the canonical list up via `onChange` so the parent can fire
 * the PATCH.
 */

import { useState, type KeyboardEvent } from "react";
import { X, Plus } from "lucide-react";

export interface TagChipEditorProps {
  tags: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  /** When true the editor is read-only (chips render but no input). */
  readOnly?: boolean;
  className?: string;
}

const MAX_TAG_LEN = 32;
const MAX_TAGS = 32;

export function TagChipEditor({
  tags,
  onChange,
  placeholder = "Add tag…",
  readOnly = false,
  className = "",
}: TagChipEditorProps) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const t = raw.trim().slice(0, MAX_TAG_LEN);
    if (!t) return;
    if (tags.some((existing) => existing.toLowerCase() === t.toLowerCase())) {
      setDraft("");
      return;
    }
    if (tags.length >= MAX_TAGS) return;
    onChange([...tags, t]);
    setDraft("");
  };

  const remove = (idx: number) => {
    onChange(tags.filter((_, i) => i !== idx));
  };

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit(draft);
      return;
    }
    if (event.key === "Backspace" && !draft && tags.length > 0) {
      event.preventDefault();
      remove(tags.length - 1);
    }
  };

  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 rounded-md border border-line/60 bg-bg-1/60 p-1.5 ${className}`}
      role="group"
      aria-label="Tag editor"
    >
      {tags.map((tag, i) => (
        <span
          key={`${tag}-${i}`}
          className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent"
        >
          <span>{tag}</span>
          {!readOnly && (
            <button
              type="button"
              onClick={() => remove(i)}
              aria-label={`Remove tag ${tag}`}
              className="text-accent/80 hover:text-accent"
            >
              <X size={11} aria-hidden />
            </button>
          )}
        </span>
      ))}
      {!readOnly && (
        <span className="inline-flex items-center gap-1">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value.slice(0, MAX_TAG_LEN))}
            onKeyDown={onKey}
            onBlur={() => commit(draft)}
            placeholder={placeholder}
            className="min-w-[7ch] flex-1 bg-transparent px-1 py-0.5 text-xs text-ink placeholder:text-ink-2 focus:outline-none"
            aria-label="Add new tag"
          />
          {draft && (
            <button
              type="button"
              onClick={() => commit(draft)}
              className="text-ink-2 hover:text-accent"
              aria-label="Confirm tag"
            >
              <Plus size={12} aria-hidden />
            </button>
          )}
        </span>
      )}
    </div>
  );
}
