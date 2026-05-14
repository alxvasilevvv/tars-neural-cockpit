#!/usr/bin/env bash
#
# W257 — Annual compliance bundle (one-click).
#
# Produces ~/Documents/TARS/compliance-bundle-<year>/ with:
#   - SOC2_TYPE_II_READINESS.pdf  (rendered from docs/)
#   - receipt-audit-<year>.pdf    (12 months of receipts from /api/audit/list)
#   - gdpr-export-<year>.zip      (12-month GDPR Article-15 self-export)
#   - manifest.json + signature.txt (ties all three together)
#
# Double-clickable; auto-closes the Terminal window in 8s on success.

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$(pwd)"

YEAR="$(date -u +%Y)"
OUT_DIR="${HOME}/Documents/TARS/compliance-bundle-${YEAR}"
mkdir -p "${OUT_DIR}"

# Window banner
echo "=========================================================="
echo "  TARS Compliance Bundle — annual auditor export"
echo "  Year:   ${YEAR}"
echo "  Output: ${OUT_DIR}"
echo "=========================================================="
echo ""

BACKEND="${TARS_BACKEND_URL:-http://127.0.0.1:8765}"
ERRORS=0

# ---------------------------------------------------------------------------
# 1) Make sure the backend is up — we need its endpoints for steps 2-3.
# ---------------------------------------------------------------------------

echo "[1/5] Pinging backend at ${BACKEND}..."
if ! curl -sS --max-time 4 "${BACKEND}/api/health" >/dev/null 2>&1; then
  echo "  ERROR: backend not reachable. Start TARS first."
  echo "  Hint:  open ${REPO_ROOT}/scripts/LAUNCH-NOW.command"
  ERRORS=$((ERRORS + 1))
fi

# ---------------------------------------------------------------------------
# 2) Render SOC2 readiness doc to PDF.
# ---------------------------------------------------------------------------

SOC2_MD="${REPO_ROOT}/docs/SOC2_TYPE_II_READINESS.md"
SOC2_PDF="${OUT_DIR}/SOC2_TYPE_II_READINESS.pdf"

echo "[2/5] Rendering SOC2 readiness PDF..."
if [ ! -f "${SOC2_MD}" ]; then
  echo "  ERROR: ${SOC2_MD} missing."
  ERRORS=$((ERRORS + 1))
elif command -v pandoc >/dev/null 2>&1; then
  pandoc "${SOC2_MD}" -o "${SOC2_PDF}" 2>&1 | sed 's/^/  /' || {
    echo "  pandoc -> PDF failed; saving markdown copy instead"
    cp "${SOC2_MD}" "${OUT_DIR}/SOC2_TYPE_II_READINESS.md"
  }
elif command -v wkhtmltopdf >/dev/null 2>&1; then
  # Fallback via plain HTML.
  python3 - "${SOC2_MD}" "${OUT_DIR}/SOC2_TYPE_II_READINESS.html" <<'PYEOF'
import sys, html
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
body = html.escape(text).replace("\n", "<br>")
open(dst, "w", encoding="utf-8").write(
  f"<!doctype html><html><body><pre>{body}</pre></body></html>"
)
PYEOF
  wkhtmltopdf "${OUT_DIR}/SOC2_TYPE_II_READINESS.html" "${SOC2_PDF}" >/dev/null 2>&1 || {
    echo "  wkhtmltopdf failed; keeping markdown copy"
    cp "${SOC2_MD}" "${OUT_DIR}/SOC2_TYPE_II_READINESS.md"
  }
else
  echo "  pandoc/wkhtmltopdf not installed; copying markdown as fallback"
  cp "${SOC2_MD}" "${OUT_DIR}/SOC2_TYPE_II_READINESS.md"
fi

# ---------------------------------------------------------------------------
# 3) Pull 12-month receipt audit PDF.
# ---------------------------------------------------------------------------

echo "[3/5] Requesting 12-month receipt audit PDF..."
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SINCE="$(date -u -v-12m +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || python3 -c "
import datetime, sys
now = datetime.datetime.utcnow()
since = now.replace(year=now.year - 1)
print(since.strftime('%Y-%m-%dT%H:%M:%SZ'))
")"

AUDIT_PDF="${OUT_DIR}/receipt-audit-${YEAR}.pdf"
JOB_JSON="$(curl -sS --max-time 8 \
  -H 'content-type: application/json' \
  -d "{\"from\":\"${SINCE}\",\"to\":\"${NOW}\",\"format\":\"pdf\"}" \
  "${BACKEND}/api/receipts/export" 2>&1)"

JOB_ID="$(echo "${JOB_JSON}" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get('job_id') or d.get('id') or '')
except Exception:
    print('')
")"

if [ -z "${JOB_ID}" ]; then
  echo "  WARN: could not start receipt-audit PDF job; response was:"
  echo "  ${JOB_JSON}" | head -c 400
  echo ""
else
  echo "  job_id=${JOB_ID} ; polling..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    STATUS="$(curl -sS --max-time 6 "${BACKEND}/api/receipts/export/${JOB_ID}" 2>&1)"
    if echo "${STATUS}" | grep -q '"status":"ready"\|"ready":true'; then
      curl -sS --max-time 60 -o "${AUDIT_PDF}" \
        "${BACKEND}/api/receipts/export/${JOB_ID}?download=1" 2>&1 | head -c 200
      [ -s "${AUDIT_PDF}" ] && break
    fi
    echo "    poll ${i}/10..."
  done
  if [ ! -s "${AUDIT_PDF}" ]; then
    echo "  WARN: receipt audit PDF not generated in time"
  fi
fi

# ---------------------------------------------------------------------------
# 4) GDPR self-export (12 months scoped to operator).
# ---------------------------------------------------------------------------

echo "[4/5] Triggering GDPR self-export..."
GDPR_ZIP="${OUT_DIR}/gdpr-export-${YEAR}.zip"

GDPR_START="$(curl -sS --max-time 8 \
  -H 'content-type: application/json' \
  -d "{}" \
  "${BACKEND}/api/gdpr/export" 2>&1)"

GDPR_JOB="$(echo "${GDPR_START}" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(d.get('job_id') or '')
except Exception:
    print('')
")"

if [ -z "${GDPR_JOB}" ]; then
  echo "  WARN: could not start GDPR export; response was:"
  echo "  ${GDPR_START}" | head -c 400
  echo ""
else
  echo "  job_id=${GDPR_JOB} ; polling..."
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    sleep 2
    GDPR_STATUS="$(curl -sS --max-time 6 "${BACKEND}/api/gdpr/export/${GDPR_JOB}" 2>&1)"
    if echo "${GDPR_STATUS}" | grep -q '"status":"ready"'; then
      curl -sS --max-time 90 -o "${GDPR_ZIP}" \
        "${BACKEND}/api/gdpr/export/${GDPR_JOB}/download" 2>&1 | head -c 200
      [ -s "${GDPR_ZIP}" ] && break
    fi
    echo "    poll ${i}/12..."
  done
  if [ ! -s "${GDPR_ZIP}" ]; then
    echo "  WARN: GDPR export zip not produced in time"
  fi
fi

# ---------------------------------------------------------------------------
# 5) Manifest + signature tying it all together.
# ---------------------------------------------------------------------------

echo "[5/5] Writing bundle manifest..."
python3 - "${OUT_DIR}" "${YEAR}" "${SINCE}" "${NOW}" <<'PYEOF'
import hashlib, json, os, sys, time

out_dir, year, since, now = sys.argv[1:5]

def sha256_of(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

artefacts = []
for name in sorted(os.listdir(out_dir)):
    if name in ("manifest.json", "signature.txt"):
        continue
    p = os.path.join(out_dir, name)
    if not os.path.isfile(p):
        continue
    artefacts.append({
        "filename": name,
        "size_bytes": os.path.getsize(p),
        "sha256": sha256_of(p),
    })

manifest = {
    "kind": "tars_annual_compliance_bundle",
    "year": int(year),
    "since": since,
    "until": now,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "contract_version": "1.0",
    "artefacts": artefacts,
}
mp = os.path.join(out_dir, "manifest.json")
with open(mp, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)

# Try to sign with the host Ed25519 key; fall back to unsigned-but-hashed.
try:
    repo_root = os.environ.get("TARS_REPO_ROOT")
    if not repo_root:
        # Walk upwards from this script's path until we find web_extras/
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            if os.path.isdir(os.path.join(cur, "web_extras")):
                repo_root = cur
                break
            cur = os.path.dirname(cur)
    if repo_root and repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from backend.core.receipts.store import (
        _resolve_host_key_path, _load_or_create_host_key,
    )
    import base64
    priv, pub = _load_or_create_host_key(_resolve_host_key_path())
    sk = Ed25519PrivateKey.from_private_bytes(priv)
    body = open(mp, "rb").read()
    sig = sk.sign(body)
    out = (
        "-----BEGIN TARS COMPLIANCE BUNDLE SIGNATURE-----\n"
        "algorithm: ed25519\n"
        f"public_key_b64: {base64.b64encode(pub).decode()}\n"
        f"key_fingerprint: {hashlib.sha256(pub).hexdigest()[:16]}\n"
        f"manifest_sha256: {hashlib.sha256(body).hexdigest()}\n"
        f"signature_b64: {base64.b64encode(sig).decode()}\n"
        "-----END TARS COMPLIANCE BUNDLE SIGNATURE-----\n"
    )
except Exception as exc:
    body = open(mp, "rb").read()
    out = (
        "-----BEGIN TARS COMPLIANCE BUNDLE SIGNATURE-----\n"
        "algorithm: ed25519\n"
        f"signing_status: fallback\n"
        f"reason: {exc}\n"
        f"manifest_sha256: {hashlib.sha256(body).hexdigest()}\n"
        "-----END TARS COMPLIANCE BUNDLE SIGNATURE-----\n"
    )
open(os.path.join(out_dir, "signature.txt"), "w").write(out)
print(f"  manifest: {mp}")
print(f"  artefacts: {len(artefacts)}")
PYEOF

echo ""
echo "=========================================================="
echo "  Bundle ready: ${OUT_DIR}"
echo "  Errors:       ${ERRORS}"
echo "=========================================================="
ls -la "${OUT_DIR}"
echo ""

# Open Finder on the result (macOS) — non-fatal if not on Mac.
if command -v open >/dev/null 2>&1; then
  open "${OUT_DIR}" 2>/dev/null || true
fi

# Auto-close terminal in 8s.
echo "(this Terminal window will close in 8s)"
sleep 8
osascript -e 'tell application "Терминал" to close (every window whose name contains "COMPLIANCE")' 2>/dev/null || true
osascript -e 'tell application "Terminal" to close (every window whose name contains "COMPLIANCE")' 2>/dev/null || true

exit 0
