import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { Compare } from "@/components/Compare";

/** Standalone `/compare` — same block as on `/`. */
export function ComparePage() {
  const t = useT();
  useDocumentMeta({
    title: `${t("compare.title")} · TARS`,
    description: t("compare.description"),
  });
  return <Compare />;
}
