import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { FAQ } from "@/components/FAQ";

/** Standalone `/faq` — same block as on `/`. */
export function FAQPage() {
  const t = useT();
  useDocumentMeta({
    title: `${t("faq.title")} · TARS`,
    description: t("faq.description"),
  });
  return <FAQ />;
}
