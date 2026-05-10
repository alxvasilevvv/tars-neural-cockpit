// SYNC: claude-w107-bundles
/**
 * Wave 107 — shared types for the bundles surface.
 *
 * Mirrors the backend ``Bundle`` / ``InstallReport`` dataclasses
 * (see backend/core/bundles/models.py).
 */

export type OrgType =
  | "vc_fund"
  | "hedge_fund"
  | "family_office"
  | "saas"
  | "dao"
  | "research_lab"
  | "other";

export interface ConnectorHint {
  id: string;
  priority: boolean;
}

export interface ScheduledEntry {
  playbook_id: string;
  cron: string;
  args?: Record<string, unknown>;
}

export interface BundleComponents {
  playbooks: string[];
  scheduled: ScheduledEntry[];
  dashboard_widgets: string[];
  report_templates: string[];
  outreach_templates: string[];
  connectors_hints: ConnectorHint[];
  welcome_content: string;
  first_run_playbook: string | null;
}

export interface Bundle {
  id: string;
  slug: string;
  name: string;
  description: string;
  org_type: OrgType;
  version: string;
  components: BundleComponents;
}

export interface InstallReportItems {
  playbooks: Array<{ id: string; available?: boolean; name?: string }>;
  scheduled: Array<{
    playbook_id?: string;
    cron?: string;
    schedule_id?: string;
    reused?: boolean;
    skipped?: boolean;
    first_run?: boolean;
    would_create?: boolean;
    deleted?: boolean;
  }>;
  dashboard_widgets: Array<{ id: string }>;
  report_templates: Array<{ slug: string }>;
  outreach_templates: Array<{ slug: string; template_id?: string; skipped?: boolean; would_seed?: boolean }>;
  connectors_hints: ConnectorHint[];
}

export interface InstallReport {
  install_id: string;
  bundle_id: string;
  org_id: string;
  dry_run: boolean;
  started_at: number;
  finished_at: number | null;
  welcome_content: string;
  first_run_id: string | null;
  items: InstallReportItems;
  counts: Record<string, number>;
  total: number;
  warnings: string[];
}

export interface PreviewEnvelope {
  ok: boolean;
  bundle: Bundle;
  preview: InstallReport;
  summary: {
    counts: Record<string, number>;
    warnings: string[];
    first_run_playbook: string | null;
  };
}

export interface InstallEnvelope {
  ok: boolean;
  report: InstallReport;
}

export interface BundleListEnvelope {
  ok: boolean;
  contract_version: string;
  count: number;
  bundles: Bundle[];
  recommended?: {
    org_type: string;
    bundle_id: string;
    slug: string;
    name: string;
  };
}

export interface InstalledListEnvelope {
  ok: boolean;
  count: number;
  installed: Array<{
    install_id: string;
    bundle_id: string;
    org_id: string;
    installed_at: number;
    finished_at: number | null;
    welcome_content: string;
    first_run_id: string | null;
    items: InstallReportItems;
    warnings: string[];
  }>;
}
