# Icons

**Checked-in assets:** `32x32.png`, `128x128.png`, `128x128@2x.png`,
`icon.icns`, `icon.ico` (plus `icon.png`) are generated from
`../assets/icon-source.png` via Tauri CLI so `cargo build` /
`cargo test` succeed on fresh clones without missing-file errors.

### Regenerate after a branding change

1. Replace `../assets/icon-source.png` with a square **≥1024×1024** PNG/SVG,
   or regenerate the placeholder bitmap:
   ```bash
   cd /path/to/jarvis
   .venv/bin/pip install Pillow   # first time only (local dev machine)
   .venv/bin/python desktop/scripts/mint_placeholder_icon.py
   ```
2. From the repo root **or** `desktop/`:
   ```bash
   cd desktop && npx @tauri-apps/cli icon assets/icon-source.png -o src-tauri/icons -v
   ```
   (Equivalent: `pnpm exec tauri icon …` where `pnpm` is available.)

3. Commit `assets/icon-source.png` and updated `icons/*`.

Tauri may also emit iOS/Android subfolders under `icons/` — keep them if
your mobile tooling expects them.
