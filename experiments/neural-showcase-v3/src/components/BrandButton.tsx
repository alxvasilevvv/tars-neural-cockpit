import { forwardRef } from "react";
import type { ButtonHTMLAttributes, AnchorHTMLAttributes, ReactNode } from "react";

/**
 * <BrandButton /> — the meeet brand CTA. Replaces three near-identical
 * inline button declarations on CookieConsent (Got it), Waitlist
 * (Notify me), DownloadStrip (Primary download). Same gradient, same
 * shadow, same hover lift, same focus ring (inherits global).
 *
 * Variants:
 *   "solid" (default) — indigo→violet CTA gradient, white text
 *   "ghost"           — transparent fill + brand stroke, accent text
 *
 * Sizes:
 *   "sm"  — short forms / inline                  (px-3 py-2)
 *   "md"  — default                               (px-4 py-2.5)
 *   "lg"  — hero CTA                              (px-6 py-3.5)
 *
 * Renders as `<a>` when `href` is provided, `<button>` otherwise.
 */

type Variant = "solid" | "ghost";
type Size = "sm" | "md" | "lg";

const SIZE_PADDING: Record<Size, string> = {
  sm: "px-3 py-2 text-[10px] tracking-[2.2px]",
  md: "px-4 py-2.5 text-[10.5px] tracking-[2.4px]",
  lg: "px-6 py-3.5 text-[12.5px] tracking-[0.18em]",
};

const SOLID = `
  text-white
  transition-all duration-200
  enabled:hover:-translate-y-0.5
  disabled:cursor-not-allowed disabled:opacity-50
`;
const GHOST = `
  text-accent
  border border-line-hot bg-accent-deep
  transition-all duration-200
  enabled:hover:-translate-y-0.5 enabled:hover:border-accent enabled:hover:bg-accent/10
  disabled:cursor-not-allowed disabled:opacity-50
`;

interface BaseProps {
  variant?: Variant;
  size?: Size;
  /** when true, button stretches to its container */
  fullWidth?: boolean;
  /** lucide-react Icon (not React node) — placed at end of label */
  trailingIcon?: ReactNode;
  /** lucide-react Icon (not React node) — placed at start of label */
  leadingIcon?: ReactNode;
  children: ReactNode;
}

type ButtonProps = BaseProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof BaseProps | "className"> & {
    href?: undefined;
    className?: string;
  };
type AnchorProps = BaseProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof BaseProps | "className"> & {
    href: string;
    className?: string;
  };
export type BrandButtonProps = ButtonProps | AnchorProps;

const baseClass = (variant: Variant, size: Size, fullWidth?: boolean) =>
  `inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-mono-tech uppercase ${
    SIZE_PADDING[size]
  } ${variant === "solid" ? SOLID : GHOST} ${fullWidth ? "w-full" : ""}`;

const solidStyle: React.CSSProperties = {
  background: "var(--brand-cta-gradient)",
  boxShadow: "var(--shadow-brand-cta)",
};

export const BrandButton = forwardRef<HTMLElement, BrandButtonProps>(
  function BrandButton(
    {
      variant = "solid",
      size = "md",
      fullWidth,
      leadingIcon,
      trailingIcon,
      children,
      className = "",
      ...rest
    },
    ref,
  ) {
    const cls = `${baseClass(variant, size, fullWidth)} ${className}`.trim();
    const inlineStyle = variant === "solid" ? solidStyle : undefined;
    const inner = (
      <>
        {leadingIcon}
        <span>{children}</span>
        {trailingIcon}
      </>
    );

    if ("href" in rest && rest.href) {
      return (
        <a
          ref={ref as React.Ref<HTMLAnchorElement>}
          className={cls}
          style={inlineStyle}
          {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}
        >
          {inner}
        </a>
      );
    }
    return (
      <button
        ref={ref as React.Ref<HTMLButtonElement>}
        className={cls}
        style={inlineStyle}
        {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}
      >
        {inner}
      </button>
    );
  },
);
