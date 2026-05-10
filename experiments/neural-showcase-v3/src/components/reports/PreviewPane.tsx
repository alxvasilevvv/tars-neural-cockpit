// SYNC: claude-w103-reports
/**
 * Wave 103 — preview pane shown inside the generate modal.
 *
 * Uses ``srcDoc`` so we never round-trip a server-side preview URL.
 * Empty state shows a quiet hint until the operator clicks Preview.
 */

import { Eye } from "lucide-react";

type Props = {
  html: string | null;
  loading: boolean;
};

export function PreviewPane({ html, loading }: Props) {
  if (loading) {
    return (
      <div className="flex h-[260px] items-center justify-center rounded-md border border-line bg-bg-1/30 text-[12px] text-ink-3">
        Rendering preview…
      </div>
    );
  }
  if (!html) {
    return (
      <div className="flex h-[260px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-line bg-bg-1/20 text-ink-3">
        <Eye size={20} aria-hidden style={{ color: "var(--brand-cyan)" }} />
        <p className="text-[12px]">Click Preview to render this template.</p>
      </div>
    );
  }
  return (
    <iframe
      title="Report preview"
      srcDoc={html}
      className="h-[360px] w-full rounded-md border border-line bg-white"
      sandbox=""
    />
  );
}
