import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

/**
 * ThemeToggle — flips <html data-theme> between dark / light.
 *
 * Persists in localStorage. Default is dark (TARS canon). Light theme
 * tokens live in index.css under :root[data-theme="light"]. The marketing
 * surface adopts; the cockpit stays dark regardless.
 */
type Theme = "dark" | "light";

const STORAGE_KEY = "tars-theme";

function readInitial(): Theme {
  if (typeof window === "undefined") return "dark";
  // Wave 122 — wrap in try/catch: private/incognito browsers throw on
  // localStorage access, which would crash the whole app at module init.
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private mode or storage disabled — use canonical default */
  }
  return "dark"; // explicit canonical default — Master.md says OLED-first
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readInitial);

  useEffect(() => {
    const html = document.documentElement;
    if (theme === "light") {
      html.setAttribute("data-theme", "light");
    } else {
      html.removeAttribute("data-theme");
    }
    // Wave 122 — guard against private/incognito storage exceptions.
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* storage disabled — DOM toggle still works in-session */
    }
  }, [theme]);

  return (
    <button
      type="button"
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      aria-pressed={theme === "light"}
      onClick={() => setTheme(t => (t === "dark" ? "light" : "dark"))}
      className="relative ml-1 inline-flex h-9 w-9 cursor-pointer items-center justify-center overflow-hidden rounded-md border border-line bg-white/[0.02] text-ink-2 transition-colors duration-200 hover:border-line-strong hover:bg-white/[0.05] hover:text-ink"
      title={theme === "dark" ? "Light theme" : "Dark theme"}
    >
      <AnimatePresence mode="wait" initial={false}>
        {theme === "dark" ? (
          <motion.span
            key="sun"
            initial={{ opacity: 0, rotate: -45, scale: 0.7 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: 45, scale: 0.7 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="grid place-items-center"
            aria-hidden
          >
            <Sun size={14} strokeWidth={1.6} />
          </motion.span>
        ) : (
          <motion.span
            key="moon"
            initial={{ opacity: 0, rotate: 45, scale: 0.7 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: -45, scale: 0.7 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="grid place-items-center"
            aria-hidden
          >
            <Moon size={14} strokeWidth={1.6} />
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}
