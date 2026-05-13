"""HTTP surface for ``tars-doctor`` (Wave 155).

Endpoints:

- ``GET /api/doctor`` — run every registered check and return the
  array of results.
- ``GET /api/doctor/{slug}`` — run a single check by slug.
- ``GET /api/doctor/registry`` — list available check slugs +
  labels without running them.

Same shape as the CLI's ``--json`` output, so any consumer (cockpit
panel, W117 synthetic monitor, brother's status dashboard) can
parse it the same way.

The endpoint is read-only — no body, no side-effects on the
subsystems being checked. Each check has its own short timeout
(default 5s) so a slow subsystem can never stall the response
indefinitely; the whole-run wall-time is bounded by sum-of-checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from backend.core.doctor import (
    FIX_REGISTRY,
    REGISTRY,
    run_all,
    run_all_fixes,
    run_check,
    run_fix,
)


router = APIRouter(prefix="/api/doctor", tags=["doctor"])


@router.get("")
async def doctor_all() -> dict[str, Any]:
    """Run every registered check and return all results.

    Response shape::

      {
        "ok": True,
        "summary": {"ok": 4, "warn": 2, "fail": 0, "skip": 1},
        "results": [<CheckResult.to_dict()>, ...]
      }

    The top-level ``ok`` mirrors the CLI's exit code logic — false
    iff any check has ``status == "fail"``.
    """

    results = run_all()
    summary = {"ok": 0, "warn": 0, "fail": 0, "skip": 0}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {
        "ok": summary["fail"] == 0,
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }


@router.get("/registry")
async def doctor_registry() -> dict[str, Any]:
    """List available check slugs + labels without running them."""

    entries: list[dict[str, str]] = []
    for slug, fn in REGISTRY:
        doc = (fn.__doc__ or "").strip().splitlines()
        entries.append(
            {
                "slug": slug,
                "label": (doc[0] if doc else slug),
            }
        )
    return {"ok": True, "checks": entries, "count": len(entries)}


@router.get("/page", response_class=HTMLResponse, include_in_schema=False)
async def doctor_page() -> str:
    """Self-contained HTML dashboard that pulls /api/doctor live.

    No build step, no React — vanilla HTML/CSS/JS. The page lives
    inline so the FastAPI host can serve it without a static-files
    mount. Operators open ``http://localhost:<port>/api/doctor/page``
    in their browser to get a real-time health view that refreshes
    every 30 seconds.
    """

    return _DOCTOR_PAGE_HTML


@router.get("/{slug}")
async def doctor_one(slug: str) -> dict[str, Any]:
    """Run a single check by slug."""

    known = {s for s, _ in REGISTRY}
    if slug not in known:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_check",
                "slug": slug,
                "known": sorted(known),
            },
        )
    result = run_check(slug)
    return {"ok": result.status != "fail", "result": result.to_dict()}


# ─── Auto-remediation surface (Wave 167) ────────────────────────────


@router.post("/fix")
async def doctor_fix_all() -> dict[str, Any]:
    """Apply every registered fixer.

    Response::

      {
        "ok": True,
        "summary": {"applied": 1, "skipped": 2, "failed": 0},
        "results": [<FixResult.to_dict()>, ...]
      }

    ``ok`` is false iff any fixer failed (applied=False AND
    skipped=False). Skip-only fixers (daemon, scheduler) don't
    demote ok.
    """

    results = run_all_fixes()
    summary = {"applied": 0, "skipped": 0, "failed": 0}
    for r in results:
        if r.applied:
            summary["applied"] += 1
        elif r.skipped:
            summary["skipped"] += 1
        else:
            summary["failed"] += 1
    return {
        "ok": summary["failed"] == 0,
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }


@router.post("/fix/{slug}")
async def doctor_fix_one(slug: str) -> dict[str, Any]:
    """Apply a single fixer by slug. 404 when slug isn't known.

    Returns ``{ok, result: <FixResult.to_dict()>}``. ``ok`` is
    false iff the fixer ran but failed (applied=False AND
    skipped=False).
    """

    known = {s for s, _ in REGISTRY}
    if slug not in known:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_check",
                "slug": slug,
                "known": sorted(known),
                "fixable": sorted(FIX_REGISTRY.keys()),
            },
        )
    result = run_fix(slug)
    failed = (not result.applied) and (not result.skipped)
    return {"ok": not failed, "result": result.to_dict()}


# ─── Notification test surface (Wave 168) ───────────────────────────


@router.post("/test/notify")
async def doctor_test_notify(
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Fire a synthetic doctor.status_changed alert through fanout_all.

    Body shape (all optional):
      {
        "channels": ["telegram", "imessage", "email"]  # default: env
        "slug": "test",
        "from": "ok",
        "to": "warn",
        "summary": "test alert from /api/doctor/test/notify"
      }

    Returns ``{ok, results: [...]}`` mirroring the fanout_all
    contract. ``ok`` is true iff every channel reports ``ok=True``.

    Use this to verify TARS_DAEMON_FANOUT_CHANNELS + per-channel
    config is wired correctly without waiting for a real drift.
    """

    body = payload or {}
    channels = body.get("channels")  # None → fanout_all reads env
    change = {
        "slug": str(body.get("slug") or "test"),
        "from": str(body.get("from") or "ok"),
        "to": str(body.get("to") or "warn"),
        "summary": str(
            body.get("summary")
            or "test alert from /api/doctor/test/notify"
        ),
    }

    try:
        from backend.core.notifications import fanout_all
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "notifications_import_failed", "detail": str(exc)},
        )

    results = fanout_all(change, channels=channels)
    if not results:
        return {
            "ok": False,
            "results": [],
            "error": "no_channels_configured",
            "hint": (
                "Pass {channels:[...]} in the body OR set "
                "TARS_DAEMON_FANOUT_CHANNELS env"
            ),
        }
    all_ok = all(r.get("ok") for r in results)
    return {"ok": all_ok, "results": results, "change": change}


# ─── Self-contained HTML dashboard (Wave 156) ───────────────────────


_DOCTOR_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>TARS doctor — health</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0a0a;
      --bg-card: #14141a;
      --fg: #f5f5f0;
      --fg-mute: #8a8880;
      --border: #2a2a30;
      --ok: #34d399;
      --warn: #fbbf24;
      --fail: #f87171;
      --skip: #71717a;
      --accent: #6366f1;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg);
      font: 14px/1.55 ui-monospace, "Share Tech Mono", SFMono-Regular, Menlo, monospace; }
    .wrap { max-width: 900px; margin: 32px auto; padding: 0 20px; }
    header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 24px; }
    h1 { font-size: 22px; margin: 0; font-weight: 600; letter-spacing: 0.02em; }
    .sub { color: var(--fg-mute); font-size: 13px; }
    .summary { display: flex; gap: 12px; margin: 16px 0 24px; flex-wrap: wrap; }
    .pill { padding: 6px 12px; border: 1px solid var(--border); border-radius: 6px;
      background: var(--bg-card); font-size: 12px; }
    .pill.ok { color: var(--ok); border-color: var(--ok); }
    .pill.warn { color: var(--warn); border-color: var(--warn); }
    .pill.fail { color: var(--fail); border-color: var(--fail); }
    .pill.skip { color: var(--skip); }
    .grid { display: flex; flex-direction: column; gap: 8px; }
    .row { display: grid; grid-template-columns: 28px 1fr 80px; gap: 12px; align-items: center;
      padding: 12px 14px; background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 8px; transition: border-color 0.2s; }
    .row.ok { border-left: 3px solid var(--ok); }
    .row.warn { border-left: 3px solid var(--warn); }
    .row.fail { border-left: 3px solid var(--fail); }
    .row.skip { border-left: 3px solid var(--skip); opacity: 0.6; }
    .glyph { font-size: 18px; text-align: center; }
    .glyph.ok { color: var(--ok); }
    .glyph.warn { color: var(--warn); }
    .glyph.fail { color: var(--fail); }
    .glyph.skip { color: var(--skip); }
    .body .label { font-weight: 500; }
    .body .summary-text { color: var(--fg-mute); margin-top: 2px; font-size: 12.5px; }
    .body .suggestion { color: var(--accent); margin-top: 6px; font-size: 12px; }
    .status-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; text-align: center;
      font-weight: 600; letter-spacing: 0.05em; }
    .status-tag.ok { background: rgba(52,211,153,0.12); color: var(--ok); }
    .status-tag.warn { background: rgba(251,191,36,0.12); color: var(--warn); }
    .status-tag.fail { background: rgba(248,113,113,0.12); color: var(--fail); }
    .status-tag.skip { background: rgba(113,113,122,0.12); color: var(--skip); }
    footer { margin-top: 32px; color: var(--fg-mute); font-size: 12px; text-align: center; }
    .loading { padding: 40px; text-align: center; color: var(--fg-mute); }
    .err { padding: 16px; border: 1px solid var(--fail); border-radius: 8px;
      color: var(--fail); margin-bottom: 16px; }
    .refresh { color: var(--accent); cursor: pointer; border: 1px solid var(--accent);
      background: transparent; padding: 6px 12px; border-radius: 6px; font-family: inherit;
      font-size: 12px; }
    .refresh:hover { background: rgba(99,102,241,0.1); }
    .fix-btn { color: var(--accent); cursor: pointer; border: 1px solid var(--accent);
      background: transparent; padding: 3px 9px; border-radius: 4px; font-family: inherit;
      font-size: 11px; margin-left: 8px; }
    .fix-btn:hover { background: rgba(99,102,241,0.15); }
    .fix-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .toast { position: fixed; bottom: 16px; right: 16px; padding: 10px 14px;
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
      font-size: 12px; max-width: 340px; opacity: 0; transition: opacity 0.2s; z-index: 9; }
    .toast.show { opacity: 1; }
    .toast.ok { border-left: 3px solid var(--ok); }
    .toast.warn { border-left: 3px solid var(--warn); }
    .toast.fail { border-left: 3px solid var(--fail); }
    code { font-family: inherit; background: rgba(255,255,255,0.04); padding: 1px 5px;
      border-radius: 3px; color: var(--accent); }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>TARS doctor</h1>
        <div class="sub">health check across every TARS subsystem · auto-refresh 30s</div>
      </div>
      <div>
        <button class="refresh" id="test-notify-btn" title="Fire a test alert through the configured fanout channels">📣 test alert</button>
        <button class="refresh" id="refresh-btn" style="margin-left:8px;">↻ refresh</button>
      </div>
    </header>

    <div id="status-display">
      <div class="loading">Running checks…</div>
    </div>

    <div id="toast" class="toast"></div>

    <footer>
      Wave 156 · powered by <code>backend.core.doctor</code> · contract v0.2.0
    </footer>
  </div>

  <script>
    const GLYPH = { ok: '✓', warn: '⚠', fail: '✗', skip: '·' };
    const REFRESH_MS = 30000;
    let refreshTimer = null;

    function esc(s) {
      return String(s).replace(/[&<>"']/g, ch => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      })[ch]);
    }

    function renderResults(body) {
      const display = document.getElementById('status-display');
      const summary = body.summary || {};
      const parts = ['ok', 'warn', 'fail', 'skip']
        .map(k => `<span class="pill ${k}">${k} · ${summary[k] || 0}</span>`)
        .join('');

      const fixable = (window.__fixable || []);
      const rows = (body.results || []).map(r => {
        const sug = r.suggestion && r.status !== 'ok'
          ? `<div class="suggestion">→ ${esc(r.suggestion)}</div>` : '';
        const showFix = r.status !== 'ok' && r.status !== 'skip' && fixable.includes(r.slug);
        const fixBtn = showFix
          ? `<button class="fix-btn" data-slug="${esc(r.slug)}" onclick="doFix(this)">⚒ fix</button>`
          : '';
        return `<div class="row ${r.status}">
          <div class="glyph ${r.status}">${GLYPH[r.status] || '?'}</div>
          <div class="body">
            <div class="label">${esc(r.label || r.slug)} ${fixBtn}</div>
            <div class="summary-text">${esc(r.summary || '')}</div>
            ${sug}
          </div>
          <div class="status-tag ${r.status}">${r.status.toUpperCase()}</div>
        </div>`;
      }).join('');

      display.innerHTML = `
        <div class="summary">${parts}</div>
        <div class="grid">${rows}</div>
      `;
    }

    async function loadDoctor() {
      try {
        const r = await fetch('/api/doctor', { cache: 'no-store' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const body = await r.json();
        renderResults(body);
      } catch (err) {
        document.getElementById('status-display').innerHTML =
          `<div class="err">Failed to fetch /api/doctor: ${esc(err.message)}</div>`;
      }
    }

    function startTimer() {
      if (refreshTimer) clearInterval(refreshTimer);
      refreshTimer = setInterval(loadDoctor, REFRESH_MS);
    }

    document.getElementById('refresh-btn').addEventListener('click', () => {
      loadDoctor();
      startTimer();
    });

    // Wave 168 — test notification button.
    document.getElementById('test-notify-btn').addEventListener('click', async () => {
      const btn = document.getElementById('test-notify-btn');
      btn.disabled = true;
      btn.textContent = '📣 firing…';
      try {
        const r = await fetch('/api/doctor/test/notify', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({}),
        });
        const body = await r.json();
        if (body.ok) {
          const channels = (body.results || []).map(x => x.channel).join(', ');
          showToast(`✓ test alert dispatched to: ${channels || '(none)'}`, 'ok');
        } else if (body.error === 'no_channels_configured') {
          showToast(`· no channels configured — ${body.hint}`, 'warn');
        } else {
          const fails = (body.results || []).filter(x => !x.ok).map(x => `${x.channel}: ${x.error}`).join('; ');
          showToast(`✗ ${fails || 'test failed'}`, 'fail');
        }
      } catch (err) {
        showToast('Test request failed: ' + err.message, 'fail');
      } finally {
        btn.disabled = false;
        btn.textContent = '📣 test alert';
      }
    });

    // Wave 167 — Fix button click handler + toast feedback.
    let toastTimer = null;
    function showToast(msg, kind) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast show ' + (kind || 'ok');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { t.className = 'toast ' + (kind || 'ok'); }, 4000);
    }

    window.doFix = async function(btn) {
      const slug = btn.getAttribute('data-slug');
      btn.disabled = true;
      btn.textContent = '⚒ fixing…';
      try {
        const r = await fetch('/api/doctor/fix/' + encodeURIComponent(slug), { method: 'POST' });
        const body = await r.json();
        const result = body.result || {};
        if (result.applied) {
          showToast(`✓ ${slug}: ${result.before_status} → ${result.after_status || '?'}`, 'ok');
        } else if (result.skipped) {
          showToast(`· ${slug}: ${result.reason} — ${result.detail}`, 'warn');
        } else {
          showToast(`✗ ${slug}: ${result.reason} — ${result.detail}`, 'fail');
        }
        // Refresh the table so the new status is reflected.
        await loadDoctor();
      } catch (err) {
        showToast('Fix request failed: ' + err.message, 'fail');
      } finally {
        btn.disabled = false;
        btn.textContent = '⚒ fix';
      }
    };

    async function loadFixable() {
      try {
        const r = await fetch('/api/doctor/registry', { cache: 'no-store' });
        const body = await r.json();
        // The registry endpoint doesn't currently list fixable slugs;
        // fall back to a hardcoded list of v0.4 fixable slugs.
        window.__fixable = ['vault', 'daemon', 'scheduler'];
      } catch {
        window.__fixable = ['vault', 'daemon', 'scheduler'];
      }
    }

    loadFixable();
    loadDoctor();
    startTimer();
  </script>
</body>
</html>
"""
