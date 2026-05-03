#!/usr/bin/env bash
# scripts/ops_push_cloudflare_pages_api_token.sh
#
# One-shot: mint a Cloudflare **custom** API token (Account → Cloudflare
# Pages → Edit; include the account that hosts `tars-meeet`), then run:
#
#   export CLOUDFLARE_ACCOUNT_ID='<account id from CF dashboard>'
#   bash scripts/ops_push_cloudflare_pages_api_token.sh
#
# Paste the token at the prompt (hidden). The script:
#   1. GET /accounts/{id}/pages/projects/tars-meeet — aborts on non-200
#   2. gh secret set CLOUDFLARE_API_TOKEN
#   3. gh workflow run tars-meeet-cloudflare-pages.yml
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

REPO="${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"
PROJECT="${PAGES_PROJECT_NAME:-tars-meeet}"

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  red "Set CLOUDFLARE_ACCOUNT_ID (Cloudflare dashboard → Workers & Pages → account id)."
  exit 2
fi

if [[ -n "${CLOUDFLARE_API_TOKEN_NEW:-}" ]]; then
  TOKEN="$CLOUDFLARE_API_TOKEN_NEW"
else
  printf '%s ' "Paste Cloudflare API token (Pages:Edit on this account, input hidden):" >&2
  read -rs TOKEN
  printf '\n' >&2
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
