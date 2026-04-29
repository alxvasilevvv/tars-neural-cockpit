import { useEffect, useState } from "react";
import { t as translate, type TKey } from "@/lib/i18n";

/**
 * toast — tiny pub/sub for operator-grade ephemeral notifications.
 *
 * Why not a library: react-hot-toast / sonner are 8-15 KB; we need
 * ~1 KB of code, full control over typography, and a single mount
 * point owned by `<ToastBus />`. The API is a subset of sonner so
 * we can swap in later if needed.
 *
 * Public API:
 *   toast.info("…")
 *   toast.success("…")
 *   toast.warn("…")
 *   toast.error("…")
 *   toast.announce("…")     // brand-tinted, neutral
 *   toast.dismiss(id?)
 *
 * Each push returns the toast `id` so callers can dismiss themselves.
 *
 * Subscriptions:
 *   const list = useToasts() // for <ToastBus />
 */

export type ToastTone =
  | "info"
  | "success"
  | "warn"
  | "error"
  | "announce";

export interface Toast {
  id: string;
  tone: ToastTone;
  text: string;
  /** Optional small caption rendered under the main text */
  hint?: string;
  /** Auto-dismiss after N ms; 0 means sticky until manually dismissed */
  duration: number;
  createdAt: number;
}

const MAX_VISIBLE = 4;

type Listener = (list: Toast[]) => void;
const listeners = new Set<Listener>();
let stack: Toast[] = [];
let nextId = 1;

function emit() {
  const snapshot = [...stack];
  for (const l of listeners) l(snapshot);
}

function push(
  text: string,
  tone: ToastTone,
  opts?: { hint?: string; duration?: number },
): string {
  const id = `t_${nextId++}`;
  const item: Toast = {
    id,
    tone,
    text,
    hint: opts?.hint,
    duration: opts?.duration ?? defaultDuration(tone),
    createdAt: Date.now(),
  };
  stack = [...stack, item].slice(-MAX_VISIBLE);
  emit();
  return id;
}

function dismiss(id?: string) {
  if (id == null) {
    stack = [];
  } else {
    stack = stack.filter(t => t.id !== id);
  }
  emit();
}

function defaultDuration(tone: ToastTone): number {
  switch (tone) {
    case "error": return 7000;   // give the user time to read it
    case "warn": return 6000;
    case "announce": return 8000;
    case "success": return 4000;
    case "info":
    default: return 4500;
  }
}

type TOpts = {
  hint?: string;
  duration?: number;
  /** vars for the i18n key interpolation when using `*T` variants */
  vars?: Record<string, string | number>;
};

export const toast = {
  info: (text: string, opts?: TOpts) => push(text, "info", opts),
  success: (text: string, opts?: TOpts) => push(text, "success", opts),
  warn: (text: string, opts?: TOpts) => push(text, "warn", opts),
  error: (text: string, opts?: TOpts) => push(text, "error", opts),
  announce: (text: string, opts?: TOpts) => push(text, "announce", opts),

  // i18n adapter — same signatures, but `key` is a TKey from
  // `lib/i18n.ts`. Resolves through the imperative `t()` so the
  // language at the moment of dispatch is captured (toasts don't
  // re-translate after they're queued — by design).
  infoT: (key: TKey, opts?: TOpts) =>
    push(translate(key, opts?.vars), "info", opts),
  successT: (key: TKey, opts?: TOpts) =>
    push(translate(key, opts?.vars), "success", opts),
  warnT: (key: TKey, opts?: TOpts) =>
    push(translate(key, opts?.vars), "warn", opts),
  errorT: (key: TKey, opts?: TOpts) =>
    push(translate(key, opts?.vars), "error", opts),
  announceT: (key: TKey, opts?: TOpts) =>
    push(translate(key, opts?.vars), "announce", opts),

  dismiss,
};

export function useToasts(): Toast[] {
  const [list, setList] = useState<Toast[]>(stack);
  useEffect(() => {
    const fn: Listener = next => setList(next);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);
  return list;
}
