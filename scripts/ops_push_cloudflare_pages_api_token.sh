#!/usr/bin/env bash
# scripts/ops_push_cloudflare_pages_api_token.sh
#
# Easiest path (paste-only):
#   cp cf-operator.env.example cf-operator.env
#   # edit cf-operator.env — two lines: ACCOUNT_ID + API_TOKEN
#   make ops-cf-pages-token
#
# Or: export CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN (or
# CLOUDFLARE_API_TOKEN_NEW), or paste token at the hidden prompt.
#
# Steps: preflight GET …/pages/projects/tars-meeet → gh secret set → workflow run.
#
# Requires: curl, jq, gh (authenticated to GitHub).

set -euo pipefail

red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*" >&2; }

need() {
  command -v "$1" >/dev/null 2>&1 || { red "missing: $1"; exit 2; }
}

need curl
need jq
need gh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"
PROJECT="${PAGES_PROJECT_NAME:-tars-meeet}"

ENV_FILE="${OPS_CF_ENV:-$ROOT/cf-operator.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  blue "Loaded: ${ENV_FILE}"
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
  red "Cloudflare returned HTTP ${code} — token needs Account → Cloudflare Pages → Edit for this account."
  head -c 2000 "$tmp" >&2 || true
  echo >&2
  exit 1
fi
rm -f "$tmp"
green "Preflight OK."

blue "Updating GitHub secret CLOUDFLARE_API_TOKEN on ${REPO} …"
printf '%s' "$TOKEN" | gh secret set CLOUDFLARE_API_TOKEN -R "$REPO"

blue "Dispatching workflow tars-meeet-cloudflare-pages.yml …"
gh workflow run "tars-meeet-cloudflare-pages.yml" -R "$REPO"

green "Done. Watch: gh run list -R ${REPO} --workflow=tars-meeet-cloudflare-pages.yml -L 1"
