// SYNC: claude-w103-reports
/**
 * Wave 103 — shared types for the reports surface.
 *
 * Mirrors the backend dataclasses in
 * ``backend/core/reports/models.py``. Contract version 1.0.
 */

export type ReportKind = "pptx" | "docx" | "xlsx" | "pdf";

export type ReportStatus = "pending" | "rendering" | "done" | "failed";

export type FieldType =
  | "string"
  | "number"
  | "int"
  | "boolean"
  | "array"
  | "object";

export type FieldSchema = {
  type?: FieldType;
  label?: string;
  required?: boolean;
  description?: string;
  default?: unknown;
  items?: FieldType | unknown;
};

export type ReportTemplate = {
  id: string;
  name: string;
  slug: string;
  kind: ReportKind;
  schema: Record<string, FieldSchema>;
  template_path: string;
  description: string;
  is_builtin: boolean;
  created_at: number;
};

export type ReportRun = {
  id: string;
  template_id: string;
  inputs: Record<string, unknown>;
  output_path: string;
  output_kind: ReportKind | "";
  status: ReportStatus;
  recipient_emails: string[];
  created_at: number;
  generated_at: number | null;
  error: string | null;
  bytes_size: number | null;
  download_url?: string | null;
};

export type RunInputs = Record<string, unknown>;
