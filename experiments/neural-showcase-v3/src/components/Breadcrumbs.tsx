/**
 * Breadcrumbs — small inline navigation strip rendered at the top of
 * deep-linked pages (workshop / enterprise / compliance). Uses the same
 * mono-tech tracking as the rest of the marketing surface so it sits
 * visually under the global nav without competing for attention.
 *
 * Wave 83 — Workshop FE polish. Pure / dependency-free / a11y-correct
 * (`<nav aria-label="Breadcrumb">` + ordered list, current page is
 * `aria-current="page"` and renders as plain text instead of a link).
 */

import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  /** Omit `to` for the current/leaf page — it renders as plain text. */
  to?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  /** Optional extra className on the outer <nav>. */
  className?: string;
}

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  if (items.length === 0) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className={`font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-3 ${className ?? ""}`}
    >
      <ol className="flex flex-wrap items-center gap-1.5">
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;
          return (
            <li
              key={`${item.label}-${idx}`}
              className="flex items-center gap-1.5"
            >
              {item.to && !isLast ? (
                <Link
                  to={item.to}
                  className="rounded-sm text-ink-2 transition-colors duration-150 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-0 focus-visible:ring-[var(--brand-indigo)]"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? "page" : undefined}
                  className={isLast ? "text-ink" : "text-ink-2"}
                >
                  {item.label}
                </span>
              )}
              {!isLast && (
                <ChevronRight
                  size={11}
                  strokeWidth={1.6}
                  aria-hidden="true"
                  className="text-ink-3"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
