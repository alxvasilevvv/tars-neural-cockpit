#!/usr/bin/env python3
"""Mint a 1024×1024 app icon PNG for ``pnpm exec tauri icon``.

Dependency: ``pip install Pillow``.

    python3 desktop/scripts/mint_placeholder_icon.py
    cd desktop && pnpm exec tauri icon assets/icon-source.png -o src-tauri/icons

Committed ``assets/icon-source.png`` is the source of truth for CI/Tauri;
re-run after brand pass with a real design asset if needed.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icon-source.png"

# meeet / TARS triad — indigo field, cyan accent, light letter
BG = (15, 15, 24, 255)
DISC = (79, 70, 229, 255)
HALO = (6, 182, 212, 220)
LETTER = (248, 250, 252, 255)


def main() -> None:
    size = 1024
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = int(size * 0.38)
    # Main disc
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=DISC)
    # Inner subtle ring (simulated with slightly smaller ellipse + stroke)
    r2 = int(r * 0.82)
    draw.ellipse(
        (cx - r2, cy - r2, cx + r2, cy + r2),
        outline=HALO,
        width=int(size * 0.022),
    )
    # "T" from primitives (readable at dock sizes)
    bar_w = int(size * 0.44)
    bar_h = int(size * 0.11)
    stem_w = int(size * 0.12)
    top = cy - int(size * 0.16)
    draw.rounded_rectangle(
        (cx - bar_w // 2, top, cx + bar_w // 2, top + bar_h),
        radius=16,
        fill=LETTER,
    )
    stem_top = top + bar_h
    stem_bot = cy + int(size * 0.2)
    draw.rounded_rectangle(
        (cx - stem_w // 2, stem_top, cx + stem_w // 2, stem_bot),
        radius=12,
        fill=LETTER,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
