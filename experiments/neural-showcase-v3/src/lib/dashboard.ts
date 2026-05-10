// SYNC: claude-w96-dashboard
/**
 * Wave 96 — Reporting dashboard config + persistence layer.
 *
 * The dashboard at `/dashboard` is a per-user workspace that pulls
 * snippets from every existing TARS surface (calendar, slack, gmail,
 * github, wallet, receipts, backtest, cohorts, HIL inbox, playbooks).
 *
 * Backend-free for v9.1 — layouts live in `localStorage` under a single
 * key. v9.3 multi-tenant will move the same shape to
 * `/api/dashboard/layout` so the data contract here doubles as the
 * eventual REST schema.
 */

import { useCallback, useEffect, useState } from "react";

// -- widget catalogue ------------------------------------------------

export type WidgetType =
  | "calendar-today"
  | "slack-mentions"
  | "gmail-unread"
  | "github-prs"
  | "wallet-balance"
  | "recent-receipts"
  | "backtest-summary"
  | "active-cohorts"
  | "hil-inbox"
  | "playbook-runs";

export type WidgetSize = 3 | 4 | 6 | 12;

export type WidgetRequires =
  | "calendar"
  | "slack"
  | "gmail"
  | "github"
  | "wallet"
  | "receipts"
  | "algotrade"
  | "cohort"
  | "policy"
  | "playbooks";

export interface WidgetMeta {
  type: WidgetType;
  name: string;
  description: string;
  defaultSize: WidgetSize;
  requires: WidgetRequires;
}

export const WIDGET_REGISTRY: Record<WidgetType, WidgetMeta> = {
  "calendar-today":   { type: "calendar-today",   name: "Calendar today",       description: "Events on your calendar today.",                 defaultSize: 6,  requires: "calendar"  },
  "slack-mentions":   { type: "slack-mentions",   name: "Slack mentions",       description: "@-mentions across your connected workspaces.",   defaultSize: 4,  requires: "slack"     },
  "gmail-unread":     { type: "gmail-unread",     name: "Gmail unread",         description: "Unread threads in your primary inbox.",          defaultSize: 4,  requires: "gmail"     },
  "github-prs":       { type: "github-prs",       name: "GitHub PRs",           description: "Pull requests waiting on your review.",          defaultSize: 4,  requires: "github"    },
  "wallet-balance":   { type: "wallet-balance",   name: "Wallet balance",       description: "Solana / EVM / TON balances across wallets.",    defaultSize: 3,  requires: "wallet"    },
  "recent-receipts":  { type: "recent-receipts",  name: "Recent receipts",      description: "Last 10 entries from the receipt ledger.",       defaultSize: 6,  requires: "receipts"  },
  "backtest-summary": { type: "backtest-summary", name: "Backtest summary",     description: "Last 3 algotrade backtests - Sharpe + win rate.",defaultSize: 6,  requires: "algotrade" },
  "active-cohorts":   { type: "active-cohorts",   name: "Active cohorts",       description: "Workshop attendees grouped by phase.",           defaultSize: 4,  requires: "cohort"    },
  "hil-inbox":        { type: "hil-inbox",        name: "HIL inbox",            description: "Pending human-in-the-loop confirmations.",       defaultSize: 3,  requires: "policy"    },
  "playbook-runs":    { type: "playbook-runs",    name: "Recent playbook runs", description: "Most recent multi-step action chains.",          defaultSize: 6,  requires: "playbooks" },
};

export function availableWidgets(): readonly WidgetMeta[] {
  return Object.values(WIDGET_REGISTRY);
}

// -- layout shape ----------------------------------------------------

export interface WidgetInstance {
  id: string;
  type: WidgetType;
  size: WidgetSize;
}

export interface DashboardLayout {
  version: 1;
  displayName: string;
  widgets: WidgetInstance[];
}

// -- default layouts per role ---------------------------------------

export type DashboardRole =
  | "fund-partner"
  | "quant"
  | "analyst"
  | "founder"
  | "generic";

export const ROLE_LABEL: Record<DashboardRole, string> = {
  "fund-partner": "Fund partner",
  "quant":        "Quant",
  "analyst":      "Analyst",
  "founder":      "Founder",
  "generic":      "Generic",
};

function widget(type: WidgetType, size?: WidgetSize): WidgetInstance {
  return {
    id: `${type}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    size: size ?? WIDGET_REGISTRY[type].defaultSize,
  };
}

export const DEFAULT_LAYOUTS: Record<DashboardRole, () => DashboardLayout> = {
  "fund-partner": () => ({
    version: 1,
    displayName: "Partner",
    widgets: [
      widget("active-cohorts"),
      widget("hil-inbox"),
      widget("recent-receipts"),
      widget("backtest-summary"),
      widget("playbook-runs"),
    ],
  }),
  "quant": () => ({
    version: 1,
    displayName: "Quant",
    widgets: [
      widget("backtest-summary", 12),
      widget("github-prs"),
      widget("playbook-runs"),
      widget("recent-receipts"),
    ],
  }),
  "analyst": () => ({
    version: 1,
    displayName: "Analyst",
    widgets: [
      widget("calendar-today"),
      widget("gmail-unread"),
      widget("slack-mentions"),
      widget("playbook-runs"),
      widget("hil-inbox"),
    ],
  }),
  "founder": () => ({
    version: 1,
    displayName: "Founder",
    widgets: [
      widget("calendar-today"),
      widget("slack-mentions"),
      widget("gmail-unread"),
      widget("wallet-balance"),
      widget("hil-inbox"),
      widget("recent-receipts"),
    ],
  }),
  "generic": () => ({
    version: 1,
    displayName: "Operator",
    widgets: [
      widget("calendar-today"),
      widget("slack-mentions"),
      widget("gmail-unread"),
      widget("hil-inbox"),
    ],
  }),
};

// -- persistence -----------------------------------------------------

export const STORAGE_KEY = "tars.dashboard.layout";

function safeStorage(): Storage | null {
  try {
    if (typeof localStorage === "undefined") return null;
    return localStorage;
  } catch {
    return null;
  }
}

export function loadLayout(): DashboardLayout {
  const s = safeStorage();
  if (!s) return DEFAULT_LAYOUTS.generic();
  const raw = s.getItem(STORAGE_KEY);
  if (!raw) return DEFAULT_LAYOUTS.generic();
  try {
    const parsed = JSON.parse(raw) as DashboardLayout;
    if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.widgets)) {
      return DEFAULT_LAYOUTS.generic();
    }
    const widgets = parsed.widgets
      .filter((w) => w && typeof w.id === "string" && (w.type as string) in WIDGET_REGISTRY)
      .map((w) => ({
        id: w.id,
        type: w.type,
        size: ([3, 4, 6, 12] as WidgetSize[]).includes(w.size as WidgetSize)
          ? (w.size as WidgetSize)
          : WIDGET_REGISTRY[w.type].defaultSize,
      }));
    return {
      version: 1,
      displayName: typeof parsed.displayName === "string" ? parsed.displayName : "Operator",
      widgets,
    };
  } catch {
    return DEFAULT_LAYOUTS.generic();
  }
}

export function saveLayout(layout: DashboardLayout): void {
  const s = safeStorage();
  if (!s) return;
  try {
    s.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // storage full / private mode - silently no-op
  }
}

export function resetLayout(role: DashboardRole = "generic"): DashboardLayout {
  const next = DEFAULT_LAYOUTS[role]();
  saveLayout(next);
  return next;
}

// -- greeting helper -------------------------------------------------

export function timeOfDayGreeting(now: Date = new Date()): string {
  const h = now.getHours();
  if (h < 5)  return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 22) return "Good evening";
  return "Good night";
}

// -- hook ------------------------------------------------------------

export interface UseDashboardResult {
  layout: DashboardLayout;
  addWidget: (type: WidgetType) => void;
  removeWidget: (id: string) => void;
  moveWidget: (id: string, toIndex: number) => void;
  setSize: (id: string, size: WidgetSize) => void;
  setDisplayName: (name: string) => void;
  reset: (role?: DashboardRole) => void;
}

export function useDashboard(): UseDashboardResult {
  const [layout, setLayout] = useState<DashboardLayout>(() => loadLayout());

  useEffect(() => {
    const fresh = loadLayout();
    setLayout(fresh);
  }, []);

  const persist = useCallback((next: DashboardLayout) => {
    setLayout(next);
    saveLayout(next);
  }, []);

  const addWidget = useCallback(
    (type: WidgetType) => {
      const meta = WIDGET_REGISTRY[type];
      if (!meta) return;
      persist({
        ...layout,
        widgets: [...layout.widgets, widget(type)],
      });
    },
    [layout, persist],
  );

  const removeWidget = useCallback(
    (id: string) => {
      persist({
        ...layout,
        widgets: layout.widgets.filter((w) => w.id !== id),
      });
    },
    [layout, persist],
  );

  const moveWidget = useCallback(
    (id: string, toIndex: number) => {
      const from = layout.widgets.findIndex((w) => w.id === id);
      if (from < 0) return;
      const clamped = Math.max(0, Math.min(layout.widgets.length - 1, toIndex));
      if (clamped === from) return;
      const next = layout.widgets.slice();
      const [moved] = next.splice(from, 1);
      next.splice(clamped, 0, moved);
      persist({ ...layout, widgets: next });
    },
    [layout, persist],
  );

  const setSize = useCallback(
    (id: string, size: WidgetSize) => {
      persist({
        ...layout,
        widgets: layout.widgets.map((w) => (w.id === id ? { ...w, size } : w)),
      });
    },
    [layout, persist],
  );

  const setDisplayName = useCallback(
    (name: string) => {
      persist({ ...layout, displayName: name });
    },
    [layout, persist],
  );

  const reset = useCallback(
    (role: DashboardRole = "generic") => {
      persist(DEFAULT_LAYOUTS[role]());
    },
    [persist],
  );

  return { layout, addWidget, removeWidget, moveWidget, setSize, setDisplayName, reset };
}
