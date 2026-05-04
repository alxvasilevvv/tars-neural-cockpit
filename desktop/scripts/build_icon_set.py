#!/usr/bin/env python3
"""Build the full TARS icon set from a single high-res source PNG.

Run:
    .venv/bin/python desktop/scripts/build_icon_set.py \\
        --source desktop/assets/icon-source-v9.png

Pipeline:
  1. Center-crop the source to a square (so AI-generated wider art
     centred on the glyph still works as input).
  2. Resize to 1024×1024 master with high-quality LANCZOS.
  3. Emit Tauri's full icon set into ``desktop/src-tauri/icons/``:
       - ``icon.png``       (512×512 — Linux .desktop / Tauri default)
       - ``32×32.png``, ``64×64.png``, ``128×128.png``, ``128×128@2x.png``
       - ``Square{30,44,71,89,107,142,150,284,310}x*Logo.png``
         and ``StoreLogo.png`` (Windows MSIX manifest)
       - ``icon.icns``      (macOS bundle icon, native iconutil)
  4. Also writes a 1024×1024 master to ``desktop/assets/icon-source.png``
     so the next build can read from a known-good square master.

The script is idempotent — re-running with the same source replaces
every output deterministically. Fails fast on missing ``iconutil``
(macOS only); the .icns step gracefully degrades to a
``.png-only`` build with a warning so Linux/Windows operators still
get usable assets.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


# (filename, size) — Tauri standard set. Square* entries match what
# `tauri icon` would produce for the Windows MSIX manifest.
TAURI_OUTPUTS: list[tuple[str, int]] = [
    ("icon.png", 512),
    ("32x32.png", 32),
    ("64x64.png", 64),
    ("128x128.png", 128),
    ("128x128@2x.png", 256),
    ("Square30x30Logo.png", 30),
    ("Square44x44Logo.png", 44),
    ("Square71x71Logo.png", 71),
    ("Square89x89Logo.png", 89),
    ("Square107x107Logo.png", 107),
    ("Square142x142Logo.png", 142),
    ("Square150x150Logo.png", 150),
    ("Square284x284Logo.png", 284),
    ("Square310x310Logo.png", 310),
    ("StoreLogo.png", 50),
]

# Sizes baked into the .icns iconset. macOS expects @1x AND @2x for
# every "ic09" / "ic07" / etc. slot to render crisp on Retina + Pro
# Display XDR.
ICNS_SIZES: list[tuple[str, int]] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def square_master(src: Path, out_size: int = 1024) -> Image.Image:
    """Center-crop ``src`` to a square and resize to ``out_size``."""

    im = Image.open(src).convert("RGBA")
    side = min(im.width, im.height)
    left = (im.width - side) // 2
    top = (im.height - side) // 2
    cropped = im.crop((left, top, left + side, top + side))
    return cropped.resize((out_size, out_size), Image.LANCZOS)


def write_resized(master: Image.Image, dest: Path, size: int) -> None:
    """Resize ``master`` to ``size×size`` and write to ``dest``."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    master.resize((size, size), Image.LANCZOS).save(dest, "PNG", optimize=True)


def build_icns(master: Image.Image, out: Path) -> bool:
    """Build a macOS .icns from ``master`` via ``iconutil``.

    Returns ``True`` on success, ``False`` when ``iconutil`` is
    missing (Linux / Windows) — caller logs and continues.
    """

    iconutil = shutil.which("iconutil")
    if iconutil is None:
        print(
            "warn: iconutil not found — skipping .icns (macOS only). "
            "Install Xcode CLT (`xcode-select --install`) on a Mac to "
            "regenerate.",
            file=sys.stderr,
        )
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        iconset = Path(tmpdir) / "icon.iconset"
        iconset.mkdir()
        for name, size in ICNS_SIZES:
            write_resized(master, iconset / name, size)
        out.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [iconutil, "-c", "icns", "-o", str(out), str(iconset)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"error: iconutil failed: {result.stderr.strip() or result.stdout.strip()}",
                file=sys.stderr,
            )
            return False
        return True


def build_ico(master: Image.Image, out: Path) -> None:
    """Write a multi-resolution Windows .ico file.

    Pillow happily packs 16/32/48/64/128/256 into a single .ico and
    Tauri's bundler reads the first one matching its target size.
    """

    out.parent.mkdir(parents=True, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(out, "ICO", sizes=sizes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to a high-resolution source PNG (any aspect; will be center-cropped).",
    )
    parser.add_argument(
        "--icons-dir",
        type=Path,
        default=Path("desktop/src-tauri/icons"),
        help="Tauri icons output directory.",
    )
    parser.add_argument(
        "--master-out",
        type=Path,
        default=Path("desktop/assets/icon-source.png"),
        help=(
            "Where to persist the 1024×1024 squared master so the next "
            "build can re-read a known-good square (overwrites the AI "
            "source if you ran from one)."
        ),
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 1

    master = square_master(args.source, out_size=1024)
    args.master_out.parent.mkdir(parents=True, exist_ok=True)
    master.save(args.master_out, "PNG", optimize=True)
    print(f"wrote master:   {args.master_out} (1024×1024)")

    args.icons_dir.mkdir(parents=True, exist_ok=True)

    for name, size in TAURI_OUTPUTS:
        write_resized(master, args.icons_dir / name, size)
        print(f"wrote tauri:    {name:36s} ({size}×{size})")

    icns_ok = build_icns(master, args.icons_dir / "icon.icns")
    if icns_ok:
        print("wrote icns:     icon.icns (10 sizes embedded)")

    build_ico(master, args.icons_dir / "icon.ico")
    print("wrote ico:      icon.ico (7 sizes embedded)")

    print("\nIcon set ready — run `tauri build` to bundle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
