#!/usr/bin/env bash
# playbooks_morning_cron.sh — single-command cron wrapper for TARS
# morning playbooks.
#
# What it does (in order):
#   1. Discovers every playbook tagged ``morning`` via the
#      playbooks CLI, OR uses ``MORNING_PLAYBOOKS`` if the
#      operator overrode the default (comma-separated ids).
#   2. Runs each playbook sequentially with ``MORNING_MODE``
#      (default ``confirm``; cron should set ``autopilot``).
#   3. Records per-playbook outcome (ok / trace_id / took_ms /
#      error) into an aggregate evidence JSON at
#      ``$MORNING_OUTPUT_DIR/<run_id>.json``.
#   4. Flushes the meeet replay buffer so events from this
#      morning's runs eventually push upstream (skip with
#      ``MORNING_SKIP_REPLAY=1`` if upstream is intentionally
#      down for maintenance).
#   5. Exits non-zero if any playbook failed (so cron alerts
#      fire) or if no morning playbooks were discovered (the
#      "silent green" failure mode we explicitly guard against).
#
# The wrapper is **continue-on-failure** by default: one bad
# playbook doesn't mask the others. Set ``MORNING_FAIL_FAST=1``
# if you need the legacy stop-on-first-failure behaviour.
#
# Cron usage (sample):
#
#   # Every weekday at 06:00 local; autopilot mode; alert on
#   # non-zero (the wrapper exits 1 on any failure, 2 on env
#   # error / no morning playbooks). Stderr surfaces failure
#   # detail; stdout is JSON-friendly for log shippers.
#   0 6 * * 1-5  cd /path/to/jarvis && \
#       MORNING_MODE=autopilot \
#       /path/to/jarvis/scripts/playbooks_morning_cron.sh \
#       >> /var/log/tars-morning.log 2>&1
#
# Exit codes:
#   0 — every playbook completed ok (replay push warnings allowed)
#   1 — at least one playbook failed
#   2 — operator error (no morning playbooks found, missing dep,
#       bad env). Distinct from 1 so cron alerts can route the
#       two failure classes separately.
#
# Env knobs:
#   MORNING_PLAYBOOKS       comma-separated playbook ids; overrides
#                           the tag-based discovery
#   MORNING_MODE            policy mode (autopilot|confirm|dry_run)
#                           default ``confirm``
#   MORNING_OUTPUT_DIR      evidence JSON sink; default ``.morning-runs``
#   MORNING_SKIP_REPLAY     set to ``1`` to skip the meeet flush
#   MORNING_FAIL_FAST       set to ``1`` to stop on first failure
#   MORNING_TAG             tag to discover (default ``morning``);
#                           change to ``evening`` etc. for parallel cron
#   PY                      python interpreter; default ``.venv/bin/python``

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-.venv/bin/python}"
PLAYBOOKS_CLI=( "$PY" -m backend.core.playbooks.cli )
REPLAY_CLI=( "$PY" -m backend.core.meeet.replay_cli )

MODE="${MORNING_MODE:-confirm}"
OUT_DIR="${MORNING_OUTPUT_DIR:-.morning-runs}"
TAG="${MORNING_TAG:-morning}"
FAIL_FAST="${MORNING_FAIL_FAST:-0}"
SKIP_REPLAY="${MORNING_SKIP_REPLAY:-0}"

mkdir -p "$OUT_DIR"

RUN_ID="morning-$(date -u +%Y%m%dT%H%M%S)-$$"
EVIDENCE="$OUT_DIR/$RUN_ID.json"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- ANSI helpers (degrade gracefully when stdout is not a tty) ----
if [[ -t 1 ]]; then
    c_red()   { printf '\033[31m%s\033[0m' "$*"; }
    c_green() { printf '\033[32m%s\033[0m' "$*"; }
    c_dim()   { printf '\033[2m%s\033[0m' "$*"; }
else
    c_red()   { printf '%s' "$*"; }
    c_green() { printf '%s' "$*"; }
    c_dim()   { printf '%s' "$*"; }
fi

# --- Discover the playbook ids to run ------------------------------
#
# Operator override wins; otherwise we shell into the playbooks CLI
# and pick every playbook whose tags include ``$TAG``. This is the
# load-bearing default: as new morning-tagged playbooks land, they
# join the cron bundle automatically, no script edit required.
if [[ -n "${MORNING_PLAYBOOKS:-}" ]]; then
    IFS=',' read -r -a IDS <<< "$MORNING_PLAYBOOKS"
    DISCOVERY="override"
else
    DISCOVERY="tag:$TAG"
    IDS_RAW=$(PYTHONPATH=. "${PLAYBOOKS_CLI[@]}" --quiet list 2>/dev/null \
        | "$PY" -c "
import json, sys, os
tag = os.environ.get('MORNING_TAG', 'morning')
try:
    body = json.load(sys.stdin)
    ids = [p['id'] for p in body.get('playbooks', [])
           if isinstance(p, dict) and tag in (p.get('tags') or [])]
    print('\n'.join(ids))
except Exception:
    pass
" 2>/dev/null)
    # shellcheck disable=SC2206
    IDS=( $IDS_RAW )
fi

if [[ ${#IDS[@]} -eq 0 ]]; then
    echo "$(c_red ERROR): no playbooks discovered (discovery=$DISCOVERY, tag=$TAG)" >&2
    echo "  Hint: check that ``make playbooks-list`` returns playbooks tagged" >&2
    echo "        with ``$TAG``, or set MORNING_PLAYBOOKS=<id1>,<id2> to override." >&2
    # Drop a minimal evidence record so the operator can audit
    # the no-playbooks-found branch without grepping cron logs.
    "$PY" -c "
import json
print(json.dumps({
    'ok': False,
    'reason': 'no_playbooks_discovered',
    'run_id': '$RUN_ID',
    'started_at': '$STARTED_AT',
    'discovery': '$DISCOVERY',
    'tag': '$TAG',
    'mode': '$MODE',
    'playbooks': [],
    'replay': None,
}, indent=2))
" > "$EVIDENCE"
    exit 2
fi

echo "$(c_dim "[$RUN_ID]") starting morning bundle: ${#IDS[@]} playbook(s) in mode=$MODE"
echo "$(c_dim "[$RUN_ID]") discovery=$DISCOVERY  evidence=$EVIDENCE"
echo

# --- Execute each playbook -----------------------------------------

# Per-playbook arrays parallel to $IDS so the final aggregator can
# zip them into the evidence JSON without losing order.
declare -a OK_FLAGS=()
declare -a TRACE_IDS=()
declare -a TOOK_MS=()
declare -a ERRORS=()
HARD_FAILED=0

for pid in "${IDS[@]}"; do
    if [[ -z "$pid" ]]; then
        continue
    fi
    started=$(date +%s)
    printf '  → %-35s ... ' "$pid"

    # Capture stdout (the JSON envelope) separately from stderr so a
    # crash anywhere in the runner shows up in the cron log without
    # corrupting the parse of a partial JSON.
    out=$(PYTHONPATH=. "${PLAYBOOKS_CLI[@]}" --quiet run "$pid" --mode "$MODE" 2>/tmp/morning-${RUN_ID}-${pid//./_}.err)
    rc=$?
    elapsed=$(($(date +%s) - started))

    # Parse the envelope; if rc=1 the body still has ok=false +
    # reason / message, so we don't need to special-case it.
    parsed=$("$PY" -c "
import json, sys
try:
    body = json.loads(sys.stdin.read())
    print(json.dumps({
        'ok': bool(body.get('ok')),
        'trace_id': body.get('trace_id') or '',
        'took_ms': body.get('took_ms') or 0,
        'reason': body.get('reason') or '',
        'message': body.get('message') or '',
        'steps_failed': sum(1 for s in (body.get('steps') or [])
                            if not s.get('ok') and not s.get('skipped')),
    }))
except Exception as exc:
    print(json.dumps({'ok': False, 'reason': 'parse_error',
                      'message': str(exc), 'trace_id': '',
                      'took_ms': 0, 'steps_failed': 0}))
" <<< "$out")

    ok=$(echo "$parsed" | "$PY" -c "import json,sys; print(json.load(sys.stdin)['ok'])")
    trace_id=$(echo "$parsed" | "$PY" -c "import json,sys; print(json.load(sys.stdin).get('trace_id') or '')")
    took=$(echo "$parsed" | "$PY" -c "import json,sys; print(json.load(sys.stdin).get('took_ms') or 0)")
    err=$(echo "$parsed" | "$PY" -c "import json,sys; b=json.load(sys.stdin); print(b.get('reason') or b.get('message') or '')")

    OK_FLAGS+=( "$ok" )
    TRACE_IDS+=( "$trace_id" )
    TOOK_MS+=( "$took" )
    ERRORS+=( "$err" )

    if [[ "$ok" == "True" ]]; then
        echo "$(c_green ok)  ($(printf '%.1f' "$took")ms wall=${elapsed}s trace=${trace_id:0:24}…)"
    else
        echo "$(c_red FAIL)  rc=$rc err=${err:-unknown}"
        HARD_FAILED=1
        if [[ "$FAIL_FAST" == "1" ]]; then
            echo "$(c_red abort): MORNING_FAIL_FAST=1, stopping after first failure" >&2
            break
        fi
    fi
done

# --- Flush meeet replay buffer (push pending events upstream) ------
REPLAY_OK="True"
REPLAY_PUSHED=0
REPLAY_SKIPPED="False"

if [[ "$SKIP_REPLAY" == "1" ]]; then
    REPLAY_SKIPPED="True"
    echo
    echo "$(c_dim "[$RUN_ID]") skipping meeet replay flush (MORNING_SKIP_REPLAY=1)"
else
    echo
    echo "$(c_dim "[$RUN_ID]") flushing meeet replay buffer..."
    replay_out=$(PYTHONPATH=. "${REPLAY_CLI[@]}" --quiet 2>&1)
    replay_rc=$?
    REPLAY_PUSHED=$("$PY" -c "
import json, sys
try:
    body = json.loads(sys.stdin.read())
    print(body.get('pushed', 0))
except Exception:
    print(0)
" <<< "$replay_out" 2>/dev/null)
    if [[ "$replay_rc" -ne 0 ]]; then
        REPLAY_OK="False"
        echo "  $(c_red WARN) replay flush exited rc=$replay_rc (events stay in local buffer for next run)"
    else
        echo "  $(c_green ok)   pushed=$REPLAY_PUSHED"
    fi
fi

# --- Aggregate the evidence JSON -----------------------------------
FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Hand the parallel arrays to Python via env vars to dodge bash
# escaping nightmares with arbitrary error messages.
export MORNING_RUN_ID="$RUN_ID"
export MORNING_STARTED_AT="$STARTED_AT"
export MORNING_FINISHED_AT="$FINISHED_AT"
export MORNING_DISCOVERY="$DISCOVERY"
export MORNING_TAG="$TAG"
export MORNING_MODE_USED="$MODE"
export MORNING_HARD_FAILED="$HARD_FAILED"
export MORNING_REPLAY_OK="$REPLAY_OK"
export MORNING_REPLAY_PUSHED="$REPLAY_PUSHED"
export MORNING_REPLAY_SKIPPED="$REPLAY_SKIPPED"
export MORNING_IDS_JSON="$("$PY" -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${IDS[@]}")"
export MORNING_OK_JSON="$("$PY" -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${OK_FLAGS[@]}")"
export MORNING_TRACE_JSON="$("$PY" -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${TRACE_IDS[@]}")"
export MORNING_TOOK_JSON="$("$PY" -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${TOOK_MS[@]}")"
export MORNING_ERR_JSON="$("$PY" -c "import json,sys; print(json.dumps(sys.argv[1:]))" "${ERRORS[@]}")"

"$PY" - <<'PYTHON_AGG' > "$EVIDENCE"
import json, os

ids    = json.loads(os.environ['MORNING_IDS_JSON'])
oks    = json.loads(os.environ['MORNING_OK_JSON'])
traces = json.loads(os.environ['MORNING_TRACE_JSON'])
tooks  = json.loads(os.environ['MORNING_TOOK_JSON'])
errs   = json.loads(os.environ['MORNING_ERR_JSON'])

playbooks = []
for i, pid in enumerate(ids):
    if i >= len(oks):
        playbooks.append({
            'id': pid, 'ok': False, 'trace_id': '',
            'took_ms': 0, 'error': 'aborted_by_fail_fast',
        })
        continue
    playbooks.append({
        'id': pid,
        'ok': oks[i] == 'True',
        'trace_id': traces[i] or None,
        'took_ms': float(tooks[i] or 0),
        'error': errs[i] or None,
    })

failed = [p['id'] for p in playbooks if not p['ok']]

print(json.dumps({
    'ok': not failed,
    'run_id': os.environ['MORNING_RUN_ID'],
    'started_at': os.environ['MORNING_STARTED_AT'],
    'finished_at': os.environ['MORNING_FINISHED_AT'],
    'discovery': os.environ['MORNING_DISCOVERY'],
    'tag': os.environ['MORNING_TAG'],
    'mode': os.environ['MORNING_MODE_USED'],
    'playbook_count': len(playbooks),
    'failed_count': len(failed),
    'failed_ids': failed,
    'replay': {
        'skipped': os.environ['MORNING_REPLAY_SKIPPED'] == 'True',
        'ok': os.environ['MORNING_REPLAY_OK'] == 'True',
        'pushed': int(os.environ['MORNING_REPLAY_PUSHED'] or 0),
    },
    'playbooks': playbooks,
}, indent=2))
PYTHON_AGG

# --- Final summary line --------------------------------------------
echo
if [[ "$HARD_FAILED" == "1" ]]; then
    echo "$(c_red SUMMARY) ${#IDS[@]} playbook(s), $(c_red FAILED) — see $EVIDENCE"
    exit 1
else
    echo "$(c_green SUMMARY) ${#IDS[@]} playbook(s), $(c_green ok) — evidence: $EVIDENCE"
    exit 0
fi
