import * as vscode from "vscode";
import {
  backendUrl,
  backendReachable,
  httpRequest,
  escapeHtml,
  offlineHtml,
} from "./extension";

interface PlanSummary {
  plan_id: string;
  intent_summary?: string;
  ops?: unknown[];
  created_at?: string | number;
  status?: string;
}

export class ComposerViewProvider implements vscode.WebviewViewProvider {
  private view?: vscode.WebviewView;

  constructor(private context: vscode.ExtensionContext) {}

  async resolveWebviewView(
    view: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): Promise<void> {
    this.view = view;
    view.webview.options = { enableScripts: true };
    await this.render();

    view.webview.onDidReceiveMessage(async (msg) => {
      if (msg?.action === "launch") {
        vscode.env.openExternal(vscode.Uri.parse("tars://"));
      } else if (msg?.action === "refresh") {
        await this.render();
      } else if (msg?.action === "newPlan") {
        await vscode.commands.executeCommand("tars.composeFromSelection");
        await this.render();
      }
    });
  }

  private async render(): Promise<void> {
    if (!this.view) return;
    const ok = await backendReachable();
    if (!ok) {
      this.view.webview.html = offlineHtml(
        "Cannot reach TARS backend at " + backendUrl() + ".",
        "Launch TARS.app"
      );
      return;
    }
    let plans: PlanSummary[] = [];
    try {
      const r = await httpRequest("GET", backendUrl() + "/api/composer/plans?limit=20");
      if (r.status < 400) {
        const j = JSON.parse(r.body);
        plans = Array.isArray(j?.plans) ? j.plans : [];
      }
    } catch {
      /* swallow — will render empty list */
    }
    this.view.webview.html = renderPlansHtml(plans);
  }
}

function renderPlansHtml(plans: PlanSummary[]): string {
  const rows = plans.length
    ? plans
        .map((p) => {
          const ops = Array.isArray(p.ops) ? p.ops.length : 0;
          return `<li>
  <div class="title">${escapeHtml(p.intent_summary || "(no summary)")}</div>
  <div class="meta">${escapeHtml(p.plan_id || "")} · ${ops} op(s) · ${escapeHtml(String(p.status || ""))}</div>
</li>`;
        })
        .join("")
    : `<li class="empty">No plans yet. Select code in an editor and run <code>TARS: Compose Edit From Selection</code>.</li>`;

  return `<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:12px;color:#e7e7ee;background:#0c0c10">
<style>
  ul{list-style:none;padding:0;margin:0}
  li{padding:8px 10px;border:1px solid #2a2a33;border-radius:8px;margin-bottom:8px;background:#15151c}
  li.empty{opacity:.7;background:transparent;border-style:dashed}
  .title{font-weight:600;margin-bottom:4px}
  .meta{font-size:11px;opacity:.65}
  .row{display:flex;gap:8px;margin-bottom:10px}
  button{padding:6px 10px;border-radius:6px;border:1px solid #444;background:#1a1a22;color:#fff;cursor:pointer;font-size:12px}
</style>
<div class="row">
  <button id="new">New plan from selection</button>
  <button id="refresh">Refresh</button>
</div>
<ul>${rows}</ul>
<script>
const vscode = acquireVsCodeApi();
document.getElementById('new').addEventListener('click',()=>vscode.postMessage({action:'newPlan'}));
document.getElementById('refresh').addEventListener('click',()=>vscode.postMessage({action:'refresh'}));
</script>
</body></html>`;
}
