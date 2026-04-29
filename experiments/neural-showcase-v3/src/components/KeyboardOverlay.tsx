import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Keyboard, X } from "lucide-react";
import { useLocation } from "react-router-dom";
import { BrandHairline } from "@/components/BrandHairline";
import { useFocusTrap } from "@/lib/useFocusTrap";

/**
 * <KeyboardOverlay /> — flagship "press ? for keymap" overlay.
 *
 * Triggered by:
 *   - `?` keypress (Shift + / on US-QWERTY) anywhere outside a text
 *     input. We avoid hijacking the key while the operator is typing
 *     in a field, textarea, or contenteditable.
 *   - `Esc` to dismiss.
 *
 * Layout:
 *   - Bottom-centred panel, ~420px wide on desktop, full-bleed on
 *     mobile. Brand-hairline at the top (matches the rest of the
 *     surface).
 *   - Two columns of categories: Global (always available) +
 *     Context (changes with the current route — Cockpit / Pitch /
 *     Landing).
 *
 * No state outside its own. Source of truth for the shortcut map is
 * inline below — when you wire a new global shortcut elsewhere in
 * the app, add it here too.
 */

type Group = "Global" | "Cockpit" | "Pitch" | "Landing";

interface Shortcut {
  keys: string[]; // visual keycaps, e.g. ["⌘", "K"]
  label: string;
  group: Group;
}

const SHORTCUTS: Shortcut[] = [
  // Global
  { keys: ["⌘", "K"],          label: "Open command palette",          group: "Global" },
  { keys: ["?"],                label: "Show this keymap",              group: "Global" },
  { keys: ["Esc"],              label: "Close any modal / overlay",     group: "Global" },

  // Cockpit
  { keys: ["⌘", "⇧", "W"],      label: "Watch me work · cinema mode",   group: "Cockpit" },
  { keys: ["Tab"],              label: "Cycle focusable elements",      group: "Cockpit" },
  { keys: ["Enter"],            label: "Invoke selected action",        group: "Cockpit" },

  // Pitch
  { keys: ["→", "↓", "PgDn"],   label: "Next slide",                    group: "Pitch" },
  { keys: ["←", "↑", "PgUp"],   label: "Previous slide",                group: "Pitch" },
  { keys: ["Home"],             label: "Jump to first slide",           group: "Pitch" },
  { keys: ["End"],              label: "Jump to last slide",            group: "Pitch" },

  // Landing
  { keys: ["↓"],                label: "Scroll forward",                group: "Landing" },
  { keys: ["↑"],                label: "Scroll backward",               group: "Landing" },
];

function isTextField(el: Element | null): boolean {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if ((el as HTMLElement).isContentEditable) return true;
  return false;
}

export function KeyboardOverlay() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const inCockpit = loc.pathname.startsWith("/cockpit");
  const inPitch = loc.pathname.startsWith("/pitch");
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, open);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // ? to open — guard: not while typing.
      if (e.key === "?" && !isTextField(document.activeElement) && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen(prev => !prev);
        return;
      }
      if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Group shortcuts; for the active context, only show the group(s)
  // that make sense.
  const visibleGroups: Group[] = ["Global"];
  if (inCockpit) visibleGroups.push("Cockpit");
  else if (inPitch) visibleGroups.push("Pitch");
  else visibleGroups.push("Landing");

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label="keyboard shortcuts"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          className="fixed inset-0 z-[75] flex items-end justify-center bg-[rgba(2,4,12,0.55)] px-4 pb-6 backdrop-blur-md sm:items-center sm:pb-0"
          onClick={() => setOpen(false)}
        >
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            onClick={e => e.stopPropagation()}
            initial={{ opacity: 0, y: 20, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.99 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-[460px] overflow-hidden rounded-[14px] border border-line-strong bg-bg-1 shadow-[0_40px_140px_rgba(0,0,0,0.65)] focus:outline-none"
          >
            <BrandHairline variant="static" />

            <header className="flex items-center justify-between border-b border-line/60 px-5 py-3.5">
              <div className="inline-flex items-center gap-2.5 font-mono-tech text-[10.5px] uppercase tracking-[2.4px] text-ink-2">
                <Keyboard
                  size={13}
                  strokeWidth={1.7}
                  aria-hidden
                  style={{ color: "var(--brand-violet)" }}
                />
                keyboard shortcuts
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close keymap"
                className="grid h-7 w-7 place-items-center rounded-md text-ink-3 transition-colors hover:bg-white/[0.05] hover:text-ink"
              >
                <X size={11} strokeWidth={2} aria-hidden />
              </button>
            </header>

            <div className="max-h-[55vh] overflow-y-auto">
              {visibleGroups.map(g => (
                <ShortcutSection
                  key={g}
                  title={g}
                  rows={SHORTCUTS.filter(s => s.group === g)}
                />
              ))}
            </div>

            <footer className="flex items-center justify-between border-t border-line/40 px-5 py-2.5 font-mono-tech text-[9.5px] uppercase tracking-[1.8px] text-ink-3">
              <span>press <Kbd>?</Kbd> any time</span>
              <span>esc · close</span>
            </footer>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ShortcutSection({
  title,
  rows,
}: {
  title: string;
  rows: Shortcut[];
}) {
  if (!rows.length) return null;
  return (
    <section>
      <div className="px-5 pt-3 pb-1.5 font-mono-tech text-[9.5px] uppercase tracking-[2.4px] text-ink-3">
        {title}
      </div>
      <ul className="border-b border-line/40">
        {rows.map(r => (
          <li
            key={r.label}
            className="grid grid-cols-[1fr_auto] items-center gap-3 px-5 py-2"
          >
            <span className="font-mono-tech text-[12.5px] text-ink">
              {r.label}
            </span>
            <span className="flex items-center gap-1">
              {r.keys.map((k, i) => (
                <Kbd key={i}>{k}</Kbd>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block min-w-[20px] rounded-[5px] border border-line/80 bg-bg-2/80 px-1.5 py-0.5 text-center font-mono-tech text-[10px] uppercase tracking-[1.4px] text-ink/95">
      {children}
    </kbd>
  );
}
