#!/usr/bin/env bash
# SOAK-HOURLY.command — W310-l PH11 §4.2 hourly soak probe for v10.0.0 GA.
#
# Designed to be called once an hour during the 72 h pre-tag soak window.
# The operator wires it into cron or launchd; the script itself is stateless
# beyond `.soak/` (created next to the repo root).
#
# What it does (per `docs/handoff/PH11_QA_SWEEP_BRIEF.md` §4.2):
#   1. Probes the running backend on http://127.0.0.1:8765 :
#        - GET /api/health           (must be 200)
#        - GET /api/pairing/status   (must be 200; brief said /identity, real
#          surface is /status — corrected in implement)
#        - GET /api/voice/health     (must be 200)
#        - GET /api/vault/status     (must be 200)
#   2. Runs the QA-Agent probe surface — `make qa-agent` style: hits the
#      lightweight `/api/qa/probe` route. Falls back to recording NaN if the
#      route is absent in older builds, since QA-Agent gating belongs to
#      RELEASE, not to the hourly soak.
#   3. Tails `backend.log` for NEW ERROR lines since the previous hour-mark
#      (uses `.soak/last_offset` to track byte offset; brand-new on first run).
#   4. Records p50/p95 latency (from the four health probes), RSS+fd count
#      (psutil if available, otherwise ps + lsof), sqlite WAL size.
#   5. Appends a one-line JSON record to `.soak/hourly.log`.
#   6. Fails (exit 1) if any probe is non-2xx for 3 consecutive hours.
#
# Outputs:
#   .soak/hourly.log         one JSON object per hour-mark
#   .soak/last_offset        byte offset into backend.log at last hour-mark
#   .soak/consec_failures    integer count of consecutive probe-fail hours
#   .soak/backend.pid        optional — populated by soak preflight, only read here
#
# Exit codes:
#   0  hour-mark recorded, no abort condition hit
#   1  3-consec-fail abort (soak must be restarted from T-0 after fix)
#   2  prerequisite missing (backend not running, repo not detected, etc.)
#
# Usage:
#   bash scripts/SOAK-HOURLY.command
#
# Cron example (operator's crontab):
#   0 * * * *   cd /path/to/jarvis && bash scripts/SOAK-HOURLY.command >> .soak/hourly.log.stderr 2>&1

set -u

if [ -n "${TARS_SOAK_REPO:-}" ]; then
  cd "${TARS_SOAK_REPO}"
else
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
fi
REPO="$(pwd)"

SOAK_DIR="${REPO}/.soak"
HOURLY_LOG="${SOAK_DIR}/hourly.log"
OFFSET_FILE="${SOAK_DIR}/last_offset"
FAILS_FILE="${SOAK_DIR}/consec_failures"
BACKEND_LOG="${SOAK_LOG_PATH:-${REPO}/backend.log}"

BASE_URL="${TARS_SOAK_BASE_URL:-http://127.0.0.1:8765}"
TIMEOUT_S="${TARS_SOAK_PROBE_TIMEOUT:-5}"
MAX_CONSEC_FAILURES="${TARS_SOAK_MAX_FAILS:-3}"

mkdir -p "${SOAK_DIR}"

now_iso() {
  # cross-platform ISO-8601 timestamp in UTC
  date -u +%Y-%m-%dT%H:%M:%SZ
}

# Probe one URL; print "<status_code> <elapsed_ms>" on stdout, or "0 -1" on
# connection failure. Status code is always emitted as a plain decimal int
# (no leading zeros — keeps the appended JSON record valid).
# Never exits nonzero — caller decides what to do with it.
probe_one() {
  local url="$1"
  local start_ms end_ms elapsed code raw_code
  start_ms="$(perl -MTime::HiRes=time -e 'printf "%d", time()*1000' 2>/dev/null || python3 -c 'import time;print(int(time.time()*1000))')"
  # Capture curl's output AND its exit; never let `||` add a second token.
  raw_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT_S}" "${url}" 2>/dev/null)" || raw_code=""
  end_ms="$(perl -MTime::HiRes=time -e 'printf "%d", time()*1000' 2>/dev/null || python3 -c 'import time;print(int(time.time()*1000))')"
  # Normalize: strip non-digits and force base-10 so "000" → 0, "200" → 200.
  raw_code="${raw_code//[!0-9]/}"
  if [ -z "${raw_code}" ]; then
    code=0
  else
    code=$((10#${raw_code}))
  fi
  elapsed=$((end_ms - start_ms))
  if [ "${code}" -eq 0 ]; then
    elapsed=-1
  fi
  printf '%s %s\n' "${code}" "${elapsed}"
}

# p50 / p95 from a space-separated list of integers. Returns "-1" (the same
# sentinel used elsewhere in the record for "no data") on empty input so the
# emitted JSON stays valid. Pure awk so no python dep.
percentile() {
  local pct="$1"; shift
  awk -v p="${pct}" 'BEGIN{n=0} {for(i=1;i<=NF;i++) if ($i+0>=0) {a[n++]=$i+0}} END{
    if(n==0){print -1; exit}
    # insertion sort, small N
    for(i=1;i<n;i++){k=a[i];j=i-1;while(j>=0 && a[j]>k){a[j+1]=a[j];j--};a[j+1]=k}
    idx=int((p/100.0)*(n-1)+0.5)
    if(idx<0)idx=0
    if(idx>=n)idx=n-1
    print a[idx]
  }' <<< "$*"
}

# Record byte offset into backend.log; return new ERROR lines since last mark.
count_new_errors() {
  if [ ! -f "${BACKEND_LOG}" ]; then
    echo "0"
    return
  fi
  local prev_offset cur_size new_errs
  prev_offset=0
  if [ -f "${OFFSET_FILE}" ]; then
    prev_offset="$(cat "${OFFSET_FILE}" 2>/dev/null || echo 0)"
    case "${prev_offset}" in ''|*[!0-9]*) prev_offset=0;; esac
  fi
  cur_size="$(wc -c < "${BACKEND_LOG}" | tr -d ' ')"
  # log was rotated / truncated — reset
  if [ "${cur_size}" -lt "${prev_offset}" ]; then
    prev_offset=0
  fi
  new_errs="$(tail -c "+$((prev_offset + 1))" "${BACKEND_LOG}" 2>/dev/null | grep -cE '(^|\s)(ERROR|CRITICAL|Traceback)' || true)"
  echo "${cur_size}" > "${OFFSET_FILE}"
  echo "${new_errs:-0}"
}

# Best-effort RSS in MB + fd count for the backend pid, if .soak/backend.pid exists.
collect_proc_metrics() {
  local pid="" rss_mb=-1 fd=-1
  if [ -f "${SOAK_DIR}/backend.pid" ]; then
    pid="$(cat "${SOAK_DIR}/backend.pid" 2>/dev/null | tr -d ' \n')"
  fi
  if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
    rss_mb="$(ps -o rss= -p "${pid}" 2>/dev/null | awk '{printf "%d", $1/1024}')"
    if command -v lsof >/dev/null 2>&1; then
      fd="$(lsof -p "${pid}" 2>/dev/null | wc -l | tr -d ' ')"
    fi
  fi
  printf '%s %s\n' "${rss_mb:--1}" "${fd:--1}"
}

# sqlite WAL size in bytes for the default meeet sqlite, if it exists.
wal_size_bytes() {
  local wal="${REPO}/meeet.sqlite-wal"
  if [ -f "${wal}" ]; then
    wc -c < "${wal}" | tr -d ' '
  else
    echo "0"
  fi
}

# ── main ─────────────────────────────────────────────────────────────────────

STAMP="$(now_iso)"

PATHS=(
  "/api/health"
  "/api/pairing/status"
  "/api/voice/health"
  "/api/vault/status"
)

CODES=()
LATENCIES=()
ANY_FAIL=0
for p in "${PATHS[@]}"; do
  read -r code latency < <(probe_one "${BASE_URL}${p}")
  CODES+=("${code}")
  LATENCIES+=("${latency}")
  if [ "${code}" -lt 200 ] || [ "${code}" -ge 300 ]; then
    ANY_FAIL=1
  fi
done

# QA-Agent probe (best-effort; absence ≠ fail)
read -r QA_CODE QA_LATENCY < <(probe_one "${BASE_URL}/api/qa/probe")

NEW_ERRORS="$(count_new_errors)"
read -r RSS_MB FD_COUNT < <(collect_proc_metrics)
WAL_BYTES="$(wal_size_bytes)"

P50_MS="$(percentile 50 ${LATENCIES[@]})"
P95_MS="$(percentile 95 ${LATENCIES[@]})"

# bump or reset consec-failure counter
PREV_FAILS=0
if [ -f "${FAILS_FILE}" ]; then
  PREV_FAILS="$(cat "${FAILS_FILE}" 2>/dev/null || echo 0)"
  case "${PREV_FAILS}" in ''|*[!0-9]*) PREV_FAILS=0;; esac
fi
if [ "${ANY_FAIL}" -eq 1 ]; then
  CONSEC=$((PREV_FAILS + 1))
else
  CONSEC=0
fi
echo "${CONSEC}" > "${FAILS_FILE}"

# Compose one JSON object on a single line — easy to grep, easy to ingest later.
PROBES_JSON=""
for i in "${!PATHS[@]}"; do
  PROBES_JSON+="${PROBES_JSON:+,}{\"path\":\"${PATHS[$i]}\",\"code\":${CODES[$i]},\"latency_ms\":${LATENCIES[$i]}}"
done

RECORD="{\"ts\":\"${STAMP}\",\"base_url\":\"${BASE_URL}\",\"probes\":[${PROBES_JSON}],\"qa_probe\":{\"code\":${QA_CODE},\"latency_ms\":${QA_LATENCY}},\"latency_p50_ms\":${P50_MS},\"latency_p95_ms\":${P95_MS},\"new_errors\":${NEW_ERRORS},\"rss_mb\":${RSS_MB},\"fd_count\":${FD_COUNT},\"wal_bytes\":${WAL_BYTES},\"consec_failures\":${CONSEC},\"any_fail\":${ANY_FAIL}}"

echo "${RECORD}" >> "${HOURLY_LOG}"

# Emit a one-line human summary on stdout for cron mailers.
echo "[soak] ${STAMP}  any_fail=${ANY_FAIL} consec=${CONSEC}  p50=${P50_MS}ms p95=${P95_MS}ms  new_err=${NEW_ERRORS} rss=${RSS_MB}MB fd=${FD_COUNT}"

if [ "${CONSEC}" -ge "${MAX_CONSEC_FAILURES}" ]; then
  echo "[soak] ABORT — ${CONSEC} consecutive probe-fail hours (>= ${MAX_CONSEC_FAILURES}). Soak must be restarted after fix." >&2
  exit 1
fi

exit 0
