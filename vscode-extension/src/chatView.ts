import * as vscode from "vscode";
import { backendUrl, backendReachable, escapeHtml, offlineHtml } from "./extension";

export class ChatViewProvider implements vscode.WebviewViewProvider {
  constructor(private context: vscode.ExtensionContext) {}

  async resolveWebviewView(
    view: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): Promise<void> {
    view.webview.options = { enableScripts: true };
    const ok = await backendReachable();
    if (!ok) {
      view.webview.html = offlineHtml(
        "Cannot reach TARS backend at " + backendUrl() + ".",
        "Launch TARS.app"
      );
      view.webview.onDidReceiveMessage((m) => {
        if (m?.action === "launch") {
          vscode.env.openExternal(vscode.Uri.parse("tars://"));
        }
      });
      return;
    }
    const url = backendUrl() + "/api/chat/embed";
    view.webview.html = `<!doctype html><html><head>
<meta charset="utf-8"/>
<style>html,body,iframe{margin:0;padding:0;height:100%;width:100%;border:0;background:#0c0c10;color:#e7e7ee}</style>
</head><body>
<iframe src="${escapeHtml(url)}" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>
</body></html>`;
  }
}
