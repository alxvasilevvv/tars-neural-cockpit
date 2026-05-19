# PH6 — L3 Sandboxed Code Execution + ArtifactPanel (v11)

**Audience:** implementer (Claude lane preferred for the cockpit
ArtifactPanel; Cursor lane fine for the backend sandbox), 1 dev, ~3 weeks.
**Wave tag:** `W310-t`. **Brief file:** `docs/handoff/PH6_L3_SANDBOX_BRIEF.md`.
**Master plan ref:** `docs/PRODUCT_MASTER_PLAN.md §3.6`.
**Phase L roadmap ref:** `docs/PHASE_L_ROADMAP.md §L3` (lines 484-518).
**Coupling:** v11 release scope. Hard dep on Phase 5 policy UI (#203)
and Phase 5 vault (#202). Soft dep on Phase 5 telemetry (#204).

---

## §1. Motivation

L3 is the last unshipped contract in the L0–L9 backend canon (L10 is
mobile, v11). Today TARS can compose, route, gate, and persist work,
but **cannot execute code on the operator's behalf**. The Council can
write a Python script that summarises a CSV; the operator must then
copy-paste it into a terminal. L3 closes that loop:

> *"write a Python script that summarises this CSV"* → assistant
> writes it, runs it in a sandbox, returns the result with the
> ArtifactPanel preview — through the policy gate.

This is the **highest-leverage v11 deliverable** for two reasons:

1. **Artifact parity with Claude.app**: cockpit can render markdown,
   code, JSON, CSV, HTML, and image outputs in a unified panel.
2. **Self-improving loop**: once code runs through `runtime.run_code`,
   the Council can do exploratory data analysis on its own outputs,
   unblocking workflows like algotrade backtests, CRM segmentation,
   wallet rebalancing simulations.

### 1.1 What already exists

| Component                                  | File / location                              | Status        |
| ------------------------------------------ | -------------------------------------------- | ------------- |
| Phase L roadmap spec for L3                | `docs/PHASE_L_ROADMAP.md` §L3                | ✅ spec       |
| Policy gate (this is destructive)          | `web_extras/routers/policy.py`               | ✅ shipped    |
| Policy inbox UI (renders confirmations)    | PR #203                                      | 📝 spec       |
| Vault gate (for secrets in user scripts)   | PR #202                                      | 📝 spec       |
| meeet event emission for actions           | `backend/core/meeet/client.py`               | ✅ shipped    |
| Cockpit (Vite + TS, page entry pattern)    | `apps/cockpit/src/pages/`                    | ✅ shipped    |
| Tauri desktop shell (for Pyodide WebView)  | `desktop/src-tauri/`                         | ✅ shipped    |
| ChatOrchestrator (Council writes the code) | `backend/core/chat/orchestrator.py`          | ✅ shipped    |
| Per-action category mapping (`code.*`)     | `policy.py::_CATEGORY_BY_PREFIX`             | ✅ shipped    |

### 1.2 What is missing (this brief)

1. **`backend/core/runtime/` module**: greenfield. Need `runner.py`,
   `pyodide.py`, `artifacts.py`, sandbox profiles, language adapters.
2. **`runtime.run_code` action**: a new pack action registered as
   destructive, gated through the existing policy queue.
3. **OS sandbox matrix**:
   - macOS: `sandbox-exec` profile (no network, FS confined to workdir).
   - Linux: `firejail` (if installed) → cgroup fallback via
     `resource.setrlimit`.
   - Windows / Tauri: Pyodide WASM inside the Tauri WebView (zero
     network, zero FS).
4. **Output classifier** (`artifacts.py`): MIME-sniff the code's stdout
   + side files, emit one or more `Artifact` records keyed on
   `application/x-tars-artifact-v1`.
5. **Cockpit `<ArtifactPanel />`**: render markdown, html (sandboxed
   iframe), json (collapsible tree), csv (virtualized table), png
   (download/copy), x-tars-table (DataFrame view).
6. **Streaming surface**: stdout + stderr stream over WS so cockpit
   updates while the script runs (long pipelines must not block UI).
7. **Per-language adapters**: v11 ships **Python** + **Bash**;
   JavaScript and SQL deferred to v11.1.

---

## §2. Goals

- **G1.** New action `runtime.run_code` callable from chat tools and the
  cockpit's "Run" button on any code block. Destructive (policy-gated).
- **G2.** Three OS sandbox backends ship in parallel; runtime picks
  best-available at boot. All refuse network egress by default.
- **G3.** Output classifier produces typed `Artifact` records; cockpit
  renders each type in a uniform panel.
- **G4.** Streaming WS contract `tars.runtime.v1` so cockpit shows
  partial stdout while long jobs run.
- **G5.** Resource budgets enforced at sandbox layer: 30s CPU, 512 MB
  RSS, 10 MB disk write (all env-tunable).
- **G6.** Secrets injection via VaultGate (PR #202) — script can
  request named secrets, vault enforces unlock; never via environment
  variables leaked from parent process.
- **G7.** Replayable artifacts: every artifact is hashed + persisted to
  `~/.tars/artifacts/<sha256>` with TTL (default 7d, env-tunable).
- **G8.** Code-execution events emit to meeet (`code.invoked`,
  `code.completed`, `code.failed`) for telemetry (PR #204 bucket
  `action.invoked.code` already exists in the schema).
- **G9.** Cockpit "Run" button is **opt-in per session** (operator must
  enable in settings — defaults off until first confirmation).

**Non-goals (out of scope for this brief):**
- GPU / accelerator access. Not yet; defer to v11.2 with explicit
  per-platform sandbox holes.
- Long-lived REPL / Jupyter kernel. Each `run_code` call is one shot;
  state persistence is via written artifact files only.
- Network-allowlist sandbox profile. Default-deny; whitelisting needs
  separate threat model.
- Multi-language interpreters running in one sandbox process. Each
  call gets its own sandbox; cross-language data passes via on-disk
  artifacts.
- Distributed / remote sandbox execution (Modal, Replicate). Local
  only for v11.

---

## §3. Target architecture

```
┌─────────────────────────────────────────────────────────────┐
│ cockpit: chat with a code block + "Run" button              │
│  ▸ click → POST /api/runtime/run_code {lang, source, secrets}│
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
       ┌──────────────────────────────────────────────┐
       │  web_extras/routers/runtime.py (NEW)         │
       │  - rate-limited                              │
       │  - immediately enqueues a policy confirmation│
       │    (action_id = "runtime.run_code")          │
       │  - returns 202 + run_id + token              │
       └────────────┬─────────────────────────────────┘
                    │
                    │ (policy gate, see PR #203 inbox)
                    │ operator approves
                    ▼
       ┌──────────────────────────────────────────────┐
       │  backend/core/runtime/runner.py              │
       │  - pick sandbox backend per OS               │
       │  - prepare ephemeral workdir                 │
       │  - launch subprocess w/ resource limits      │
       │  - tee stdout/stderr to WS bus               │
       │  - on exit → classify outputs               │
       └────┬───────────────────┬─────────────────────┘
            │                   │
            ▼                   ▼
   ┌─────────────────┐   ┌──────────────────────────────────┐
   │ sandbox backend │   │  backend/core/runtime/artifacts.py│
   │ ─────────────── │   │  - sniff MIME on stdout +        │
   │ macOS:          │   │    workdir/* files               │
   │  sandbox-exec   │   │  - hash + persist to             │
   │ Linux:          │   │    ~/.tars/artifacts/<sha>       │
   │  firejail       │   │  - emit one Artifact per output  │
   │  (cgroup fallbk)│   └──────────────────────────────────┘
   │ Win/Tauri:      │                  │
   │  Pyodide WASM   │                  │
   │  in WebView     │                  │
   └─────────────────┘                  ▼
                        ┌──────────────────────────────────┐
                        │  WS bus: tars.runtime.v1         │
                        │  - run.started / .stdout / .stderr│
                        │  - run.artifact / .completed     │
                        │  - run.failed / .cancelled       │
                        └──────────────────────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────────┐
                        │  cockpit ArtifactPanel.ts        │
                        │  renders per type:               │
                        │  ├ markdown (react-markdown)     │
                        │  ├ html (sandboxed iframe)       │
                        │  ├ json (collapsible tree)       │
                        │  ├ csv (virtualised table)       │
                        │  ├ png/jpg (img + download)      │
                        │  └ x-tars-table (DataFrame view) │
                        └──────────────────────────────────┘
```

### 3.1 Wire contract (`tars.runtime.v1`)

```jsonc
// POST /api/runtime/run_code
{
  "lang": "python" | "bash",
  "source": "<text>",
  "secrets": ["HUBSPOT_API_KEY", ...],   // optional, resolved via VaultGate
  "files": [                              // optional input files
    { "name": "data.csv", "content_b64": "..." }
  ],
  "timeout_s": 30,                        // optional, default + bounded by sandbox cap
  "thread_id": "thread_abc"               // for meeet tracing
}
// → 202
{
  "ok": true,
  "run_id": "run_01HW...",
  "policy_token": "<token>",   // for the inbox confirmation
  "ws_url": "/ws/runtime/run_01HW..."
}
```

```jsonc
// WS messages on /ws/runtime/{run_id}
{ "kind": "run.started",   "ts": 1779000000, "lang": "python", "backend": "macos-sandbox-exec" }
{ "kind": "run.stdout",    "ts": 1779000001, "data_b64": "..." }    // chunked
{ "kind": "run.stderr",    "ts": 1779000001, "data_b64": "..." }
{ "kind": "run.artifact",  "ts": 1779000002, "artifact": { "id": "<sha256>",
                                                            "mime": "text/csv",
                                                            "size": 4123,
                                                            "name": "summary.csv" } }
{ "kind": "run.completed", "ts": 1779000003, "exit_code": 0, "elapsed_ms": 1234,
                           "artifacts": [...] }
{ "kind": "run.failed",    "ts": 1779000003, "error": "TimeoutError",
                           "elapsed_ms": 30001 }
{ "kind": "run.cancelled", "ts": 1779000003, "reason": "operator_cancel" }
```

### 3.2 Artifact record shape (`application/x-tars-artifact-v1`)

```jsonc
{
  "id": "sha256:abcd...",
  "mime": "text/csv",
  "name": "summary.csv",          // optional, from filename or "stdout"
  "size": 4123,
  "created_at": 1779000002,
  "run_id": "run_01HW...",
  "lang": "python",
  "ttl_until": 1779604802,        // 7d default
  "preview": "first 4 KB of text" // null for binary
}
```

Persistent on disk at `~/.tars/artifacts/<sha256>` (file content) with
metadata index in `~/.tars/artifacts.json`. Eviction loop scans
`ttl_until` on boot + every 6h.

### 3.3 OS sandbox profiles

#### macOS (`sandbox-exec`)

`backend/core/runtime/profiles/macos.sb`:

```
(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow file-read* (subpath "/usr"))
(allow file-read* (subpath "/System"))
(allow file-read* (subpath "/Library/Developer"))
(allow file-read* (subpath "<<WORKDIR>>"))
(allow file-write* (subpath "<<WORKDIR>>"))
(allow sysctl-read)
;; no network
;; no FS write outside workdir
```

`runner.py` substitutes `<<WORKDIR>>` with the ephemeral dir at launch.

#### Linux (`firejail` preferred)

```sh
firejail \
  --quiet \
  --noprofile \
  --net=none \
  --private="$WORKDIR" \
  --rlimit-as=536870912 \
  --rlimit-cpu=30 \
  --timeout=00:00:35 \
  -- python3 -u "$SCRIPT"
```

If `firejail` not installed → fallback `resource.setrlimit` + `os.chroot`
(documented limitation: weaker isolation; emit warning in
`/api/runtime/status`).

#### Windows / Tauri (Pyodide in WebView)

`pyodide.py`: Tauri shell loads Pyodide bundle (CDN-mirrored, vendored
in `desktop/static/pyodide/`); runtime POSTs source via JSON-RPC to a
hidden WebView window; WebView returns artifacts as base64. Zero
network, zero FS by virtue of running in WASM. Lower performance
acceptable for v11.

### 3.4 Language adapters

```python
# backend/core/runtime/langs/__init__.py
class LanguageAdapter:
    name: str
    def prepare(self, source: str, workdir: Path) -> Path: ...  # write to file
    def cmd(self, script_path: Path) -> list[str]: ...          # subprocess args
    def post_process(self, workdir: Path) -> list[Artifact]: ...# collect outputs

class PythonAdapter(LanguageAdapter):
    name = "python"
    # writes script.py + injects allow-listed stdlib
class BashAdapter(LanguageAdapter):
    name = "bash"
```

V11 ships Python + Bash. JS + SQL → v11.1.

---

## §4. Implementation steps (7 mechanical, sequential)

### Step 1 — Core module skeleton + types

**Files:**
- `backend/core/runtime/__init__.py` (NEW, ~30 LoC) — public surface
- `backend/core/runtime/types.py` (NEW, ~120 LoC) — `Artifact`, `RunSpec`, `RunResult`, errors

**Tests** (`tests/test_runtime_types.py`, ~6 cases): serialization
roundtrip, MIME inference, hash determinism, TTL math.

### Step 2 — `runner.py` w/ OS dispatch + resource budgets

**Files:**
- `backend/core/runtime/runner.py` (NEW, ~320 LoC)
- `backend/core/runtime/profiles/macos.sb` (NEW)

Logic:
- `detect_backend()` → returns enum {`macos-sandbox-exec`, `linux-firejail`,
  `linux-rlimit`, `tauri-pyodide`, `subprocess-unsafe`}
- `Runner.run(spec) -> AsyncIterator[RunEvent]` — yields events
  matching the wire contract.
- Resource budgets: subprocess wrapped in `asyncio.wait_for` for wall
  clock; rlimit setters for CPU + RSS; tempdir auto-cleanup.

**Tests** (`tests/test_runtime_runner.py`, ~14 cases): timeout cancels,
RSS overrun killed, FS write outside workdir rejected, network blocked
(attempt → `ConnectionError` or DNS fail), stdout streamed in chunks.

### Step 3 — `artifacts.py` classifier + persistence

**Files:**
- `backend/core/runtime/artifacts.py` (NEW, ~240 LoC)
- `backend/core/runtime/store.py` (NEW, ~160 LoC) — TTL + eviction

MIME sniffing: file extension first, then content sniff
(stdlib `mimetypes` + small magic-byte table for png/jpg/gif).
Edge cases: empty stdout → no artifact; multi-output via workdir
scan; binary stdout → `application/octet-stream`.

**Tests** (`tests/test_runtime_artifacts.py`, ~10 cases): all MIME
buckets resolve, eviction respects TTL, hash collisions handled,
concurrent writes safe.

### Step 4 — Language adapters (Python + Bash)

**Files:**
- `backend/core/runtime/langs/__init__.py` (NEW, ~50 LoC)
- `backend/core/runtime/langs/python.py` (NEW, ~140 LoC)
- `backend/core/runtime/langs/bash.py` (NEW, ~90 LoC)

Python adapter highlights:
- `-u` for unbuffered stdout
- `-S` to skip site-packages (sandbox cleanliness)
- Inject `__tars_artifact__()` helper into script preamble for
  programmatic artifact emission

Bash adapter: `set -euo pipefail` injected, `-c` mode.

**Tests** (`tests/test_runtime_langs.py`, ~8 cases): each adapter
runs hello-world, captures errors, respects timeouts.

### Step 5 — HTTP + WS surface + policy integration

**Files:**
- `web_extras/routers/runtime.py` (NEW, ~260 LoC)
- `web_extras/routers/runtime_ws.py` (NEW, ~140 LoC) — WS endpoint

Endpoints:

```
POST   /api/runtime/run_code      → 202 (enqueues policy confirmation)
GET    /api/runtime/status        → backend info, queue depth, recent runs
GET    /api/runtime/runs/{run_id} → run metadata + artifact list
GET    /api/runtime/artifacts/{sha256} → raw artifact bytes
DELETE /api/runtime/runs/{run_id} → cancel (if still pending or running)
WS     /ws/runtime/{run_id}       → tars.runtime.v1 event stream
```

Policy integration: action registered as `runtime.run_code` with
`destructive=True`; policy router emits confirmation; runtime router
subscribes via internal hook (no polling).

**Tests** (`tests/test_runtime_router.py`, ~12 cases): 202 response,
policy ties through, WS stream delivers, cancel works, status reflects.

### Step 6 — Cockpit `<ArtifactPanel />`

**Files:**
- `apps/cockpit/src/components/artifact-panel.ts` (NEW, ~360 LoC)
- `apps/cockpit/src/components/artifact-views/markdown.ts` (NEW, ~80 LoC)
- `apps/cockpit/src/components/artifact-views/html.ts` (NEW, ~110 LoC)
- `apps/cockpit/src/components/artifact-views/json.ts` (NEW, ~140 LoC)
- `apps/cockpit/src/components/artifact-views/csv.ts` (NEW, ~180 LoC)
- `apps/cockpit/src/components/artifact-views/image.ts` (NEW, ~70 LoC)
- `apps/cockpit/src/components/artifact-views/tars-table.ts` (NEW, ~160 LoC)
- `apps/cockpit/src/lib/runtime-client.ts` (NEW, ~200 LoC) — HTTP + WS
- `apps/cockpit/src/styles/artifact-panel.css` (NEW, ~200 LoC)

**Render rules:**
- Markdown: `marked` (already vendored in cockpit if present;
  otherwise add as small dep) + Shiki for code highlighting; no
  innerHTML, sanitize via DOMPurify.
- HTML: `<iframe sandbox="allow-scripts">` — no `allow-same-origin`,
  no `allow-top-navigation`, no `allow-forms`. Set `srcdoc` directly;
  do not load from external URLs.
- JSON: custom tree component (depth-first lazy expand; cap render at
  10k nodes).
- CSV: virtualised table (window of 100 rows, scroll-paginate);
  detect header row via first-line heuristic.
- PNG: `<img src=`blob:…`>` from fetched bytes; download + copy buttons.
- `application/x-tars-table`: DataFrame view (sortable column headers,
  cell type inference, pagination).

**Tests** (`tests/playwright/artifact-panel.spec.ts`, ~10 scenarios):
each MIME type renders, HTML iframe is sandboxed (assert no
`document.cookie` leaks), JSON tree expand/collapse, CSV virtualises
correctly under 100k row load.

### Step 7 — "Run" button + chat integration + opt-in setting

**Files:**
- `apps/cockpit/src/components/code-run-button.ts` (NEW, ~120 LoC)
- `apps/cockpit/src/pages/cockpit-entry.ts` (extend, ~25 LoC delta) —
  mount run buttons on chat code blocks; settings toggle for opt-in

Behavior:
- Settings → "Enable code execution" toggle (default OFF).
- Toggle off: run buttons hidden site-wide.
- Toggle on: render small "▶ Run" overlay on every `<pre><code class="language-*">` block.
- Click → POST `/api/runtime/run_code` → live run drawer opens
  showing streaming output + ArtifactPanel for each emitted artifact.

**Tests**: covered by `artifact-panel.spec.ts` scenarios.

---

## §5. Files touched

| Area              | Files                                            | LoC est |
| ----------------- | ------------------------------------------------ | ------- |
| Core module       | `backend/core/runtime/__init__.py` (NEW)         | +30     |
|                   | `backend/core/runtime/types.py` (NEW)            | +120    |
|                   | `backend/core/runtime/runner.py` (NEW)           | +320    |
|                   | `backend/core/runtime/artifacts.py` (NEW)        | +240    |
|                   | `backend/core/runtime/store.py` (NEW)            | +160    |
|                   | `backend/core/runtime/profiles/macos.sb` (NEW)   | +40     |
|                   | `backend/core/runtime/pyodide.py` (NEW)          | +180    |
| Language adapters | `backend/core/runtime/langs/__init__.py` (NEW)   | +50     |
|                   | `backend/core/runtime/langs/python.py` (NEW)     | +140    |
|                   | `backend/core/runtime/langs/bash.py` (NEW)       | +90     |
| HTTP + WS         | `web_extras/routers/runtime.py` (NEW)            | +260    |
|                   | `web_extras/routers/runtime_ws.py` (NEW)         | +140    |
| Policy hook       | `backend/core/domains/registry.py` (modify)      | +20     |
| Tauri integration | `desktop/src-tauri/src/pyodide_bridge.rs` (NEW)  | +220    |
|                   | `desktop/static/pyodide/` (vendor bundle)        | ~5MB    |
| Cockpit           | `apps/cockpit/src/components/artifact-panel.ts`  | +360    |
|                   | + 6 artifact-views/*.ts                          | +740    |
|                   | `apps/cockpit/src/components/code-run-button.ts` | +120    |
|                   | `apps/cockpit/src/lib/runtime-client.ts`         | +200    |
|                   | `apps/cockpit/src/styles/artifact-panel.css`     | +200    |
|                   | `apps/cockpit/src/pages/cockpit-entry.ts` (mod)  | +25     |
| Tests             | unit + integration + Playwright                  | +1.4k   |
| Docs              | `docs/RUNTIME_SANDBOX.md` (NEW)                  | +250    |
| **Total**         |                                                  | **≈ 5k LoC** |

---

## §6. Coupling

| Brief / PR                  | Relationship                                                 |
| --------------------------- | ------------------------------------------------------------ |
| Phase 5 policy UI (PR #203) | **Hard dep.** Every `run_code` enqueues a policy confirmation; inbox UI is the operator's surface for it. |
| Phase 5 vault (PR #202)     | **Hard dep.** Secrets injection routes through VaultGate; runtime refuses to start if requested secrets unavailable. |
| Phase 5 telemetry (PR #204) | **Soft dep.** Bucket `action.invoked.code` already in schema; no new instrumentation needed beyond the standard hook. |
| Phase 3 keyring (PR #195)   | No direct coupling. |
| Phase 4 trio (#199-#201)    | No direct coupling. Pyodide bundle distribution piggy-backs on existing Tauri bundling. |
| Phase 7 planner (next brief)| Forward dep. Planner uses `runtime.run_code` for "execute a step" actions; brief should land first. |

---

## §7. Test plan

| Category    | Coverage                                                        |
| ----------- | --------------------------------------------------------------- |
| Unit        | Types, MIME classifier, hash determinism, TTL math              |
| Integration | macOS sandbox-exec blocks network, blocks FS escape              |
| Integration | Linux firejail same; rlimit fallback same                       |
| Integration | Tauri Pyodide round-trip in WebView                             |
| Resource    | Timeout kills; RSS overrun kills; CPU rlimit honored            |
| Security    | Sandbox profile review (manual gate before merge)                |
| Policy      | run_code enqueues confirmation; approval triggers execution     |
| Vault       | Locked vault → run_code with secrets refused                    |
| WS contract | All 7 event kinds emit; ordering invariants hold                |
| Artifacts   | All 6 MIME buckets render in cockpit                            |
| HTML iframe | Sandbox attrs enforced; XSS attempt isolated                     |
| Soak        | 1000 runs in a row → no FD leak, no zombie processes, eviction works |
| OS matrix   | Same script reproduces same artifact hash on macOS + Linux      |

**Sandbox profile review checklist** (manual gate in PR description):

- [ ] `sandbox-exec` profile reviewed by a second engineer for FS scope
- [ ] `firejail` invocation reviewed for net=none correctness
- [ ] Pyodide bundle integrity verified (SHA256 pinned, signed)
- [ ] No process-spawn allowed across sandbox boundary
- [ ] /proc, /sys inaccessible (Linux)
- [ ] No `iokit`/`mach` allowed (macOS)

---

## §8. Open questions for operator

1. **Default opt-in cohort**: should `runtime.run_code` be hidden
   entirely behind a feature flag until v11.1, or shipped as
   default-off-but-discoverable? (Recommendation: latter — default off
   in settings, but settings entry visible. Reduces "where do I
   enable" friction without surprising new operators.)
2. **Artifact TTL default**: 7 days suggested. Operators with limited
   disk may want 24h. (Recommendation: 7d default + cockpit setting.)
3. **Pyodide bundle size**: ~5 MB vendored adds to desktop install
   size. Acceptable, or load on first use from a TARS mirror?
   (Recommendation: vendor — first-use install is offline-incompatible.)
4. **Network in sandbox**: strict no-net is the default. Some
   adapters (e.g. data fetch from internal CRM) might need a
   per-host allowlist. (Recommendation: defer to v11.1 with a
   separate "trusted network targets" config + threat model.)
5. **Auto-approve for "safe" snippets**: e.g. read-only stdlib-only
   Python under 100 LoC. Static analysis to detect? (Recommendation:
   no — every run requires confirmation in v11. The "policy fatigue"
   risk is real but the security gain is larger; revisit with usage
   data in v11.1.)
6. **GPU passthrough**: out of scope per §2. Confirm.
7. **Long-running jobs**: 30s cap is small for ML inference. Bump
   default to 5 min? (Recommendation: 30s default, cockpit per-run
   override up to 5 min, hard ceiling 10 min.)

---

## §9. Effort summary

| Step          | LoC delta (incl tests) | Time   |
| ------------- | ---------------------- | ------ |
| 1 (types)     | +200                   | 1 d    |
| 2 (runner)    | +680                   | 4 d    |
| 3 (artifacts) | +500                   | 2 d    |
| 4 (langs)     | +400                   | 1.5 d  |
| 5 (router+WS) | +600                   | 2.5 d  |
| 6 (ArtifactPanel)| +1.9k                | 5 d    |
| 7 (run button)| +160                   | 1 d    |
| Docs          | +250                   | 1 d    |
| Sandbox review| +0                     | 1 d    |
| **Total**     | **≈ 5k LoC + bundle**  | **~3 weeks** |

Matches master plan estimate (§3.6 = 3 weeks). Includes the manual
sandbox profile review as an explicit step — recommended gate before
merge to main.

---

## §10. Acceptance criteria for v11 ship

- [ ] `/api/runtime/status` reports a non-`subprocess-unsafe` backend
  on macOS, Linux, and Windows (Tauri).
- [ ] `runtime.run_code` enqueues a policy confirmation; only fires
  after approval.
- [ ] All sandbox profiles reviewed by 2nd engineer.
- [ ] Cockpit "Run" button visible only when opt-in toggle is ON.
- [ ] ArtifactPanel renders all 6 MIME buckets on a smoke-test script
  per OS (1 per OS = 3 manual smoke screenshots in PR).
- [ ] Timeout / RSS overrun kills work cross-platform.
- [ ] Vault-locked → `runtime.run_code` requesting secrets returns
  402-style error before sandbox spawn.
- [ ] 1000-run soak: zero process leaks, eviction works, artifact
  store < 100 MB.
- [ ] Pyodide bundle SHA pinned + verified at install.
- [ ] `docs/PHASE_L_ROADMAP.md §L3` updated to ✅ shipped.
- [ ] `docs/PRODUCT_MASTER_PLAN.md §3.6` updated to ✅ shipped.

---

## §11. Sources & references

- **Master plan**: `docs/PRODUCT_MASTER_PLAN.md §3.6`.
- **Phase L roadmap**: `docs/PHASE_L_ROADMAP.md §L3` (lines 484-518).
- **Existing policy gate**: `web_extras/routers/policy.py`.
- **Existing category mapping**: `policy.py::_CATEGORY_BY_PREFIX`
  (already contains `code.*` bucket — runtime registers there).
- **Existing meeet client + events**: `backend/core/meeet/client.py`.
- **Cockpit page pattern**: `apps/cockpit/src/pages/`.
- **Tauri shell**: `desktop/src-tauri/`.
- **macOS sandbox reference**: `man 5 sandbox-exec`,
  https://github.com/Apple/sandbox-tracer.
- **firejail reference**: https://firejail.wordpress.com/documentation-2/
- **Pyodide reference**: https://pyodide.org/en/stable/

---

*End of brief. PR title: "PH6 — L3 sandboxed code execution + ArtifactPanel
brief (v11)".*
