import { useLocale, useT, type Locale } from "@/lib/i18n";

/**
 * Bug #5 from docs/SYSTEM_AUDIT_2026-05-02.md — small, dependency-
 * free locale switcher. Exposes the supported locales as a native
 * ``<select>`` so we don't have to ship a dropdown library or
 * accessibility shim. Persists via ``useLocale()``.
 *
 * Visual style matches the footer link copy (font-mono-tech,
 * uppercase tracking, ink-2 colour) so it slots into existing
 * footer / nav surfaces without bespoke styling per host.
 */
export function LocaleSwitcher({ className = "" }: { className?: string }) {
  const { locale, setLocale, supported } = useLocale();
  const t = useT();

  return (
    <label
      className={`inline-flex items-center gap-2 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink-2 ${className}`}
    >
      <span aria-hidden>{t("locale.label")}:</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.currentTarget.value as Locale)}
        aria-label={t("locale.label")}
        className="rounded border border-line bg-bg-1 px-2 py-1 font-mono-tech text-[10px] uppercase tracking-[2px] text-ink focus:border-cyan-400 focus:outline-none"
      >
        {supported.map((loc) => (
          <option key={loc} value={loc}>
            {t(`locale.${loc}` as `locale.${typeof loc}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
