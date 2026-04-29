import { useEffect } from "react";

/**
 * useFocusTrap — keyboard focus containment for modals & overlays.
 *
 * Captures Tab / Shift+Tab inside the referenced container while
 * `active` is true, restores the previously-focused element when the
 * trap deactivates, and seeds initial focus to the first tabbable
 * descendant (or the container itself if it's tabindex=-1).
 *
 * Drop-in usage:
 *
 *   const ref = useRef<HTMLDivElement>(null);
 *   useFocusTrap(ref, isOpen);
 *
 *   return isOpen ? <div ref={ref} role="dialog" tabIndex={-1}>…</div> : null;
 *
 * Notes:
 *   - Listens on the document; once-per-mount, no per-render overhead.
 *   - Doesn't hijack Esc (callers wire their own handler — keeps this
 *     hook composable with Cmd+K / Watch-me-work / KeyboardOverlay
 *     existing logic).
 *   - Respects `inert`-trees: if a tabbable element happens to be
 *     inside an inert subtree, querySelectorAll returns it but
 *     focusing a no-op node is harmless.
 *   - Auto-skips trapping when there's exactly 0 or 1 tabbable
 *     descendants (Tab still cycles between document UA defaults).
 */

const TABBABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[contenteditable='true']",
  "iframe",
  "object",
  "embed",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function useFocusTrap(
  ref: React.RefObject<HTMLElement | null>,
  active: boolean,
): void {
  useEffect(() => {
    if (!active) return;
    const container = ref.current;
    if (!container) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Seed focus inside the container. Prefer first tabbable; fall
    // back to the container itself (must have tabindex=-1).
    const focusFirst = () => {
      const tabbables = getTabbables(container);
      if (tabbables.length > 0) {
        tabbables[0].focus();
      } else if (container.tabIndex >= 0 || container.getAttribute("tabindex") === "-1") {
        container.focus();
      }
    };
    // Microtask delay so AnimatePresence has time to mount the node.
    const seed = setTimeout(focusFirst, 16);

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const tabbables = getTabbables(container);
      if (tabbables.length === 0) {
        // Nothing to cycle — pin focus on the container itself.
        e.preventDefault();
        container.focus();
        return;
      }
      const first = tabbables[0];
      const last = tabbables[tabbables.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;

      if (e.shiftKey) {
        if (activeEl === first || !container.contains(activeEl)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (activeEl === last || !container.contains(activeEl)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", onKey, true);

    return () => {
      clearTimeout(seed);
      document.removeEventListener("keydown", onKey, true);
      // Restore focus to the opener; ignore if it was removed.
      try {
        previouslyFocused?.focus?.();
      } catch {
        /* ignore */
      }
    };
  }, [active, ref]);
}

function getTabbables(root: HTMLElement): HTMLElement[] {
  const list = Array.from(
    root.querySelectorAll<HTMLElement>(TABBABLE_SELECTOR),
  );
  return list.filter(el => {
    if (el.hidden) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    // Exclude elements with display:none / visibility:hidden (cheap check).
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return false;
    return true;
  });
}
