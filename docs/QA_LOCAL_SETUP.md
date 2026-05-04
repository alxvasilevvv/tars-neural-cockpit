# QA — local setup for TARS (cockpit + backend tests)

Minimal paths validated on macOS; Linux/WSL analogous.

## Cockpit (`experiments/neural-showcase-v3`)

- **Node:** ≥ 20 (`node -v`).
- **Install:** `npm ci`
- **Checks:** `npm run test` · `npm run typecheck` · `npm run build`  
  Production API base is baked from `.env.production` (`VITE_TARS_API=https://tars.meeet.world`).

## Backend (`pytest` / `make test`)

Pinned stack (**FastAPI 0.136.x**) requires **Python ≥ 3.10**. Apple’s default `/usr/bin/python3` is often **3.9** — installs will fail with “No matching distribution”.

1. Install a current Python (example Homebrew):  
   `brew install python@3.12`  
   Then use that binary for the venv:
   ```bash
   cd /path/to/tars-neural-cockpit
   /opt/homebrew/opt/python@3.12/bin/python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   PYTHONPATH=. .venv/bin/python -m pytest tests -q
   ```
2. Quick gate: **`make check-python-version`** (fails fast on 3.9).

## Desktop (`desktop/`)

Tauri build expects **pnpm** + packaged cockpit; see `desktop/package.json` — not covered in this short guide.

## Install page vs manifest

`/install` prefers **`GET /api/product/downloads`** when it loads so version and filenames match production. GitHub Release URLs may **404** for anonymous users when the repo is private (**B-017**); the UI surfaces a banner and brew/curl fallbacks.
