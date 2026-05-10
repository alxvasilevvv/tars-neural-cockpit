/**
 * tutorial.ts — Wave 92
 *
 * localStorage helpers + a small `useTutorial` hook for the in-app
 * workshop tutorial overlay. Each "page" of the workshop surface
 * (generic /workshop, /workshop/cohort facilitator dashboard,
 * /workshop/enterprise marketing landing) gets its own completion
 * key so a first-time visitor sees the right tour for the page they
 * actually opened.
 *
 * Storage schema (one key per pageKey):
 *
 *   tars.workshop.tutorial.completed.<pageKey> = "1"
 *
 * Plus a legacy unscoped key for the original /workshop tour:
 *
 *   tars.workshop.tutorial.completed = "1"
 *
 * The reset() helper wipes every known scope so the dev/Cmd+K
 * "restart tutorial" actions surface every overlay again.
 *
 * Defensive: every localStorage call is wrapped — Safari private mode
 * throws on `.setItem` and `.getItem` will only return null. Treating
 * those failures as "not completed" keeps the tutorial from breaking
 * the page if storage is unavailable; the worst case is that a user
 * sees the overlay every visit (acceptable degradation).
 */

import { useCallback, useEffect, useState } from "react";

/** Generic key prefix shared with WorkshopRail, etc. */
export const STORAGE_PREFIX = "tars.workshop.tutorial.completed";

/** Page identifiers the workshop tutorial supports. */
export type TutorialPageKey =
  | "workshop-generic"
  | "workshop-cohort"
  | "workshop-enterprise";

const KNOWN_PAGE_KEYS: TutorialPageKey[] = [
  "workshop-generic",
  "workshop-cohort",
  "workshop-enterprise",
];

function storageKey(page: TutorialPageKey): string {
  return `${STORAGE_PREFIX}.${page}`;
}

/** Returns true if the user already finished (or skipped) this tour. */
export function isCompleted(page: TutorialPageKey): boolean {
  if (typeof localStorage === "undefined") return false;
  try {
    return localStorage.getItem(storageKey(page)) === "1";
  } catch {
    return false;
  }
}

/** Marks the tour as completed so we never auto-mount it again. */
export function markCompleted(page: TutorialPageKey): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(storageKey(page), "1");
  } catch {
    /* private mode — silently ignore */
  }
}

/**
 * Wipe completion flags. Pass a single page to reset that scope only,
 * or call with no args to wipe every known workshop tutorial flag
 * (used by Settings + Cmd+K "Restart workshop tutorial").
 */
export function reset(page?: TutorialPageKey): void {
  if (typeof localStorage === "undefined") return;
  try {
    if (page) {
      localStorage.removeItem(storageKey(page));
    } else {
      for (const key of KNOWN_PAGE_KEYS) {
        localStorage.removeItem(storageKey(key));
      }
      // Drop the legacy unscoped key too just in case an earlier
      // build wrote it.
      localStorage.removeItem(STORAGE_PREFIX);
    }
  } catch {
    /* ignore */
  }
}

export interface UseTutorialResult {
  /** Zero-indexed step the user is currently viewing. */
  step: number;
  /** Total number of steps in this tour. */
  total: number;
  /** Advance one step (or finish if at the last step). */
  next: () => void;
  /** Go back one step (no-op on the first step). */
  prev: () => void;
  /** Cancel the entire tour and remember it. */
  skip: () => void;
  /**
   * `true` while the overlay should be mounted. Flips to `false`
   * after `next()` past the last step OR after `skip()`.
   */
  isVisible: boolean;
  /**
   * Imperative re-show — used by GlobalCommandPalette / Settings
   * when the user explicitly asks to restart the tutorial.
   */
  restart: () => void;
}

/**
 * useTutorial — small state hook that owns step / visibility for one
 * page's tutorial. Reads the localStorage flag exactly once on mount
 * to decide whether to surface the overlay.
 */
export function useTutorial(
  page: TutorialPageKey,
  total: number,
): UseTutorialResult {
  const [step, setStep] = useState(0);
  const [isVisible, setVisible] = useState(false);

  // Decide on mount whether to show. Defer to a microtask so SSR
  // hydration + framer remount don't fight us.
  useEffect(() => {
    if (isCompleted(page)) return;
    setStep(0);
    setVisible(true);
  }, [page]);

  const finish = useCallback(() => {
    markCompleted(page);
    setVisible(false);
  }, [page]);

  const next = useCallback(() => {
    setStep((s) => {
      if (s >= total - 1) {
        // Finishing — mark complete + hide.
        markCompleted(page);
        setVisible(false);
        return s;
      }
      return s + 1;
    });
  }, [total, page]);

  const prev = useCallback(() => {
    setStep((s) => Math.max(0, s - 1));
  }, []);

  const skip = useCallback(() => {
    finish();
  }, [finish]);

  const restart = useCallback(() => {
    reset(page);
    setStep(0);
    setVisible(true);
  }, [page]);

  return { step, total, next, prev, skip, isVisible, restart };
}
