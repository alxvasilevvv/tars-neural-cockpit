// SYNC: claude-w102-files
/**
 * <CategorySidebar /> — Wave 102.
 *
 * Left rail of /files. Shows the standard catalogue (8 slots) plus
 * any custom slugs the operator has minted, with a per-bucket count
 * badge. "All files" sits at the top as the unfiltered view.
 */

import { Folder, Files as FilesIcon } from "lucide-react";

export interface CategoryDef {
  slug: string;
  label: string;
  blurb?: string;
}

export interface CategorySidebarProps {
  categories: CategoryDef[];
  /** Counts keyed by slug. ``__all__`` carries the unfiltered total. */
  counts: Record<string, number>;
  /** Currently active filter slug; empty string = All files. */
  active: string;
  onSelect: (slug: string) => void;
  /** Optional list of custom slugs (anything outside the standard set). */
  custom?: string[];
}

export function CategorySidebar({
  categories,
  counts,
  active,
  onSelect,
  custom = [],
}: CategorySidebarProps) {
  const total = counts["__all__"] ?? 0;
  return (
    <nav
      aria-label="File categories"
      className="flex w-full flex-col gap-1 text-sm"
    >
      <button
        type="button"
        onClick={() => onSelect("")}
        className={pillClass(active === "")}
      >
        <FilesIcon size={14} aria-hidden className="opacity-70" />
        <span className="flex-1 text-left">All files</span>
        <span className="text-xs text-ink-2">{total}</span>
      </button>
      <div className="my-2 h-px bg-line/40" aria-hidden />
      {categories.map((cat) => (
        <button
          key={cat.slug}
          type="button"
          onClick={() => onSelect(cat.slug)}
          className={pillClass(active === cat.slug)}
          title={cat.blurb}
        >
          <Folder size={14} aria-hidden className="opacity-60" />
          <span className="flex-1 text-left">{cat.label}</span>
          <span className="text-xs text-ink-2">{counts[cat.slug] ?? 0}</span>
        </button>
      ))}
      {custom.length > 0 && (
        <>
          <div className="mt-2 px-2 text-[10px] uppercase tracking-wider text-ink-2">
            Custom
          </div>
          {custom.map((slug) => (
            <button
              key={slug}
              type="button"
              onClick={() => onSelect(slug)}
              className={pillClass(active === slug)}
            >
              <Folder size={14} aria-hidden className="opacity-60" />
              <span className="flex-1 text-left">{slug}</span>
              <span className="text-xs text-ink-2">{counts[slug] ?? 0}</span>
            </button>
          ))}
        </>
      )}
    </nav>
  );
}

function pillClass(isActive: boolean): string {
  const base =
    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 transition-colors";
  return isActive
    ? `${base} bg-accent/15 text-ink ring-1 ring-accent/40`
    : `${base} text-ink-1 hover:bg-bg-1`;
}
