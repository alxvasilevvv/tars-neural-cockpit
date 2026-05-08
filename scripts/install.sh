#!/usr/bin/env bash
# DEPRECATED — kept as a redirector so anyone who copy-pasted the old
# `curl -fsSL meeet.world/install.sh | bash` URL still gets a working
# install. The canonical scripts now live at:
#
#   • https://tars.meeet.world/install.sh — public/install.sh
#     (immutable Cloudflare Pages build, served fresh on every deploy)
#
#   • scripts/install-tars.sh — the in-repo source for the same
#     canonical content; targets the real GitHub repo
#     (alxvasilevvv/tars-neural-cockpit) with the correct asset
#     filenames published by .github/workflows/release-desktop-tagged.yml.
#
# The previous version of THIS file pointed at `meeet-world/tars`
# (404'd) and used `tars-${tag}-${OS}-${ARCH}.tar.gz` filenames that
# no release ever produced. Anyone reading the script tree should
# treat the public/ + install-tars.sh pair as the source of truth.
#
# We deliberately keep this stub — and not delete the file — because
# `docs/PLAN_FORWARD.md` and a handful of historic comments still
# reference `scripts/install.sh`, and breaking those links has zero
# upside.

set -euo pipefail

CANONICAL_URL="https://tars.meeet.world/install.sh"
CANONICAL_LOCAL="scripts/install-tars.sh"

cat >&2 <<EOF
[scripts/install.sh] This script has been replaced.

  Canonical install (web):
      curl -fsSL ${CANONICAL_URL} | bash

  Canonical source (in-repo, identical asset targets):
      bash ${CANONICAL_LOCAL}

Re-running this stub will execute the canonical local script if it is
present, otherwise will exit with a clear error.
EOF

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Use [[ -f ]] + `bash <file>` rather than [[ -x ]] + direct exec so
# we don't depend on the canonical script's exec bit (it ships
# `rw-r--r--` because callers always invoke it via `bash`).
if [[ -f "${ROOT}/${CANONICAL_LOCAL}" ]]; then
  exec bash "${ROOT}/${CANONICAL_LOCAL}" "$@"
fi

echo >&2
echo "ERROR: ${CANONICAL_LOCAL} not found in the local checkout." >&2
echo "Run the canonical web installer instead:" >&2
echo "    curl -fsSL ${CANONICAL_URL} | bash" >&2
exit 1
