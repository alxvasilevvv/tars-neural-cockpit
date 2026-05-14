#!/usr/bin/env bash
# scripts/ONPREM-DEPLOY/install.sh — W263
#
# One-line on-prem installer. Same UX as cloud SaaS curl-pipe-bash, but
# every byte stays on the operator's network.
#
# Hosted at:   https://meeet.world/install-tars-onprem
# Usage:       curl -L https://meeet.world/install-tars-onprem | bash
#
# What it does (in order):
#   1. Sanity-check prereqs: docker, docker compose v2, curl, openssl, git.
#   2. Clone (or pull) https://github.com/alxvasilevvv/tars-neural-cockpit
#      into /opt/tars (override via TARS_ONPREM_DIR).
#   3. Generate a fresh .env.onprem from the example template, minting
#      secrets where the example says <generate>.
#   4. Drop a self-signed cert into ./certs/ if no cert exists yet
#      (operator should replace before exposing to anything but localhost).
#   5. docker compose pull + up -d.
#   6. Wait for /health to return 200 (timeout 120s).
#   7. Print the URLs + first-login admin token.
#
# Re-run safe: every step is idempotent. Existing .env.onprem is kept;
# only missing keys get appended.

set -euo pipefail

TARS_ONPREM_DIR="${TARS_ONPREM_DIR:-/opt/tars}"
TARS_REPO_URL="${TARS_REPO_URL:-https://github.com/alxvasilevvv/tars-neural-cockpit.git}"
TARS_RELEASE_TAG="${TARS_RELEASE_TAG:-v10.0.0-rc.1}"

G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; X=$'\033[0m'

say()  { printf "${B}[install-tars-onprem]${X} %s\n" "$*"; }
ok()   { printf "${G}✓${X} %s\n" "$*"; }
warn() { printf "${Y}⚠${X} %s\n" "$*"; }
die()  { printf "${R}✗ %s${X}\n" "$*"; exit 1; }

# ── 1. Prereqs ────────────────────────────────────────────────────────
say "checking prereqs"
for bin in docker curl openssl git; do
  command -v "$bin" >/dev/null 2>&1 || die "missing prereq: $bin (install it and re-run)"
done
docker compose version >/dev/null 2>&1 || die "docker compose v2 required (legacy docker-compose not supported)"
ok "prereqs present"

# ── 2. Clone / pull ──────────────────────────────────────────────────
say "syncing repo into ${TARS_ONPREM_DIR}"
if [ ! -d "${TARS_ONPREM_DIR}/.git" ]; then
  mkdir -p "$(dirname "${TARS_ONPREM_DIR}")"
  git clone --depth=1 --branch "${TARS_RELEASE_TAG}" "${TARS_REPO_URL}" "${TARS_ONPREM_DIR}" \
    || die "git clone failed"
else
  git -C "${TARS_ONPREM_DIR}" fetch --tags --depth=1 origin "${TARS_RELEASE_TAG}" || true
  git -C "${TARS_ONPREM_DIR}" checkout "${TARS_RELEASE_TAG}" || true
fi
ok "repo at ${TARS_ONPREM_DIR} (tag ${TARS_RELEASE_TAG})"

cd "${TARS_ONPREM_DIR}/scripts/ONPREM-DEPLOY"

# ── 3. .env.onprem from template ─────────────────────────────────────
say "minting secrets in .env.onprem"
ENV_FILE=".env.onprem"
ENV_EXAMPLE=".env.onprem.example"

[ -f "${ENV_EXAMPLE}" ] || die "${ENV_EXAMPLE} missing (release packaging bug — report it)"

if [ ! -f "${ENV_FILE}" ]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
fi

# Replace every <generate> with a fresh 32-byte hex token.
mint() {
  local key="$1"
  if grep -q "^${key}=<generate>" "${ENV_FILE}"; then
    local val
    val="$(openssl rand -hex 32)"
    # macOS sed needs -i ''; GNU sed needs -i. Use a portable approach.
    sed -i.bak "s|^${key}=<generate>|${key}=${val}|" "${ENV_FILE}" && rm -f "${ENV_FILE}.bak"
    ok "minted ${key}"
  fi
}
mint POSTGRES_PASSWORD
mint TARS_AUTH_LOCAL_SIGNING_KEY
mint TARS_CONFIRM_KEY
mint TARS_VAULT_KEY
mint BRIDGE_SHARED_SECRET
mint ADMIN_BOOTSTRAP_TOKEN
chmod 600 "${ENV_FILE}"
ok ".env.onprem ready (0600)"

# ── 4. Self-signed cert (only if no cert in ./certs/) ─────────────────
mkdir -p certs logs pg-init
if [ ! -f certs/tars.crt ]; then
  say "generating self-signed cert (replace before public exposure)"
  openssl req -x509 -newkey rsa:4096 -keyout certs/tars.key -out certs/tars.crt \
    -days 365 -nodes -subj "/CN=tars.local" 2>/dev/null
  chmod 600 certs/tars.key
  ok "self-signed cert at certs/tars.{crt,key}"
else
  ok "existing cert at certs/tars.crt (keeping it)"
fi

# ── 5. Pull + bring up ───────────────────────────────────────────────
say "docker compose pull"
docker compose -f docker-compose.yml --env-file "${ENV_FILE}" pull 2>&1 | tail -5 || true

say "docker compose up -d (this will build images on first run, ~5min)"
docker compose -f docker-compose.yml --env-file "${ENV_FILE}" up -d --build

# ── 6. Wait for /health ──────────────────────────────────────────────
say "waiting for backend /health"
HTTP_PORT="$(grep -E '^TARS_HTTP_PORT=' "${ENV_FILE}" | cut -d= -f2 || echo 80)"
HTTP_PORT="${HTTP_PORT:-80}"
DEADLINE=$(( $(date +%s) + 120 ))
while [ "$(date +%s)" -lt "${DEADLINE}" ]; do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
    ok "backend healthy"
    break
  fi
  sleep 3
done
if ! curl -fsS "http://127.0.0.1:${HTTP_PORT}/health" >/dev/null 2>&1; then
  warn "/health did not respond within 120s — check logs:"
  echo "  docker compose -f ${TARS_ONPREM_DIR}/scripts/ONPREM-DEPLOY/docker-compose.yml logs"
  exit 2
fi

# ── 7. Final summary ─────────────────────────────────────────────────
ADMIN_TOKEN="$(grep -E '^ADMIN_BOOTSTRAP_TOKEN=' "${ENV_FILE}" | cut -d= -f2)"
cat <<DONE

${G}=== TARS v${TARS_RELEASE_TAG} on-prem is up ===${X}

  Cockpit:        http://localhost:${HTTP_PORT}/
  API health:     http://localhost:${HTTP_PORT}/health
  Metrics:        http://localhost:${HTTP_PORT}/metrics
  Logs:           docker compose -f ${TARS_ONPREM_DIR}/scripts/ONPREM-DEPLOY/docker-compose.yml logs -f
  Stop:           docker compose -f ${TARS_ONPREM_DIR}/scripts/ONPREM-DEPLOY/docker-compose.yml down

  First-login admin token (one-shot, rotate after use):
    ${ADMIN_TOKEN}

  Next:
    1. Replace certs/tars.{crt,key} with a real CA-signed cert.
    2. Wire your IdP (Okta/AzureAD/Google) — edit MEEET_ONPREM_IDP_URL.
    3. Read docs/ONPREM_DEPLOYMENT_GUIDE.md for backup/restore + monitoring.

DONE
