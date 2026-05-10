// SYNC: claude-w103-reports
/**
 * Wave 103 — single template card in the templates grid.
 *
 * Displays the name, kind badge, description, and a "Generate"
 * action that opens the Reports page modal. Pure presentation; the
 * parent owns the modal state.
 */

import { motion } from "framer-motion";
import { FileText, FileSpreadsheet, FileImage, FileCode } from "lucide-react";
import type { ReportKind, ReportTemplate } from "./types";

const KIND_ICON: Record<ReportKind, typeof FileText> = {
  pptx: FileImage,
  docx: FileText,
  xlsx: FileSpreadsheet,
  pdf: FileCode,
};

const KIND_LABEL: Record<ReportKind, string> = {
  pptx: "Slides",
  docx: "Document",
  xlsx: "Spreadsheet",
  pdf: "PDF",
};

type Props = {
  template: ReportTemplate;
  onSelect: (t: ReportTemplate) => void;
};

export function TemplateCard({ template, onSelect }: Props) {
  const Icon = KIND_ICON[template.kind] ?? FileText;
  return (
    <motion.button
      type="button"
      onClick={() => onSelect(template)}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="group relative flex w-full flex-col gap-3 rounded-md border border-line bg-bg-1/40 p-4 text-left backdrop-blur-sm transition-colors hover:border-[var(--brand-cyan)] hover:bg-bg-1/70 focus:outline-none focus:ring-2 focus:ring-[var(--brand-cyan)]/40"
      data-template-slug={template.slug}
      aria-label={`Generate ${template.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-line bg-bg-0/40">
          <Icon size={18} aria-hidden style={{ color: "var(--brand-cyan)" }} />
        </div>
        <span className="rounded-sm border border-line px-2 py-0.5 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-2">
          {KIND_LABEL[template.kind] ?? template.kind}
        </span>
      </div>
      <div>
        <h3 className="text-[15px] font-medium leading-tight text-ink">
          {template.name}
        </h3>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-2">
          {template.description ||
            "No description provided. Click to view the input schema."}
        </p>
      </div>
      <div className="mt-auto flex items-center justify-between border-t border-line/60 pt-2 font-mono-tech text-[10px] uppercase tracking-[1.5px] text-ink-3">
        <span>{template.slug}</span>
        {template.is_builtin && <span>Built-in</span>}
      </div>
    </motion.button>
  );
}
