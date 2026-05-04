import { useDocumentMeta } from "@/lib/meta";
import { useT } from "@/lib/i18n";
import { Pricing } from "@/components/Pricing";

/** Standalone `/pricing` — same block as on `/`, avoids SPA 404 on deep links. */
export function PricingPage() {
  const t = useT();
  useDocumentMeta({
    title: `${t("pricing.title")} · TARS`,
    description: t("pricing.description"),
  });
  return <Pricing />;
}
