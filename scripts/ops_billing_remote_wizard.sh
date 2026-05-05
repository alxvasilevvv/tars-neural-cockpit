#!/usr/bin/env bash
# scripts/ops_billing_remote_wizard.sh
#
# Operator one-shot: paste the Supabase **TARS_BILLING_API_KEY** (same value TARS
# uses as **MEEET_BILLING_API_KEY**), confirm, then:
#   1) GET …/operator (prod)
#   2) POST …/operator/usage twice with the same trace_id (idempotency)
#   3) optionally merge **TARS_BILLING_SOURCE**, **MEEET_BILLING_BASE_URL**,
#      **MEEET_BILLING_API_KEY** into repo-root **.env** (active lines only)
#
# Usage:
#   make ops-billing-remote-wizard
#   # or:
#   bash scripts/ops_billing_remote_wizard.sh
#
# Prerequisites: curl, jq, python3 (stdlib only for .env merge).
# The key is never printed; only read from stdin (hidden) or existing env.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export ROOT

red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
yel()   { printf '\033[0;33m%s\033[0m\n' "$*" >&2; }

need() {
  command -v "$1" >/dev/null 2>&1 || { red "missing: $1"; exit 2; }
}

need curl
need jq
need python3

DEFAULT_BASE="https://zujrmifaabkletgnpoyw.supabase.co/functions/v1/tars-billing"
MEEET_BILLING_BASE_URL="${MEEET_BILLING_BASE_URL:-$DEFAULT_BASE}"
MEEET_BILLING_BASE_URL="${MEEET_BILLING_BASE_URL%/}"

trim() {
  local s="$1"
  s="${s//$'\r'/}"
  echo -n "$s" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

if [[ -n "${MEEET_BILLING_API_KEY:-}" ]]; then
  yel "MEEET_BILLING_API_KEY is already set in the environment."
  read -r -p "Use it for smoke + .env? [Y/n] " _useenv
  if [[ "${_useenv:-}" =~ ^[Nn]$ ]]; then
    read -r -s -p "Paste MEEET_BILLING_API_KEY (hidden): " MEEET_BILLING_API_KEY
    echo ""
  fi
else
  read -r -s -p "Paste MEEET_BILLING_API_KEY (hidden): " MEEET_BILLING_API_KEY
  echo ""
fi

MEEET_BILLING_API_KEY="$(trim "${MEEET_BILLING_API_KEY:-}")"
if [[ -z "$MEEET_BILLING_API_KEY" ]]; then
  red "Empty key — aborting."
  exit 2
fi

export MEEET_BILLING_API_KEY
export MEEET_BILLING_BASE_URL

read -r -p "Run prod smoke on ${MEEET_BILLING_BASE_URL} ? [Y/n] " _go
if [[ -n "${_go:-}" && ! "${_go}" =~ ^[Yy] ]] && [[ -n "${_go}" ]]; then
  green "Skipped smoke."
else
  OP_URL="${MEEET_BILLING_BASE_URL}/operator"
  US_URL="${MEEET_BILLING_BASE_URL}/operator/usage"

  code="$(curl -sS -o /tmp/tars_bill_wiz_get.json -w "%{http_code}" "$OP_URL" \
    -H "Authorization: Bearer ${MEEET_BILLING_API_KEY}" \
    -H "Accept: application/json")"
  if [[ "$code" != "200" ]]; then
    red "GET /operator failed HTTP $code"
    head -c 400 /tmp/tars_bill_wiz_get.json >&2 || true
    echo "" >&2
    exit 1
  fi
  ok="$(jq -r '.ok // false' /tmp/tars_bill_wiz_get.json)"
  if [[ "$ok" != "true" ]]; then
    red "GET /operator JSON ok!=true"
    jq . /tmp/tars_bill_wiz_get.json >&2 || cat /tmp/tars_bill_wiz_get.json >&2
    exit 1
  fi
  green "GET /operator → 200 ok"

  TRACE="tars_wizard_$(date +%s)_${RANDOM}_$$"
  body1="$(curl -sS -w "\n%{http_code}" -X POST "$US_URL" \
    -H "Authorization: Bearer ${MEEET_BILLING_API_KEY}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"delta_usd\":0.01,\"trace_id\":\"${TRACE}\"}")"
  http1="$(echo "$body1" | tail -n1)"
  json1="$(echo "$body1" | sed '$d')"
  if [[ "$http1" != "200" ]]; then
    red "First POST /operator/usage failed HTTP $http1"
    echo "$json1" >&2
    exit 1
  fi
  ok1="$(echo "$json1" | jq -r '.ok // false')"
  if [[ "$ok1" != "true" ]]; then
    red "First POST ok!=true"
    echo "$json1" >&2
    exit 1
  fi
  dup1="$(echo "$json1" | jq -r 'if (.duplicate|type)=="boolean" then .duplicate else "absent" end')"
  spent1="$(echo "$json1" | jq -r '.spent_usd_24h // empty')"

  body2="$(curl -sS -w "\n%{http_code}" -X POST "$US_URL" \
    -H "Authorization: Bearer ${MEEET_BILLING_API_KEY}" \
    -H "Accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"delta_usd\":0.01,\"trace_id\":\"${TRACE}\"}")"
  http2="$(echo "$body2" | tail -n1)"
  json2="$(echo "$body2" | sed '$d')"
  if [[ "$http2" != "200" ]]; then
    red "Second POST /operator/usage failed HTTP $http2"
    echo "$json2" >&2
    exit 1
  fi
  dup2="$(echo "$json2" | jq -r '.duplicate // false')"
  spent2="$(echo "$json2" | jq -r '.spent_usd_24h // empty')"
  if [[ "$dup2" != "true" ]]; then
    red "Expected duplicate:true on second POST, got: $dup2"
    echo "$json2" >&2
    exit 1
  fi
  if [[ -n "$spent1" && -n "$spent2" && "$spent1" != "$spent2" ]]; then
    red "spent_usd_24h changed on duplicate POST ($spent1 → $spent2)"
    exit 1
  fi
  green "POST /operator/usage idempotency OK (trace_id=${TRACE})"
  if [[ "$dup1" == "true" ]]; then
    yel "Note: first POST already had duplicate:true (trace reused?) — spend check still passed."
  fi
fi

read -r -p "Write TARS_BILLING_SOURCE=remote + MEEET_BILLING_* into ${ROOT}/.env ? [y/N] " _wenv
if [[ "${_wenv:-}" =~ ^[Yy] ]]; then
  python3 <<'PY'
import os, re
from pathlib import Path

root = Path(os.environ["ROOT"])
path = root / ".env"
keys_pat = re.compile(
    r"^(TARS_BILLING_SOURCE|MEEET_BILLING_BASE_URL|MEEET_BILLING_API_KEY)=",
    re.MULTILINE,
)

def load_lines() -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return text.splitlines(keepends=True)

def filter_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        st = line.lstrip()
        if st.startswith("#"):
            out.append(line)
            continue
        if keys_pat.match(line):
            continue
        out.append(line)
    return out

def shell_single_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"

lines = filter_lines(load_lines())
body = "".join(lines)
if body and not body.endswith("\n"):
    body += "\n"
body += "\n# --- remote billing (ops_billing_remote_wizard) ---\n"
body += f"TARS_BILLING_SOURCE=remote\n"
body += f"MEEET_BILLING_BASE_URL={shell_single_quote(os.environ['MEEET_BILLING_BASE_URL'])}\n"
body += f"MEEET_BILLING_API_KEY={shell_single_quote(os.environ['MEEET_BILLING_API_KEY'])}\n"
path.write_text(body, encoding="utf-8")
print(f"Wrote billing block to {path}")
PY
  green ".env updated (billing keys merged; other lines preserved)."
  read -r -p "Run pytest billing files now? [Y/n] " _py
  if [[ -z "${_py:-}" || "${_py}" =~ ^[Yy] ]]; then
    ( cd "$ROOT" && PYTHONPATH=. ./.venv/bin/python -m pytest \
        tests/test_meeet_billing_remote.py tests/test_meeet_billing_usage.py -q --tb=short ) \
      || { red "pytest failed"; exit 1; }
    green "pytest billing: OK (mocked; does not call prod)"
  fi
else
  yel "Skipped .env write. Export manually:"
  printf '  export TARS_BILLING_SOURCE=remote\n'
  printf '  export MEEET_BILLING_BASE_URL=%q\n' "$MEEET_BILLING_BASE_URL"
  printf '  export MEEET_BILLING_API_KEY=<hidden>\n'
fi

green "Done."
