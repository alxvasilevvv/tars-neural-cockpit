#!/usr/bin/env bash
# gate_release.sh — single command release-readiness gate for TARS + meeet.world.
#
# Aggregates every machine-checkable signal into one PASS/FAIL run with a
# trace-id, writes the trace to docs/release-evidence/<trace_id>.json, and
# exits non-zero on the first failure.
#
# Steps (in order):
#   1. pytest (TARS backend)
#   2. cockpit-changelog-check + cockpit-tsc + cockpit-test (showcase v3)
#   3. core-bridge e2e smoke (requires BRIDGE_SHARED_SECRET)
#   4. TARS Layer-1 QA agent (scripts/qa_agent, JSON mode)
#   5. (Optional, if QA_BASE_URL is set) Layer-2 qa-suite browser probes
#   6. Aggregated summary written to docs/release-evidence/<trace_id>.json
#
# Env knobs:
#   GATE_SKIP_BRIDGE=1      skip step 3 (useful for local dev without secrets)
#   GATE_SKIP_QA_BROWSER=1  skip step 5 (default skip if no QA_BASE_URL)
#   QA_BASE_URL             enables step 5 (Layer-2 browser probes)
#   QA_REPORT_PATH          override the JSON sink for Layer-1
#   GATE_OUTPUT_DIR         override docs/release-evidence/ path
#
# Exit codes:
#   0 — all green (warnings allowed in QA agents)
#   1 — at least one step failed
#   2 — operator error (missing dependency, bad env)

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PY="${PY:-.venv/bin/python}"
COCKPIT="${COCKPIT:-experiments/neural-showcase-v3}"
OUT_DIR="${GATE_OUTPUT_DIR:-docs/release-evidence}"

TRACE_ID="rel-$(date -u +%Y%m%dT%H%M%S)-$RANDOM"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$OUT_DIR"
EVIDENCE="$OUT_DIR/$TRACE_ID.json"

# Track each step's outcome for the summary file.
declare -a STEPS_NAME=()
declare -a STEPS_STATUS=()
declare -a STEPS_ELAPSED=()
declare -a STEPS_DETAILS=()
HARD_FAILED=0

c_red()   { printf '\033[31m%s\033[0m' "$*"; }
c_grn()   { printf '\033[32m%s\033[0m' "$*"; }
c_yel()   { printf '\033[33m%s\033[0m' "$*"; }
c_dim()   { printf '\033[2m%s\033[0m' "$*"; }

log_step() {
  local name="$1"
  local status="$2"
  local detail="$3"
  case "$status" in
    pass) printf '  [%s] %s %s\n' "$(c_grn 'PASS')" "$name" "$(c_dim "$detail")" ;;
    warn) printf '  [%s] %s %s\n' "$(c_yel 'WARN')" "$name" "$(c_dim "$detail")" ;;
    skip) printf '  [%s] %s %s\n' "$(c_dim 'SKIP')" "$name" "$(c_dim "$detail")" ;;
    fail) printf '  [%s] %s %s\n' "$(c_red 'FAIL')" "$name" "$(c_dim "$detail")" ;;
    *)    printf '  [%s] %s %s\n' "$status" "$name" "$detail" ;;
  esac
}

run_step() {
  local name="$1"
  shift
  local cmd=("$@")
  local start_ts
  start_ts="$(date +%s)"
  printf '\n%s %s\n' "$(c_dim '▶')" "$name"
  if "${cmd[@]}"; then
    local elapsed=$(( $(date +%s) - start_ts ))
    STEPS_NAME+=("$name")
    STEPS_STATUS+=("pass")
    STEPS_ELAPSED+=("$elapsed")
    STEPS_DETAILS+=("ok in ${elapsed}s")
    log_step "$name" pass "${elapsed}s"
    return 0
  else
    local rc=$?
    local elapsed=$(( $(date +%s) - start_ts ))
    STEPS_NAME+=("$name")
    STEPS_STATUS+=("fail")
    STEPS_ELAPSED+=("$elapsed")
    STEPS_DETAILS+=("rc=$rc after ${elapsed}s")
    log_step "$name" fail "rc=$rc"
    HARD_FAILED=1
    return $rc
  fi
}

skip_step() {
  local name="$1"
  local reason="$2"
  STEPS_NAME+=("$name")
  STEPS_STATUS+=("skip")
  STEPS_ELAPSED+=("0")
  STEPS_DETAILS+=("$reason")
  log_step "$name" skip "$reason"
}

# ---------------------------------------------------------------
# Step 1 — pytest
# ---------------------------------------------------------------
if [[ ! -x "$PY" ]]; then
  echo "ERROR: $PY not found. Set PY env or run: python -m venv .venv && .venv/bin/pip install -e .[dev]"
  exit 2
fi
run_step "pytest (backend)" env PYTHONPATH=. "$PY" -m pytest -q --tb=line tests || true

# ---------------------------------------------------------------
# Step 2a — changelog public artefact (Cloudflare CI parity)
# ---------------------------------------------------------------
if [[ -f scripts/generate_public_changelog.py ]]; then
  run_step "cockpit-changelog-check" "$PY" scripts/generate_public_changelog.py --check || true
else
  skip_step "cockpit-changelog-check" "scripts/generate_public_changelog.py missing"
fi

# ---------------------------------------------------------------
# Step 2b — cockpit tsc
# ---------------------------------------------------------------
if [[ -d "$COCKPIT" ]]; then
  if command -v pnpm >/dev/null 2>&1; then
    run_step "cockpit-tsc" pnpm --dir "$COCKPIT" exec tsc --noEmit || true
    run_step "cockpit-test (vitest)" pnpm --dir "$COCKPIT" test -- --reporter=basic || true
  else
    skip_step "cockpit-tsc" "pnpm not installed"
    skip_step "cockpit-test (vitest)" "pnpm not installed"
  fi
else
  skip_step "cockpit-tsc" "$COCKPIT/ not present"
  skip_step "cockpit-test (vitest)" "$COCKPIT/ not present"
fi

# ---------------------------------------------------------------
# Step 3 — core-bridge e2e smoke (optional)
# ---------------------------------------------------------------
if [[ "${GATE_SKIP_BRIDGE:-0}" == "1" ]]; then
  skip_step "smoke-core-bridge" "GATE_SKIP_BRIDGE=1"
elif [[ -z "${BRIDGE_SHARED_SECRET:-}" ]]; then
  skip_step "smoke-core-bridge" "BRIDGE_SHARED_SECRET not set"
elif [[ ! -f scripts/smoke_core_bridge_e2e.sh ]]; then
  skip_step "smoke-core-bridge" "smoke script missing"
else
  run_step "smoke-core-bridge" bash scripts/smoke_core_bridge_e2e.sh || true
fi

# ---------------------------------------------------------------
# Step 4 — TARS Layer-1 QA agent (always runs; warn-only)
# ---------------------------------------------------------------
if [[ -d scripts/qa_agent ]]; then
  set +e
  "$PY" -m scripts.qa_agent --json --no-color > "$OUT_DIR/$TRACE_ID.qa-agent.json" 2>"$OUT_DIR/$TRACE_ID.qa-agent.stderr"
  qa_rc=$?
  set -e
  if [[ "$qa_rc" -eq 0 ]]; then
    STEPS_NAME+=("qa-agent (layer-1)")
    STEPS_STATUS+=("pass")
    STEPS_ELAPSED+=("0")
    STEPS_DETAILS+=("ok; report=$OUT_DIR/$TRACE_ID.qa-agent.json")
    log_step "qa-agent (layer-1)" pass "report=$OUT_DIR/$TRACE_ID.qa-agent.json"
  else
    STEPS_NAME+=("qa-agent (layer-1)")
    STEPS_STATUS+=("warn")
    STEPS_ELAPSED+=("0")
    STEPS_DETAILS+=("rc=$qa_rc; report=$OUT_DIR/$TRACE_ID.qa-agent.json")
    log_step "qa-agent (layer-1)" warn "rc=$qa_rc"
    # Layer-1 probes are warn-only in the gate by design.
  fi
else
  skip_step "qa-agent (layer-1)" "scripts/qa_agent missing"
fi

# ---------------------------------------------------------------
# Step 5 — Layer-2 qa-suite browser probes (optional)
# ---------------------------------------------------------------
if [[ "${GATE_SKIP_QA_BROWSER:-0}" == "1" ]]; then
  skip_step "qa-suite (layer-2 browser)" "GATE_SKIP_QA_BROWSER=1"
elif [[ -z "${QA_BASE_URL:-}" ]]; then
  skip_step "qa-suite (layer-2 browser)" "QA_BASE_URL not set"
else
  echo
  echo "▶ qa-suite (layer-2 browser) — base=$QA_BASE_URL"
  echo "  This step lives in the meeet core repo; from this gate we only"
  echo "  surface a reminder. Run there: \`npm run qa:browser\`."
  skip_step "qa-suite (layer-2 browser)" "see meeet core repo (manual)"
fi

# ---------------------------------------------------------------
# Summary + evidence file
# ---------------------------------------------------------------
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Build a JSON evidence file using only python (no jq dependency).
"$PY" - "$EVIDENCE" "$TRACE_ID" "$STARTED_AT" "$FINISHED_AT" "$HARD_FAILED" "${STEPS_NAME[@]}" -- "${STEPS_STATUS[@]}" -- "${STEPS_ELAPSED[@]}" -- "${STEPS_DETAILS[@]}" <<'PY' || true
import json
import sys
from pathlib import Path

argv = sys.argv[1:]
out_path = argv[0]
trace_id = argv[1]
started_at = argv[2]
finished_at = argv[3]
hard_failed = int(argv[4])

# The remaining args come in 4 groups separated by literal "--" tokens.
groups = []
current = []
for arg in argv[5:]:
    if arg == "--":
        groups.append(current)
        current = []
        continue
    current.append(arg)
if current:
    groups.append(current)

names = groups[0] if len(groups) > 0 else []
statuses = groups[1] if len(groups) > 1 else []
elapsed = groups[2] if len(groups) > 2 else []
details = groups[3] if len(groups) > 3 else []

n = max(len(names), len(statuses), len(elapsed), len(details))
steps = []
counters = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
for i in range(n):
    s = {
        "name": names[i] if i < len(names) else "",
        "status": statuses[i] if i < len(statuses) else "skip",
        "elapsed_s": int(elapsed[i]) if i < len(elapsed) and str(elapsed[i]).isdigit() else 0,
        "details": details[i] if i < len(details) else "",
    }
    steps.append(s)
    counters[s["status"]] = counters.get(s["status"], 0) + 1

evidence = {
    "version": "release-gate/1.0.0",
    "trace_id": trace_id,
    "started_at": started_at,
    "finished_at": finished_at,
    "hard_failed": bool(hard_failed),
    "summary": counters,
    "steps": steps,
}

Path(out_path).parent.mkdir(parents=True, exist_ok=True)
Path(out_path).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
PY

echo
echo "─────────────────────────────────────────────────────"
echo "RELEASE GATE  trace_id=$TRACE_ID"
echo "evidence:     $EVIDENCE"
if [[ "$HARD_FAILED" == "1" ]]; then
  echo "$(c_red 'RESULT: FAIL')"
  exit 1
fi
echo "$(c_grn 'RESULT: GREEN')"
exit 0
