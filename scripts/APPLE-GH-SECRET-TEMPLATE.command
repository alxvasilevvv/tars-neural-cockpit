#!/usr/bin/env bash
# APPLE-GH-SECRET-TEMPLATE.command — print gh secret set commands (no secret values).
#
# Operator fills values from Keychain / .p12 export. Read-only helper for GA B1–B5.
#
set -euo pipefail

REPO="${GH_REPO:-alxvasilevvv/tars-neural-cockpit}"

cat <<EOF
# Paste values from docs/APPLE_SIGNING_SETUP.md — do NOT commit secrets.

gh secret set APPLE_CERTIFICATE --repo ${REPO} < path/to/certificate.p12.b64
gh secret set APPLE_CERTIFICATE_PASSWORD --repo ${REPO}
gh secret set APPLE_SIGNING_IDENTITY --repo ${REPO}   # e.g. "Developer ID Application: Name (TEAMID)"
gh secret set APPLE_TEAM_ID --repo ${REPO}
gh secret set APPLE_ID --repo ${REPO}                 # Apple ID email
gh secret set APPLE_PASSWORD --repo ${REPO}           # app-specific password

# Verify:
gh secret list --repo ${REPO} | grep APPLE_
bash scripts/PREFLIGHT-APPLE-SIGN.command
EOF

exit 0
