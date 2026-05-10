// SYNC: claude-w102-files
/**
 * <Files /> — Wave 102.
 *
 * Document & file management surface at /files. B2B operators land
 * hundreds of PDFs / decks / contracts via the attachment ingest
 * pipeline; this page is the single browser for managing them
 * outside any specific chat thread.
 *
 * Layout:
 *   [ Header (title + count + Upload + view toggle) ]
 *   [ Sidebar (categories + counts) | Search + filter chips + grid/list ]
 *   [ Bulk actions toolbar — appears when ≥1 file is selected ]
 *   [ Preview modal — opened by clicking a file ]
 *
 * All state is local; the FE keeps the canonical selection set and
 * sync to /api/files via small fetches. No SSE / WS — file mutations
 * are user-initiated and re-render-on-success is good enough.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { motion } from "framer-motion";
import {
  FolderOpen,
  LayoutGrid,
  List,
  Search,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { useDocumentMeta } from "@/lib/meta";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { CategorySidebar } from "@/components/files/CategorySidebar";
import { FileGrid } from "@/components/files/FileGrid";
import { FileList } from "@/components/files/FileList";
import { FilePreview } from "@/components/files/FilePreview";
import { BulkUploadDropzone } from "@/components/files/BulkUploadDropzone";
import { BulkActionsToolbar } from "@/components/files/BulkActionsToolbar";
import { TagChipEditor } from "@/components/files/TagChipEditor";
import type {
  CategoryDef,
  FileItem,
  FilesStats,
} from "@/components/files/types";

type ViewMode = "grid" | "list";
type SortMode =
  | "created_desc"
  | "created_asc"
  | "size_desc"
  | "size_asc"
  | "filename_asc"
  | "filename_desc";

const STANDARD_FALLBACK: CategoryDef[] = [
  { slug: "contracts",       label: "Contracts" },
  { slug: "decks",           label: "Decks" },
  { slug: "reports",         label: "Reports" },
  { slug: "research",        label: "Research" },
  { slug: "legal",           label: "Legal" },
  { slug: "correspondence",  label: "Correspondence" },
  { slug: "code",            label: "Code" },
  { slug: "uncategorized",   label: "Uncategorized" },
];

export function Files() {
  useDocumentMeta({
    title: "Files — TARS",
    description:
      "Browse, tag and manage every PDF, deck, report and attachment ingested by TARS.",
  });

  const params = new URLSearchParams(
    typeof window !== "undefined" ? window.location.search : "",
  );
  const initialUploadOpen = params.get("upload") === "1";
  const initialFocusSearch = params.get("focus") === "search";

  const [view, setView] = useState<ViewMode>("grid");
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [stats, setStats] = useState<FilesStats | null>(null);
  const [categories, setCategories] = useState<CategoryDef[]>(STANDARD_FALLBACK);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortMode>("created_desc");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [showUpload, setShowUpload] = useState(initialUploadOpen);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);

  // Initial focus when arriving via the Cmd+K "Search files" command.
  useEffect(() => {
    if (initialFocusSearch && searchRef.current) {
      searchRef.current.focus();
    }
  }, [initialFocusSearch]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    const search = new URLSearchParams();
    search.set("limit", "200");
    if (activeCategory) search.set("category", activeCategory);
    if (pinnedOnly) search.set("pinned", "true");
    if (query.trim()) search.set("query", query.trim());
    if (!query.trim()) search.set("sort", sort);
    try {
      const [listRes, statsRes] = await Promise.all([
        fetch(`/api/files?${search.toString()}`),
        fetch("/api/files/stats"),
      ]);
      if (!listRes.ok) throw new Error(`list ${listRes.status}`);
      const listBody = await listRes.json();
      setFiles(listBody.items ?? []);
      if (statsRes.ok) {
        const sb = await statsRes.json();
        setStats(sb);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [activeCategory, pinnedOnly, query, sort]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Pull category catalogue once (best-effort).
  useEffect(() => {
    fetch("/api/files/categories")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((b) => {
        if (Array.isArray(b.categories) && b.categories.length > 0) {
          setCategories(b.categories);
        }
      })
      .catch(() => {});
  }, []);

  const counts = useMemo<Record<string, number>>(() => {
    const out: Record<string, number> = { __all__: stats?.total_count ?? 0 };
    if (stats?.by_category) {
      for (const [slug, n] of Object.entries(stats.by_category)) {
        out[slug] = n;
      }
    }
    return out;
  }, [stats]);

  const customSlugs = useMemo<string[]>(() => {
    if (!stats?.by_category) return [];
    const standard = new Set(categories.map((c) => c.slug));
    return Object.keys(stats.by_category).filter((s) => !standard.has(s));
  }, [categories, stats]);

  // Selection helpers ----------------------------------------------------
  const toggle = (id: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleAll = (next: boolean) => {
    if (next) setSelected(new Set(files.map((f) => f.id)));
    else setSelected(new Set());
  };
  const clearSelection = () => setSelected(new Set());

  // Bulk handlers --------------------------------------------------------
  const bulkTag = async (tag: string) => {
    await fetch("/api/files/bulk-tag", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        ids: Array.from(selected),
        tags: [tag],
        operation: "add",
      }),
    });
    clearSelection();
    await reload();
  };
  const bulkCategorize = async (slug: string) => {
    await fetch("/api/files/bulk-categorize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ids: Array.from(selected), category: slug }),
    });
    clearSelection();
    await reload();
  };
  const bulkPin = async (next: boolean) => {
    for (const id of Array.from(selected)) {
      await fetch(`/api/files/${id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ pinned: next }),
      });
    }
    clearSelection();
    await reload();
  };
  const bulkDelete = async (reason: string) => {
    await fetch("/api/files/bulk-delete", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ids: Array.from(selected), reason }),
    });
    clearSelection();
    await reload();
  };

  // Single-file handlers -------------------------------------------------
  const onMenu = (file: FileItem) => setPreview(file);
  const onOpen = (file: FileItem) => setPreview(file);
  const updateTags = async (file: FileItem, tags: string[]) => {
    await fetch(`/api/files/${file.id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    await reload();
    setPreview((cur) => (cur && cur.id === file.id ? { ...cur, tags } : cur));
  };

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-32 pt-8">
      <Breadcrumbs items={[{ label: "Files" }]} />

      <header className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-2xl text-ink">Files</h1>
          <span className="text-sm text-ink-2">
            {stats ? `${stats.total_count} total · ${formatBytes(stats.total_bytes)}` : "loading…"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowUpload((v) => !v)}
            className="flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-sm text-bg-0"
          >
            <UploadCloud size={14} aria-hidden /> Upload
          </button>
          <button
            type="button"
            onClick={reload}
            className="flex items-center gap-1 rounded-md border border-line/60 px-2 py-1.5 text-xs text-ink-1 hover:border-accent hover:text-accent"
            aria-label="Reload"
          >
            <RefreshCw size={12} aria-hidden /> Reload
          </button>
          <div className="flex overflow-hidden rounded-md border border-line/60">
            <button
              type="button"
              onClick={() => setView("grid")}
              className={`px-2 py-1.5 text-xs ${view === "grid" ? "bg-accent/15 text-accent" : "text-ink-2 hover:text-ink"}`}
              aria-pressed={view === "grid"}
              aria-label="Grid view"
            >
              <LayoutGrid size={12} aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={`px-2 py-1.5 text-xs ${view === "list" ? "bg-accent/15 text-accent" : "text-ink-2 hover:text-ink"}`}
              aria-pressed={view === "list"}
              aria-label="List view"
            >
              <List size={12} aria-hidden />
            </button>
          </div>
        </div>
      </header>

      {showUpload && (
        <motion.section
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4"
        >
          <BulkUploadDropzone
            category={activeCategory || undefined}
            onUploaded={async () => {
              await reload();
            }}
          />
        </motion.section>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[220px_1fr]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <CategorySidebar
            categories={categories}
            counts={counts}
            active={activeCategory}
            onSelect={(slug) => {
              setActiveCategory(slug);
              clearSelection();
            }}
            custom={customSlugs}
          />
        </aside>

        <section>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="flex flex-1 items-center gap-2 rounded-md border border-line/60 bg-bg-1 px-2 py-1.5">
              <Search size={12} className="text-ink-2" aria-hidden />
              <input
                ref={searchRef}
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search every file (FTS5)…"
                className="min-w-0 flex-1 bg-transparent text-sm text-ink placeholder:text-ink-2 focus:outline-none"
                aria-label="Search files"
              />
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortMode)}
              disabled={Boolean(query.trim())}
              className="rounded-md border border-line/60 bg-bg-1 px-2 py-1.5 text-xs text-ink"
              aria-label="Sort files by"
            >
              <option value="created_desc">Newest</option>
              <option value="created_asc">Oldest</option>
              <option value="size_desc">Largest</option>
              <option value="size_asc">Smallest</option>
              <option value="filename_asc">Name A→Z</option>
              <option value="filename_desc">Name Z→A</option>
            </select>
            <label className="flex items-center gap-1 text-xs text-ink-2">
              <input
                type="checkbox"
                checked={pinnedOnly}
                onChange={(e) => setPinnedOnly(e.target.checked)}
                className="h-3.5 w-3.5 accent-accent"
              />
              Pinned only
            </label>
          </div>

          {error && (
            <div className="mb-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex h-48 items-center justify-center text-sm text-ink-2">
              <FolderOpen size={16} className="mr-2" aria-hidden /> Loading…
            </div>
          ) : view === "grid" ? (
            <FileGrid
              files={files}
              selectedIds={selected}
              onToggle={toggle}
              onOpen={onOpen}
              onMenu={onMenu}
            />
          ) : (
            <FileList
              files={files}
              selectedIds={selected}
              onToggle={toggle}
              onToggleAll={toggleAll}
              onOpen={onOpen}
              onMenu={onMenu}
            />
          )}
        </section>
      </div>

      <BulkActionsToolbar
        count={selected.size}
        onClear={clearSelection}
        onAddTag={bulkTag}
        onCategorize={bulkCategorize}
        onPin={bulkPin}
        onDelete={bulkDelete}
        categories={categories.map((c) => ({ slug: c.slug, label: c.label }))}
      />

      {preview && (
        <FilePreview
          file={preview}
          onClose={() => setPreview(null)}
        />
      )}
      {preview && (
        <div className="fixed bottom-4 right-4 z-40 w-72 rounded-md border border-line/60 bg-bg-1/95 p-3 shadow-lg">
          <h3 className="text-xs font-semibold text-ink">Tags</h3>
          <div className="mt-2">
            <TagChipEditor
              tags={preview.tags}
              onChange={(next) => updateTags(preview, next)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export default Files;
