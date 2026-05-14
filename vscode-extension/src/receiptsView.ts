import * as vscode from "vscode";
import {
  backendUrl,
  backendReachable,
  httpRequest,
  escapeHtml,
  offlineHtml,
} from "./extension";

interface ReceiptRow {
  id?: string;
  type?: string;
  actor?: string;
  target?: string;
  ts?: number | string;
  verified?: boolean;
}

export class ReceiptsViewProvider implements vscode.WebviewViewProvider {
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
    const rows = await fetchReceipts();
    this.view.webview.html = renderReceiptsHtml(rows);
  }
}

async function fetchReceipts(): Promise<ReceiptRow[]> {
  // Spec says /api/receipts/recent. If the backend ships that route, we
  // use it; if not (current /api/receipts router returns the recent list
  // via limit), we fall back transparently.
  const tryRoutes = [
    backendUrl() + "/api/receipts/recent?limit=20",
    backendUrl() + "/api/receipts?limit=20",
  ];
  for (const url of tryRoutes) {
    try {
      const r = await httpRequest("GET", url);
      if (r.status >= 400) continue;
      const j = JSON.parse(r.body);
      const arr = (j?.receipts || j?.items || []) as ReceiptRow[];
      if (Array.isArray(arr)) return arr;
    } catch {
      /* try next */
    }
  }
  return [];
}

function renderReceiptsHtml(rows: ReceiptRow[]): string {
  const items = rows.length
    ? rows
        .map((r) => {
          const when =
            typeof r.ts === "number"
              ? new Date(r.ts * (r.ts < 1e12 ? 1000 : 1)).toLocaleString()
              : escapeHtml(String(r.ts || ""));
          const ok = r.verified === false ? "broken" : "ok";
          return `<li class="r ${ok}">
  <div class="t">${escapeHtml(r.type || "?")}</div>
  <div class="m">${escapeHtml(r.actor || "")} → ${escapeHtml(r.target || "")}</div>
  <div class="w">${when}</div>
</li>`;
        })
        .join("")
    : `<li class="empty">No receipts yet. Anything TARS does (composer plans, agent runs, voice actions) leaves a signed receipt here.</li>`;

  return `<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:12px;color:#e7e7ee;background:#0c0c10">
<style>
  ul{list-style:none;padding:0;margin:0}
  li.r{padding:8px 10px;border:1px solid #2a2a33;border-left:3px solid #4af;border-radius:6px;margin-bottom:6px;background:#15151c}
  li.r.broken{border-left-color:#e64}
  li.empty{opacity:.7;padding:8px;border:1px dashed #333;border-radius:6px}
  .t{font-weight:600}
  .m{font-size:11px;opacity:.85}
  .w{font-size:10px;opacity:.55;margin-top:2px}
  button{padding:6px 10px;border-radius:6px;border:1px solid #444;background:#1a1a22;color:#fff;cursor:pointer;font-size:12px;margin-bottom:10px}
</style>
<button id="refresh">Refresh</button>
<ul>${items}</ul>
<script>
const vscode = acquireVsCodeApi();
document.getElementById('refresh').addEventListener('click',()=>vscode.postMessage({action:'refresh'}));
</script>
</body></html>`;
}
