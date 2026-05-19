#!/usr/bin/env bash
# SOAK-REPORT.command — W310-l PH11 §4.6 soak postmortem reporter.
#
# Reads `.soak/hourly.log` (one JSON record per hour, produced by
# SOAK-HOURLY.command) and emits a markdown soak report on stdout.
#
# Operator usage at T+72 h:
#
#   bash scripts/SOAK-REPORT.command > docs/qa/SOAK_v10.0.0.md
#
# Per `docs/handoff/PH11_QA_SWEEP_BRIEF.md` §4.6 the report includes:
#   - Hour-by-hour latency + RSS + fd + ERROR-count table
#   - Top 5 ERROR signatures (grep + count, sampled from backend.log)
#   - meeet bridge drift histogram (best-effort — uses
#     scripts/CHECK-MEEET-LIVE.command output if invoked with --check-meeet)
#   - Final go/no-go: "GA tag authorised" or "GA tag blocked"
#
# Exit codes:
#   0  report rendered (go/no-go printed inside, NOT used as exit)
#   2  prerequisite missing (`.soak/hourly.log` absent or empty)
#
# The decision exit code is deliberately separated from the report exit
# code so the operator's diff/CI tooling can read the markdown unchanged.

set -u

if [ -n "${TARS_SOAK_REPO:-}" ]; then
  cd "${TARS_SOAK_REPO}"
else
  cd "$(dirname "${BASH_SOURCE[0]}")/.."
fi
REPO="$(pwd)"

SOAK_DIR="${REPO}/.soak"
HOURLY_LOG="${SOAK_DIR}/hourly.log"
BACKEND_LOG="${SOAK_LOG_PATH:-${REPO}/backend.log}"

# Hard-fail thresholds — pulled verbatim from PH11 brief §4.5.
P95_DRIFT_PCT_THRESHOLD="${TARS_SOAK_P95_DRIFT_PCT:-20}"
ERR_PER_HOUR_THRESHOLD="${TARS_SOAK_ERR_PER_HOUR:-100}"
RSS_MB_THRESHOLD="${TARS_SOAK_RSS_MB:-2048}"
FD_THRESHOLD="${TARS_SOAK_FD:-1024}"

if [ ! -s "${HOURLY_LOG}" ]; then
  cat <<EOF
# Soak Report — v10.0.0

> **No hourly records found** at \`.soak/hourly.log\`. Run
> \`bash scripts/SOAK-HOURLY.command\` at least once before generating
> a report.

**Go / no-go: blocked (no data).**
EOF
  exit 2
fi

# Pure-awk extractor: produces TSV "ts p50 p95 new_err rss fd consec any_fail"
# from the JSON-per-line log. Avoids a python dep so the script also works in
# locked-down environments where pip install is not allowed.
extract_tsv() {
  awk '
    function pick(field,   m, v) {
      m = match($0, "\"" field "\":[^,}\\]]*")
      if (m == 0) return "-"
      v = substr($0, RSTART, RLENGTH)
      sub("\"" field "\":", "", v)
      gsub(/^[ "]+|[ "]+$/, "", v)
      return v
    }
    {
      ts        = pick("ts")
      p50       = pick("latency_p50_ms")
      p95       = pick("latency_p95_ms")
      new_err   = pick("new_errors")
      rss       = pick("rss_mb")
      fd        = pick("fd_count")
      consec    = pick("consec_failures")
      any_fail  = pick("any_fail")
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", ts, p50, p95, new_err, rss, fd, consec, any_fail
    }
  ' "${HOURLY_LOG}"
}

TSV="$(extract_tsv)"
TOTAL_HOURS="$(printf '%s\n' "${TSV}" | grep -c .)"

BASELINE_P95="$(printf '%s\n' "${TSV}" | head -1 | awk -F'\t' '{print $3+0}')"
LAST_P95="$(printf '%s\n' "${TSV}" | tail -1 | awk -F'\t' '{print $3+0}')"

# Aggregate signals.
read -r MAX_RSS MAX_FD MAX_NEW_ERR ANY_HARD_FAIL <<<"$(
  printf '%s\n' "${TSV}" | awk -F'\t' -v rss_th="${RSS_MB_THRESHOLD}" -v fd_th="${FD_THRESHOLD}" -v err_th="${ERR_PER_HOUR_THRESHOLD}" '
    BEGIN{ max_rss=-1; max_fd=-1; max_err=-1; bad=0 }
    {
      if ($5+0 > max_rss) max_rss=$5+0
      if ($6+0 > max_fd)  max_fd=$6+0
      if ($4+0 > max_err) max_err=$4+0
      if ($8+0 == 1) bad=1
      if ($5+0 > rss_th)  bad=1
      if ($6+0 > fd_th)   bad=1
      if ($4+0 > err_th)  bad=1
    }
    END{ printf "%d %d %d %d", max_rss, max_fd, max_err, bad }
  '
)"

# p95 drift gate.
P95_DRIFT_PCT=0
if [ "${BASELINE_P95}" -gt 0 ] 2>/dev/null; then
  P95_DRIFT_PCT="$(awk -v b="${BASELINE_P95}" -v l="${LAST_P95}" 'BEGIN{ if(b<=0){print 0} else {printf "%d", (l-b)*100.0/b} }')"
fi
P95_DRIFT_ABS="${P95_DRIFT_PCT#-}"
if [ "${P95_DRIFT_ABS}" -gt "${P95_DRIFT_PCT_THRESHOLD}" ]; then
  ANY_HARD_FAIL=1
fi

# Top 5 ERROR signatures from backend.log (best-effort — empty if log absent).
TOP_ERRORS=""
if [ -f "${BACKEND_LOG}" ]; then
  TOP_ERRORS="$(grep -E 'ERROR|CRITICAL|Traceback' "${BACKEND_LOG}" 2>/dev/null \
    | sed -E 's/^[^]]+\]//; s/[0-9]+/N/g; s/0x[0-9a-fA-F]+/HEX/g' \
    | sort | uniq -c | sort -rn | head -5 \
    | awk '{ count=$1; $1=""; sub(/^ /,""); printf "| %d | `%s` |\n", count, substr($0,1,160) }')"
fi
[ -z "${TOP_ERRORS}" ] && TOP_ERRORS="| 0 | _(none)_ |"

# meeet bridge drift histogram is best-effort: tries CHECK-MEEET-LIVE in dry
# mode. If the live check isn't available or isn't authorised, we surface a
# placeholder rather than failing the report.
MEEET_BLOCK=""
if [ -x "${REPO}/scripts/CHECK-MEEET-LIVE.command" ] && [ "${1:-}" = "--check-meeet" ]; then
  if MEEET_OUT="$(bash "${REPO}/scripts/CHECK-MEEET-LIVE.command" 2>&1)"; then
    MEEET_BLOCK="$(printf '%s' "${MEEET_OUT}" | tail -20)"
  else
    MEEET_BLOCK="_(CHECK-MEEET-LIVE failed; see backend.log)_"
  fi
else
  MEEET_BLOCK="_(skipped — re-run with \`--check-meeet\` to include)_"
fi

# Decision.
if [ "${ANY_HARD_FAIL}" -eq 0 ] && [ "${TOTAL_HOURS}" -ge 72 ]; then
  DECISION="GA tag **authorised** — proceed to \`scripts/RELEASE-v10.0.command\`."
  EXIT_HINT=0
elif [ "${ANY_HARD_FAIL}" -eq 0 ]; then
  DECISION="GA tag **blocked** — only ${TOTAL_HOURS}/72 hourly samples recorded. Wait for full window."
  EXIT_HINT=2
else
  DECISION="GA tag **blocked** — hard-fail criterion hit (see thresholds table below). Restart soak from T-0 after fix."
  EXIT_HINT=2
fi

# ── render ──────────────────────────────────────────────────────────────────

cat <<EOF
# Soak Report — v10.0.0

**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
**Hours recorded:** ${TOTAL_HOURS} / 72
**Source:** \`.soak/hourly.log\` (one JSON record per hour from \`scripts/SOAK-HOURLY.command\`)

---

## 1. Verdict

${DECISION}

---

## 2. Hard-fail thresholds vs observed peak

| Signal | Threshold | Observed peak | Status |
| ------ | --------- | ------------- | ------ |
| p95 drift vs baseline | ≤ ${P95_DRIFT_PCT_THRESHOLD}% | ${P95_DRIFT_PCT}% | $( [ "${P95_DRIFT_ABS}" -le "${P95_DRIFT_PCT_THRESHOLD}" ] && echo "✓" || echo "✗ FAIL") |
| ERROR lines / hour | ≤ ${ERR_PER_HOUR_THRESHOLD} | ${MAX_NEW_ERR} | $( [ "${MAX_NEW_ERR}" -le "${ERR_PER_HOUR_THRESHOLD}" ] && echo "✓" || echo "✗ FAIL") |
| RSS (MB) | ≤ ${RSS_MB_THRESHOLD} | ${MAX_RSS} | $( [ "${MAX_RSS}" -le "${RSS_MB_THRESHOLD}" ] && echo "✓" || echo "✗ FAIL") |
| fd count | ≤ ${FD_THRESHOLD} | ${MAX_FD} | $( [ "${MAX_FD}" -le "${FD_THRESHOLD}" ] && echo "✓" || echo "✗ FAIL") |
| any 4-probe hour | 0 | $(printf '%s\n' "${TSV}" | awk -F'\t' '$8+0==1' | wc -l | tr -d ' ') | _see hourly table_ |

Baseline p95: ${BASELINE_P95} ms. Last hour p95: ${LAST_P95} ms.

---

## 3. Hour-by-hour table

| ts (UTC) | p50 ms | p95 ms | new ERRs | RSS MB | fd | consec | probe |
| -------- | -----: | -----: | -------: | -----: | --: | -----: | ----- |
$(printf '%s\n' "${TSV}" | awk -F'\t' '{
  status = ($8+0 == 1) ? "✗" : "✓"
  printf "| %s | %s | %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6, $7, status
}')

---

## 4. Top 5 ERROR signatures

| Count | Signature (sanitized; digits→N, hex→HEX) |
| ----: | ----------------------------------------- |
${TOP_ERRORS}

---

## 5. meeet bridge drift

${MEEET_BLOCK}

---

## 6. Next step

EOF

case "${EXIT_HINT}" in
  0) cat <<EOF
1. Confirm \`docs/V10_GA_CHECKLIST.md\` — all hard blockers green.
2. \`bash scripts/FINAL-QA-GATE.command\` (last gate before tag).
3. \`RELEASE_v10_DRY_RUN=1 bash scripts/RELEASE-v10.0.command\` (no tag).
4. \`bash scripts/RELEASE-v10.0.command\` (real tag).
EOF
     ;;
  *) cat <<EOF
1. Investigate the hard-fail rows above.
2. File \`cursor/soak-v10-fix-NN\` PRs; do **not** bandage — soak is binary.
3. After fixes land, \`rm -rf .soak/\` and restart soak from T-0.
4. Re-run \`bash scripts/SOAK-REPORT.command\` after 72 h of clean signal.
EOF
     ;;
esac

# Always exit 0 so the report file is captured even if the verdict is "blocked".
# The verdict itself is the source of truth inside the markdown.
exit 0
