#!/usr/bin/env bash
# cf-operator.env или env vars → gh secret CLOUDFLARE_API_TOKEN + dispatch Pages workflow.
# Нужны: curl, jq, gh.

set -euo pipefail

red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*" >&2; }
yel()   { printf '\033[0;33m%s\033[0m\n' "$*" >&2; }

open_url() {
  if command -v open >/dev/null 2>&1; then open "$1" || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" || true
  fi
}

# When Pages preflight fails: explain if token is "account OK but Pages denied".
diagnose_pages_403() {
  local t="$1" ac="$2" pages_http="$3"
  local acct_tmp acode
  acct_tmp="$(mktemp)"
  acode=$(curl -sS -o "$acct_tmp" -w "%{http_code}" \
    -H "Authorization: Bearer ${t}" \
    "https://api.cloudflare.com/client/v4/accounts")
  if [[ "$acode" == "200" ]] && jq -e '.success == true' "$acct_tmp" >/dev/null 2>&1; then
    yel "Диагностика: токен работает для GET /accounts, но Pages API вернул HTTP ${pages_http}."
    yel "Значит в токене нет разрешения: Account → Cloudflare Pages → Edit."
    echo "" >&2
    yel "Создай новый Custom Token в Cloudflare:"
    yel "  • Permissions → Account → Cloudflare Pages → Edit"
    yel "  • Account Resources → Include → Specific account → ${ac}"
    yel "  • Вставь новый cfat_… в cf-operator.env → CLOUDFLARE_API_TOKEN=… (одна строка)"
    echo "" >&2
    if [[ "${OPS_CF_NO_BROWSER:-}" != "1" ]]; then
      blue "Открываю https://dash.cloudflare.com/profile/api-tokens"
      open_url "https://dash.cloudflare.com/profile/api-tokens"
    fi
  else
    red "Диагностика: токен не проходит GET /accounts — неверный/отозван, обрезан при копировании,"
    red "или раньше портило поле через «source .env» (символы \$ и т.д.). Скрипт теперь парсит файл без source — сохрани cf-operator.env и снова make ops-cf-pages-token."
  fi
  rm -f "$acct_tmp"
}

need() {
  command -v "$1" >/dev/null 2>&1 || { red "missing: $1"; exit 2; }
}

need curl
need jq
need gh

# Never `source` the token line — characters like $ or ` break or truncate the value.
load_cf_operator_file() {
  local f="$1" line key val
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line//$'\r'/}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// /}" ]] && continue
    [[ "$line" == *"="* ]] || continue
    key="${line%%=*}"
    val="${line#*=}"
    key="$(echo -n "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    val="$(echo -n "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    case "$key" in
      CLOUDFLARE_ACCOUNT_ID) CLOUDFLARE_ACCOUNT_ID="$val" ;;
      CLOUDFLARE_API_TOKEN)  CLOUDFLARE_API_TOKEN="$val" ;;
    esac
  done < "$f"
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"
PROJECT="${PAGES_PROJECT_NAME:-tars-meeet}"

ENV_FILE="${OPS_CF_ENV:-$ROOT/cf-operator.env}"
if [[ -f "$ENV_FILE" ]]; then
  load_cf_operator_file "$ENV_FILE"
  blue "Loaded (safe parse): ${ENV_FILE}"
fi

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" || "${CLOUDFLARE_ACCOUNT_ID}" =~ ^[[:space:]]*$ ]]; then
  red "Need CLOUDFLARE_ACCOUNT_ID (put it in cf-operator.env — see cf-operator.env.example)."
  exit 2
fi

TOKEN="${CLOUDFLARE_API_TOKEN_NEW:-${CLOUDFLARE_API_TOKEN:-}}"
if [[ -z "$TOKEN" ]]; then
  if [[ -t 0 ]]; then
    printf '%s ' "Paste Cloudflare API token (Pages:Edit, input hidden):" >&2
    read -rs TOKEN
    printf '\n' >&2
  else
    red "Need CLOUDFLARE_API_TOKEN in cf-operator.env or paste interactively in a TTY."
    exit 2
  fi
fi

TOKEN="${TOKEN#Bearer }"
TOKEN="$(echo -n "$TOKEN" | tr -d '\r\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

if [[ -z "$TOKEN" ]]; then
  red "Token is empty."
  exit 2
fi

CF_ACCOUNT="$(echo -n "$CLOUDFLARE_ACCOUNT_ID" | tr -d '\r\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
URL="https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/pages/projects/${PROJECT}"

blue "Preflight: GET ${URL}"
tmp="$(mktemp)"
code=$(curl -sS -o "$tmp" -w "%{http_code}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "$URL")

if [[ "$code" != "200" ]] || ! jq -e '.success == true' "$tmp" >/dev/null 2>&1; then
  red "Cloudflare Pages preflight HTTP ${code} — нужен токен с правом Cloudflare Pages (Edit)."
  head -c 2000 "$tmp" >&2 || true
  echo >&2
  diagnose_pages_403 "$TOKEN" "$CF_ACCOUNT" "$code"
  exit 1
fi
rm -f "$tmp"
green "Preflight OK."

blue "Updating GitHub secret CLOUDFLARE_API_TOKEN on ${REPO} …"
printf '%s' "$TOKEN" | gh secret set CLOUDFLARE_API_TOKEN -R "$REPO"

blue "Dispatching workflow tars-meeet-cloudflare-pages.yml …"
gh workflow run "tars-meeet-cloudflare-pages.yml" -R "$REPO"

green "Done. Watch: gh run list -R ${REPO} --workflow=tars-meeet-cloudflare-pages.yml -L 1"
