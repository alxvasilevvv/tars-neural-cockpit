#!/usr/bin/env bash
# scripts/ops_set_bridge_shared_secret.sh
#
# Operator one-shot: paste the canonical BRIDGE_SHARED_SECRET (the value
# that Lovable's `core-bridge` Supabase function uses) and this script:
#
#   1. Stores it as a Cloudflare Pages **production** environment
#      variable (encrypted) for the `tars-meeet` project.
#   2. Stores it as a GitHub repo secret on the `tars-neural-cockpit`
#      repo so the synthetic monitor + QA agent jobs can run with it.
#   3. Triggers a fresh Pages deploy so the new env var actually
#      reaches Functions.
#   4. Triggers the QA agent workflow so the next run is green.
#
# We never write the literal to disk; the value is read from stdin (or
# the BRIDGE_SHARED_SECRET env var if already exported).
#
# Required tools: curl, jq, gh.
# Required env (one-shot, prefer to pass via interactive stdin):
#   BRIDGE_SHARED_SECRET             secret value from Lovable
#   CLOUDFLARE_API_TOKEN             token with Pages:Edit on the account
#   CLOUDFLARE_ACCOUNT_ID            the meeet account id
#
# Optional env:
#   PAGES_PROJECT_NAME               default `tars-meeet`
#   GH_REPO                          default `alxvasilevvv/tars-neural-cockpit`
#
# Exit codes:
#   0  all four steps succeeded
#   1  one or more steps failed
#   2  prerequisites missing (env / tools)
#
# Authoritative spec: docs/TARS_MEEET_OPS_TODO.md §1.

set -euo pipefail

red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
blue()  { printf '\033[0;34m%s\033[0m\n' "$*" >&2; }
yel()   { printf '\033[0;33m%s\033[0m\n' "$*" >&2; }

need() {
  command -v "$1" >/dev/null 2>&1 || { red "missing prerequisite: $1"; exit 2; }
}

need curl
need jq
need gh

PROJECT="${PAGES_PROJECT_NAME:-tars-meeet}"
REPO="${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" || -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  red "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID must be set in the env"
  red "  (Cloudflare → My Profile → API Tokens → tars-admin token)"
  exit 2
fi

# Read secret either from env or from interactive stdin (-s hides input).
if [[ -z "${BRIDGE_SHARED_SECRET:-}" ]]; then
  printf '%s ' "Paste BRIDGE_SHARED_SECRET (input hidden):" >&2
  read -rs BRIDGE_SHARED_SECRET
  printf '\n' >&2
fi

if [[ -z "${BRIDGE_SHARED_SECRET}" ]]; then
  red "BRIDGE_SHARED_SECRET is empty — abort."
  exit 2
fi

if [[ "${#BRIDGE_SHARED_SECRET}" -lt 16 ]]; then
  yel "warning: BRIDGE_SHARED_SECRET shorter than 16 chars (${#BRIDGE_SHARED_SECRET})"
fi

# ---------- Step 1: Cloudflare Pages production env ----------
blue "[1/4] Cloudflare Pages → ${PROJECT} → env vars (production)"

# PATCH the project's deployment_configs.production.env_vars to merge in
# the new secret. We cannot send the full deployment_configs without
# clobbering existing keys, so we GET → merge → PATCH.
CF_API="https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/pages/projects/${PROJECT}"

cf_curl() {
  curl -fsS -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
       -H "Content-Type: application/json" "$@"
}

current=$(cf_curl "${CF_API}")
if ! jq -e '.success == true' >/dev/null <<<"$current"; then
  red "  FAIL: Cloudflare API rejected the request — token scope wrong?"
  jq -r '.errors // []' <<<"$current" >&2 || true
  exit 1
fi

merged_env=$(
  jq -n \
    --arg secret "$BRIDGE_SHARED_SECRET" \
    --argjson cur "$(jq '.result.deployment_configs.production.env_vars // {}' <<<"$current")" \
    '$cur + { "BRIDGE_SHARED_SECRET": { "type": "secret_text", "value": $secret } }'
)

patch_payload=$(jq -n --argjson env "$merged_env" \
  '{ deployment_configs: { production: { env_vars: $env } } }')

resp=$(cf_curl -X PATCH "${CF_API}" --data "$patch_payload")
if jq -e '.success == true' >/dev/null <<<"$resp"; then
  green "  OK:   BRIDGE_SHARED_SECRET (encrypted) written to Pages production env"
else
  red "  FAIL: PATCH /pages/projects/${PROJECT} rejected"
  jq -r '.errors' <<<"$resp" >&2 || true
  exit 1
fi

# ---------- Step 2: GitHub repo secret ----------
blue "[2/4] GitHub → ${REPO} → repo secrets"
if printf '%s' "$BRIDGE_SHARED_SECRET" | gh secret set BRIDGE_SHARED_SECRET \
     --repo "$REPO" --body - >/dev/null; then
  green "  OK:   BRIDGE_SHARED_SECRET set on ${REPO}"
else
  red "  FAIL: gh secret set rejected — check `gh auth status`"
  exit 1
fi

# ---------- Step 3: trigger fresh Pages deploy ----------
blue "[3/4] Trigger fresh Pages deploy (workflow_dispatch on main)"
if gh workflow run "tars-meeet-cloudflare-pages.yml" \
     --repo "$REPO" --ref main >/dev/null 2>&1; then
  green "  OK:   Pages workflow dispatched"
else
  yel "  WARN: workflow_dispatch failed; Pages will pick up the new env on the next deploy"
fi

# ---------- Step 4: trigger QA agent ----------
blue "[4/4] Trigger TARS QA Agent (workflow_dispatch on main)"
if gh workflow run "qa-agent.yml" --repo "$REPO" --ref main >/dev/null 2>&1; then
  green "  OK:   QA agent dispatched — should flip from YELLOW → GREEN"
else
  yel "  WARN: workflow_dispatch failed; QA agent will catch up on the next 30-min cron"
fi

echo
green "================================================"
green "  DONE: BRIDGE_SHARED_SECRET propagated end-to-end"
green "================================================"
yel "Watch deploy:  gh run list --repo ${REPO} --workflow=tars-meeet-cloudflare-pages.yml --limit 1"
yel "Watch QA:      gh run list --repo ${REPO} --workflow=qa-agent.yml --limit 1"
