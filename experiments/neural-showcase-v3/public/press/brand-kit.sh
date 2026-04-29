#!/usr/bin/env bash
# TARS · meeet.world brand kit downloader
# ----------------------------------------
# Pulls the canonical brand assets into ./tars-brand-kit/ for press,
# partners, and integrators. No tracking, no install, no telemetry —
# just curl + the public meeet.world CDN.
#
# Usage:
#   curl -fsSL https://meeet.world/press/brand-kit.sh | bash
#
# Or, pinned to a versioned snapshot:
#   curl -fsSL https://meeet.world/press/brand-kit.sh | bash -s -- --version v9.0

set -eu

VERSION="latest"
OUTDIR="tars-brand-kit"
BASE="https://meeet.world"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --out)     OUTDIR="$2"; shift 2 ;;
    --base)    BASE="$2";   shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

ASSETS=(
  # Logos / favicon
  "favicon.svg|logo/favicon.svg"
  # Open Graph cards
  "og.svg|og/og-default.svg"
  "og-build-with.svg|og/og-build-with.svg"
  "og-pitch.svg|og/og-pitch.svg"
  "og-install.svg|og/og-install.svg"
  "og-cockpit.svg|og/og-cockpit.svg"
  # Built-with-TARS embed badges (4 variants)
  "badge/built-with-tars.svg|badge/full-dark.svg"
  "badge/built-with-tars-light.svg|badge/full-light.svg"
  "badge/built-with-tars-compact.svg|badge/compact-dark.svg"
  "badge/built-with-tars-compact-light.svg|badge/compact-light.svg"
)

mkdir -p "$OUTDIR"
echo "TARS brand kit · $VERSION → $OUTDIR/"
echo "----------------------------------------"

for entry in "${ASSETS[@]}"; do
  src="${entry%%|*}"
  dst="${entry##*|}"
  out="$OUTDIR/$dst"
  mkdir -p "$(dirname "$out")"
  printf "  %-44s " "$dst"
  if curl -fsSL "$BASE/$src" -o "$out"; then
    printf "ok\n"
  else
    printf "FAIL · skipped\n"
    rm -f "$out"
  fi
done

# Inline brand-token reference
cat > "$OUTDIR/colors.txt" <<EOF
# TARS · meeet.world brand triad
# ----------------------------------------
# Always use all three together as a sweep, never just one in isolation.
# OLED background (#000000) is canonical; paper-mode is opt-in.

INDIGO  #6366F1   # Brand accent · CTA gradients · "Pro" tier
VIOLET  #8B5CF6   # Recommended states · Council voting · "Lifetime" tier
CYAN    #06B6D4   # Live indicators · awareness · "Free" tier
ORCHID  #A78BFA   # Accent variation · sparkles · supporting

INK     #F5F5F0   # Foreground
INK-2   #B0AEA4   # Muted body copy
INK-3   #7A786F   # Tertiary / mono-tech eyebrows

BG-0    #000000   # OLED canvas
BG-1    #0B0B10   # Card surfaces
BG-2    #14141B   # Secondary fills

SUCCESS #34D399
ALERT   #EF4444

# Typography
DISPLAY  Share Tech Mono   (headlines, eyebrows)
MONO     Fira Code         (body, tabular numbers, code)
EOF

# README
cat > "$OUTDIR/README.txt" <<EOF
TARS · meeet.world brand kit ($VERSION)
========================================

This kit was downloaded with:
  curl -fsSL $BASE/press/brand-kit.sh | bash

Contents:
  logo/        Favicon (SVG, mask-icon ready)
  og/          5 Open Graph cards 1200×630, brand-triad on OLED
  badge/       "Built with TARS" embed badges (4 variants)
  colors.txt   Brand-triad reference + typography
  README.txt   This file

Permitted use:
  - Editorial coverage of meeet.world / TARS
  - Linking back via the embed badges
  - Conference / panel materials when discussing the product
  - Internal slides at companies evaluating TARS

Not permitted without written consent (legal@meeet.world):
  - Modified colours / cropping that obscure the wordmark
  - Implying partnership, endorsement, or affiliation
  - Re-selling / re-branding the marks

Press contact:        press@meeet.world
Founder availability: hello@meeet.world
Legal:                legal@meeet.world

Site:    $BASE
GitHub:  https://github.com/meeet-world/tars
EOF

echo "----------------------------------------"
echo "done · $(find "$OUTDIR" -type f | wc -l | tr -d ' ') files in $OUTDIR/"
