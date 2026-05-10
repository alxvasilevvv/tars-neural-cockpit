// SYNC: claude-w102-files

/**
 * Shared types for /files. Mirrors the backend ``_record_to_card``
 * envelope from ``web_extras.routers.files``.
 */
export interface FileItem {
  id: string;
  thread_id: string;
  message_id: string | null;
  mime: string;
  filename: string | null;
  bytes_total: number;
  char_count: number;
  extracted_text_preview: string;
  status: string;
  error: string | null;
  content_hash: string | null;
  created_at: number;
  meta: Record<string, unknown>;
  tags: string[];
  category: string;
  pinned: boolean;
  deleted_at: number | null;
  extension: string;
  thumbnail_url: string | null;
  preview_url: string;
  match_snippet?: string;
}

export interface FilesStats {
  total_count: number;
  total_bytes: number;
  by_category: Record<string, number>;
  by_extension: Record<string, number>;
  deleted_count: number;
  pinned_count: number;
}

export interface CategoryDef {
  slug: string;
  label: string;
  blurb?: string;
}
