/**
 * TARS — VS Code extension entrypoint.
 *
 * This is a *thin bridge* to TARS.app. TARS itself runs as a separate Mac
 * app (or a backend pinned to 127.0.0.1:8765). We do not embed any model
 * logic here — every interesting thing happens over HTTP against the
 * backend.
 *
 * Commands:
 *   tars.openChat              — open a Webview Panel pointing at the
 *                                chat embed page on the backend.
 *   tars.composeFromSelection  — take the current editor selection,
 *                                POST it to /api/composer/plan, then
 *                                walk the user through each op as a
 *                                native VS Code diff editor.
 *   tars.showReceipts          — pull recent receipts and render them
 *                                in a tree view inside the activity-bar
 *                                container.
 *
 * View container & sidebar Webviews (chat / composer / receipts) are
 * registered alongside the commands.
 */

import * as vscode from "vscode";
import * as http from "http";
import * as https from "https";
import { URL } from "url";

import { ChatViewProvider } from "./chatView";
import { ComposerViewProvider } from "./composerView";
import { ReceiptsViewProvider } from "./receiptsView";

// ---------------------------------------------------------------------------
// Config / helpers
// ---------------------------------------------------------------------------

export function backendUrl(): string {
  const cfg = vscode.workspace.getConfiguration("tars");
  return (cfg.get<string>("backendUrl") || "http://127.0.0.1:8765").replace(
    /\/+$/,
    ""
  );
}

interface HttpResult {
  status: number;
  body: string;
}

export function httpRequest(
  method: string,
  url: string,
  payload?: unknown,
  timeoutMs = 8000
): Promise<HttpResult> {
  return new Promise((resolve, reject) => {
    let parsed: URL;
    try {
      parsed = new URL(url);
    } catch (e) {
      reject(e);
      return;
    }
    const lib = parsed.protocol === "https:" ? https : http;
    const body = payload === undefined ? undefined : JSON.stringify(payload);
    const req = lib.request(
      {
        method,
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname + parsed.search,
        headers: {
          "content-type": "application/json",
          "x-tars-client": "vscode-tars-tab/0.1.0",
          ...(body ? { "content-length": Buffer.byteLength(body) } : {}),
        },
        timeout: timeoutMs,
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          resolve({
            status: res.statusCode || 0,
            body: Buffer.concat(chunks).toString("utf8"),
          });
        });
      }
    );
    req.on("timeout", () => {
      req.destroy(new Error("backend timeout"));
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

export async function backendReachable(): Promise<boolean> {
  try {
    const r = await httpRequest("GET", backendUrl() + "/health", undefined, 2000);
    return r.status >= 200 && r.status < 500;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Command: tars.openChat
// ---------------------------------------------------------------------------

async function cmdOpenChat(context: vscode.ExtensionContext): Promise<void> {
  const ok = await backendReachable();
  const url = backendUrl() + "/api/chat/embed";

  const panel = vscode.window.createWebviewPanel(
    "tarsChat",
    "TARS — Chat",
    vscode.ViewColumn.Active,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
    }
  );

  if (ok) {
    // Embed via iframe — the backend serves /api/chat/embed as a
    // standalone HTML page sized for a webview.
    panel.webview.html = `<!doctype html><html><head>
<meta charset="utf-8"/>
<style>html,body,iframe{margin:0;padding:0;height:100%;width:100%;border:0;background:#0c0c10;color:#e7e7ee}</style>
</head><body>
<iframe src="${url}" sandbox="allow-scripts allow-forms allow-same-origin"></iframe>
</body></html>`;
  } else {
    panel.webview.html = offlineHtml(
      "Cannot reach TARS backend at " + backendUrl() + ".",
      "Launch TARS.app"
    );
    panel.webview.onDidReceiveMessage((msg) => {
      if (msg && msg.action === "launch") {
        vscode.env.openExternal(vscode.Uri.parse("tars://"));
      }
    });
  }
  context.subscriptions.push(panel);
}

export function offlineHtml(reason: string, buttonLabel: string): string {
  return `<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:24px;color:#e7e7ee;background:#0c0c10">
<h2 style="margin:0 0 8px">TARS backend not running</h2>
<p style="opacity:.8;margin:0 0 16px">${escapeHtml(reason)}</p>
<button id="b" style="padding:8px 14px;border-radius:8px;border:1px solid #444;background:#1a1a22;color:#fff;cursor:pointer">${escapeHtml(buttonLabel)}</button>
<script>
const vscode = acquireVsCodeApi();
document.getElementById('b').addEventListener('click', () => vscode.postMessage({action:'launch'}));
</script>
</body></html>`;
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ---------------------------------------------------------------------------
// Command: tars.composeFromSelection
// ---------------------------------------------------------------------------

async function cmdComposeFromSelection(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("TARS: open a file and select text first.");
    return;
  }
  const sel = editor.document.getText(editor.selection);
  if (!sel.trim()) {
    vscode.window.showWarningMessage("TARS: selection is empty.");
    return;
  }
  const transcript = await vscode.window.showInputBox({
    prompt: "What should TARS do with this selection? (this becomes the transcript)",
    placeHolder: "e.g. extract this into a helper named formatDate",
  });
  if (!transcript) return;

  const project = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  let resp: HttpResult;
  try {
    resp = await httpRequest("POST", backendUrl() + "/api/composer/plan", {
      transcript: `${transcript}\n\n--- selected context ---\n${sel}`,
      project_root: project,
    });
  } catch (e: any) {
    vscode.window.showErrorMessage(
      "TARS: composer call failed — is the backend up? " + (e?.message || e)
    );
    return;
  }
  if (resp.status >= 400) {
    vscode.window.showErrorMessage("TARS composer rejected the plan (HTTP " + resp.status + "): " + resp.body.slice(0, 240));
    return;
  }
  let parsed: any;
  try {
    parsed = JSON.parse(resp.body);
  } catch {
    vscode.window.showErrorMessage("TARS: composer returned non-JSON.");
    return;
  }
  if (!parsed?.ok || !parsed?.plan?.ops?.length) {
    vscode.window.showInformationMessage("TARS: planner returned no actionable ops.");
    return;
  }

  // Walk each op and show a native diff editor. The backend's ops carry
  // path + before + after fields; we synthesise virtual documents for the
  // diff view.
  for (let i = 0; i < parsed.plan.ops.length; i++) {
    const op = parsed.plan.ops[i];
    const before = String(op.before ?? "");
    const after = String(op.after ?? "");
    const beforeUri = vscode.Uri.parse(
      "untitled:tars-before-" + i + "-" + encodeURIComponent(op.path || "op")
    );
    const afterUri = vscode.Uri.parse(
      "untitled:tars-after-" + i + "-" + encodeURIComponent(op.path || "op")
    );
    const beforeDoc = await vscode.workspace.openTextDocument({
      content: before,
      language: guessLang(op.path),
    });
    const afterDoc = await vscode.workspace.openTextDocument({
      content: after,
      language: guessLang(op.path),
    });
    await vscode.commands.executeCommand(
      "vscode.diff",
      beforeDoc.uri,
      afterDoc.uri,
      `TARS plan ${parsed.plan.plan_id || ""} — op ${i + 1}/${parsed.plan.ops.length}: ${op.path || op.kind || ""}`
    );
  }
  vscode.window.showInformationMessage(
    `TARS: opened ${parsed.plan.ops.length} diff(s). Approve / reject the plan from the TARS.app Composer panel.`
  );
}

function guessLang(path?: string): string {
  if (!path) return "plaintext";
  const ext = path.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "ts": case "tsx": return "typescript";
    case "js": case "jsx": return "javascript";
    case "py": return "python";
    case "rs": return "rust";
    case "go": return "go";
    case "json": return "json";
    case "md": return "markdown";
    case "css": return "css";
    case "html": return "html";
    case "yaml": case "yml": return "yaml";
    case "sh": return "shellscript";
    default: return "plaintext";
  }
}

// ---------------------------------------------------------------------------
// Command: tars.showReceipts
// ---------------------------------------------------------------------------

async function cmdShowReceipts(): Promise<void> {
  // Focus the activity-bar view; the ReceiptsViewProvider does the fetch.
  await vscode.commands.executeCommand("workbench.view.extension.tars-tab");
  await vscode.commands.executeCommand("tars.receiptsView.focus");
}

// ---------------------------------------------------------------------------
// Activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  const chatProvider = new ChatViewProvider(context);
  const composerProvider = new ComposerViewProvider(context);
  const receiptsProvider = new ReceiptsViewProvider(context);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("tars.chatView", chatProvider),
    vscode.window.registerWebviewViewProvider("tars.composerView", composerProvider),
    vscode.window.registerWebviewViewProvider("tars.receiptsView", receiptsProvider),
    vscode.commands.registerCommand("tars.openChat", () => cmdOpenChat(context)),
    vscode.commands.registerCommand("tars.composeFromSelection", cmdComposeFromSelection),
    vscode.commands.registerCommand("tars.showReceipts", cmdShowReceipts)
  );
}

export function deactivate(): void {
  // nothing — webview disposables are owned by the extension context.
}
