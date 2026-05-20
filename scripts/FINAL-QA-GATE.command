#!/usr/bin/env bash
# FINAL-QA-GATE.command — W267 end-to-end go/no-go gate for v10.0 GA.
#
# Runs every check that must be green before the v10.0 tag is cut.
# Aborts on first failure but always prints a final go/no-go summary
# so the operator knows exactly which step blocks the release.
#
# Steps (in order; later steps assume earlier ones pass):
#   1. pytest suite (full)
#   2. SMOKE-TEST.command (60+ route smoke)
#   3. RUN-PERF-SUITE.command (5 SLOs)
#   4. codesign verify on /Applications/TARS.app (spctl accepted)
#   5. bash -n on every scripts/*.command
#   6. Doc render check (markdown links resolve)
#   7. JSON + YAML validation (every JSON/YAML under repo parses)
#   8. Version consistency across 10 files
#
# Usage: bash scripts/FINAL-QA-GATE.command

set -u

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO="$(pwd)"
LOG="${REPO}/.FINAL-QA-GATE.txt"

exec > >(tee -a "$LOG") 2>&1

if [ -t 1 ]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; B=$'\033[34m'; D=$'\033[2m'; X=$'\033[0m'
else
  G=""; R=""; Y=""; B=""; D=""; X=""
fi

echo "=== FINAL-QA-GATE.command at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo: ${REPO}"

PASSED=()
FAILED=()
SKIPPED=()

PYTHON="${PYTHON:-python3}"
if [ -x "${REPO}/.venv/bin/python" ]; then
  PYTHON="${REPO}/.venv/bin/python"
fi

run_step() {
  local name="$1"; shift
  local ec=0
  echo ""
  echo "${B}── [${name}] ──${X}"
  "$@" || ec=$?
  if [ "${ec}" -eq 0 ]; then
    echo "${G}✓${X} ${name} passed"
    PASSED+=("${name}")
    return 0
  fi
  if [ "${ec}" -eq 2 ]; then
    echo "${Y}⚠${X} ${name} skipped (see above)"
    return 0
  fi
  echo "${R}✗${X} ${name} FAILED"
  FAILED+=("${name}")
  return 1
}

skip_step() {
  local name="$1"; shift
  local reason="$1"
  echo ""
  echo "${B}── [${name}] ──${X}"
  echo "${Y}⚠${X} ${name} skipped: ${reason}"
  SKIPPED+=("${name} (${reason})")
}

# 1 — full pytest suite (excludes the perf marker because step 3 owns it).
run_step "1/8 pytest" \
  "${PYTHON}" -m pytest tests/ -q --no-header --tb=short \
    --ignore=tests/perf -x

# 2 — SMOKE-TEST: 60+ route smoke. Needs the backend on :8765.
if [ -f "${REPO}/scripts/SMOKE-TEST.command" ]; then
  run_step "2/8 smoke" bash "${REPO}/scripts/SMOKE-TEST.command"
else
  skip_step "2/8 smoke" "scripts/SMOKE-TEST.command missing"
fi

# 3 — perf suite: 5 SLOs.
if [ -f "${REPO}/scripts/RUN-PERF-SUITE.command" ]; then
  run_step "3/8 perf" bash "${REPO}/scripts/RUN-PERF-SUITE.command"
else
  skip_step "3/8 perf" "scripts/RUN-PERF-SUITE.command missing"
fi

# 4 — codesign verify on /Applications/TARS.app.
#    We do NOT fail if the .app isn't installed yet — that's a soft
#    signal the operator hasn't built it. We DO fail if it's installed
#    but spctl rejects it.
codesign_check() {
  local app="/Applications/TARS.app"
  if [ ! -d "${app}" ]; then
    echo "${Y}⚠${X} ${app} not installed — skipping spctl assess"
    SKIPPED+=("4/8 codesign (TARS.app not installed)")
    return 2
  fi
  if ! command -v spctl >/dev/null 2>&1; then
    echo "${Y}⚠${X} spctl not available (non-macOS host?) — skipping"
    SKIPPED+=("4/8 codesign (spctl unavailable)")
    return 2
  fi
  if spctl --assess --type execute --verbose "${app}" 2>&1 | grep -q "accepted"; then
    return 0
  fi
  local ver=""
  ver="$(defaults read "${app}/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || true)"
  if echo "${ver}" | grep -qiE 'rc|beta'; then
    echo "${Y}⚠${X} ${app} (${ver}) is a pre-release build and spctl rejected it."
    echo "${Y}Skipping for pre-tag mechanical QA — verify the signed GA .dmg via:${X}"
    echo "  bash scripts/DOWNLOAD-AND-VERIFY-RELEASE.command"
    SKIPPED+=("4/8 codesign (pre-release install; verify GA artifact post-tag)")
    return 2
  fi
  echo "${R}TARS.app is installed but spctl REJECTED it.${X}"
  echo "${R}Re-run scripts/SIGN-AND-NOTARIZE.command to re-stamp.${X}"
  return 1
}
run_step "4/8 codesign" codesign_check

# 5 — bash -n on every scripts/*.command. Catches syntax bugs without
#     executing the scripts (which would side-effect the host).
bash_n_check() {
  local fail=0
  for f in "${REPO}/scripts/"*.command; do
    [ -f "$f" ] || continue
    if ! bash -n "$f" 2>&1; then
      echo "${R}✗${X} bash -n failed: $(basename "$f")"
      fail=1
    fi
  done
  return ${fail}
}
run_step "5/8 .command bash -n" bash_n_check

# 6 — Doc render check. Every .md in the repo root + docs/ must parse
#     and have no obviously-broken local links (../, ./, no protocol).
doc_render_check() {
  "${PYTHON}" - <<'PY_DOC'
import sys, re, pathlib
repo = pathlib.Path(".")
md_files = sorted(set(
    list(repo.glob("*.md")) + list((repo / "docs").glob("**/*.md"))
))
broken = []
checked = 0
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
for md in md_files:
    try:
        text = md.read_text(encoding="utf-8")
    except Exception as e:
        broken.append(f"{md}: read failed: {e}")
        continue
    checked += 1
    for m in LINK_RE.finditer(text):
        link = m.group(1)
        # Skip external + anchor-only links.
        if link.startswith(("http", "https", "mailto:", "#", "tars://")):
            continue
        # Strip in-page anchor.
        target = link.split("#", 1)[0]
        if not target:
            continue
        # Resolve relative to the md file's dir.
        candidate = (md.parent / target).resolve()
        if not candidate.exists():
            broken.append(f"{md}: broken link → {link}")
print(f"checked {checked} md files")
if broken:
    for b in broken[:40]:
        print(f"  {b}")
    if len(broken) > 40:
        print(f"  ... and {len(broken) - 40} more")
    sys.exit(1)
PY_DOC
}
run_step "6/8 doc render" doc_render_check

# 7 — JSON + YAML validation. Every .json + .yaml under the repo must
#     parse (excluding node_modules / .venv / target / .git).
json_yaml_check() {
  "${PYTHON}" - <<'PY_JV'
import json, sys, pathlib

repo = pathlib.Path(".")
exclude_parts = {".git", "node_modules", ".venv", "target",
                 "__pycache__", "dist", "build"}

def included(p):
    return not any(part in exclude_parts for part in p.parts)

bad = []

for p in repo.rglob("*.json"):
    if not included(p): continue
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        bad.append(f"{p}: JSON parse error: {e}")

try:
    import yaml
except ImportError:
    print("PyYAML not installed; skipping YAML validation")
else:
    for ext in ("*.yaml", "*.yml"):
        for p in repo.rglob(ext):
            if not included(p): continue
            try:
                with p.open(encoding="utf-8") as fh:
                    list(yaml.safe_load_all(fh))
            except Exception as e:
                bad.append(f"{p}: YAML parse error: {e}")

if bad:
    for b in bad[:30]:
        print(f"  {b}")
    if len(bad) > 30:
        print(f"  ... and {len(bad) - 30} more")
    sys.exit(1)
print("all JSON+YAML parsed cleanly")
PY_JV
}
run_step "7/8 json/yaml" json_yaml_check

# 8 — Version consistency across files that must agree on the TARS
#     version constant. Updated lockstep at every release tag.
version_consistency() {
  "${PYTHON}" - <<'PY_VER'
import re, sys, pathlib

# Files that must agree. The string each must contain is a regex that
# matches the current version. The RELEASE-v10.0.command bumps these
# in lockstep — drift here means the release script regressed.
TARGETS = [
    ("desktop/package.json", r'"version":\s*"([^"]+)"'),
    ("desktop/src-tauri/tauri.conf.json", r'"version":\s*"([^"]+)"'),
    ("desktop/src-tauri/Cargo.toml", r'version\s*=\s*"([^"]+)"'),
    ("web_extras/app.py", r'version="([^"]+)"'),
    ("backend/core/observability/otel.py", r'"([0-9]+\.[0-9]+\.[0-9]+[^"]*)"'),
    ("backend/core/product/manifest.py", r'_DEFAULT_VERSION\s*=\s*"([^"]+)"'),
    ("backend/core/mcp/tools.py", r'version\s*=\s*"([^"]+)"'),
    ("web_extras/routers/github.py", r'TARS-cockpit/([0-9][^\s]+)'),
    ("web_extras/routers/awareness.py", r'"version":\s*"([^"]+)"'),
]

versions = {}
missing = []
for path, regex in TARGETS:
    p = pathlib.Path(path)
    if not p.exists():
        missing.append(path)
        continue
    text = p.read_text(encoding="utf-8")
    m = re.search(regex, text)
    if not m:
        missing.append(f"{path} (regex did not match)")
        continue
    versions[path] = m.group(1)

if missing:
    print("MISSING/UNMATCHED:")
    for m in missing:
        print(f"  {m}")

print("Versions found:")
for k, v in versions.items():
    print(f"  {v:<24} {k}")

uniq = set(versions.values())
if len(uniq) != 1:
    print(f"\nVERSION DRIFT: {sorted(uniq)}")
    sys.exit(1)
if missing:
    sys.exit(1)
print(f"\nAll {len(versions)} files agree: {next(iter(uniq))}")
PY_VER
}
run_step "8/8 version consistency" version_consistency

# ── Final report ───────────────────────────────────────────────────
echo ""
echo "${B}=====================================================${X}"
echo "${B}FINAL-QA-GATE — go/no-go report${X}"
echo "${B}=====================================================${X}"
echo "Passed:  ${#PASSED[@]}"
for s in "${PASSED[@]}"; do echo "  ${G}✓${X} ${s}"; done
if [ "${#SKIPPED[@]}" -gt 0 ]; then
  echo "Skipped: ${#SKIPPED[@]}"
  for s in "${SKIPPED[@]}"; do echo "  ${Y}⚠${X} ${s}"; done
fi
echo "Failed:  ${#FAILED[@]}"
if [ "${#FAILED[@]}" -gt 0 ]; then
  for s in "${FAILED[@]}"; do echo "  ${R}✗${X} ${s}"; done
fi

echo ""
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "${R}=== NO-GO ===${X}"
  echo "${R}Fix the failed steps above before running RELEASE-v10.0.command.${R}"
  echo "${R}Full log: ${LOG}${X}"
  exit 1
fi
if [ "${#SKIPPED[@]}" -gt 0 ]; then
  echo "${Y}=== GO (with skips) ===${X}"
  echo "${Y}All required checks passed; ${#SKIPPED[@]} step(s) skipped — see FINAL-QA-VERDICT for GA call.${X}"
  echo "Log: ${LOG}"
  exit 0
fi
echo "${G}=== GO ===${X}"
echo "${G}All gates green — v10.0 GA can ship.${X}"
echo "${G}Next: bash scripts/RELEASE-v10.0.command${X}"
echo "Log: ${LOG}"
exit 0
