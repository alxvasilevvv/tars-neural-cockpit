# TARS desktop shell (Tauri 2)

Phase **L9** of `docs/PHASE_L_ROADMAP.md`. This folder packages the
already-shipped React cockpit (`experiments/neural-showcase-v3/`) and
the FastAPI backend (`web_extras/app.py` mounted on `serve.py`) into a
single signed installer:

- **macOS** — `TARS-<version>.dmg` (Apple Developer ID notarised).
- **Windows** — `TARS-<version>-Setup.exe` (Authenticode signed).

Distribution is **direct download from the official site** (HTTPS,
SHA256-checksum, `tauri-plugin-updater`). Mac App Store / Microsoft
Store listings are explicitly out of scope for v1.

## Status

- [x] Project layout sketched (this folder).
- [x] `src-tauri/` minimal Rust shell with one window loading the
      cockpit dist (or local Vite dev server in dev mode).
- [x] Sidecar spawn hook wired with health-poll + lifecycle events
      (`desktop.sidecar.started|failed|exited`). Schema:
      `desktop/src-tauri/sidecar-events.schema.json`. Pinned by
      `tests/test_desktop_sidecar_events_contract.py`.
- [x] Sidecar binary resolution: `TARS_BACKEND_BIN` env var → bundled
      `tars-backend(.exe)` in resource_dir → `python3 serve.py`
      fallback. Pyoxidizer config: `desktop/pyoxidizer.bzl`.
- [ ] Cross-target pyoxidizer CI build matrix (darwin × {aarch64,
      x86_64}, windows × {x86_64, aarch64}, linux × {x86_64,
      aarch64}). Local `pyoxidizer build` works on the host arch.
- [ ] Notarise on macOS, Authenticode-sign on Windows.
- [x] Updater channel publisher landed (Phase L9 K2): see
      `python -m backend.core.product.publish --updater-out …` and
      `backend/core/product/updater.py`. Tauri config endpoints already
      point at `meeet.world/updates/{{target}}/{{current_version}}.json`.
      Real **minisign** signing key is still a CI-only artefact; locally
      the publisher reads `<artifact>.sig` sidecar files when present.

## Layout

```
desktop/
├── README.md                 ← this file
├── package.json              ← npm scripts (dev / build / bundle)
├── .gitignore
├── public/
│   └── icon.png              ← placeholder; Claude swaps in branded
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   ├── icons/                ← placeholder icons
│   └── src/
│       ├── main.rs           ← entry point, spawns sidecar, manages window
│       └── sidecar.rs        ← TODO: bring up FastAPI as a child process
└── scripts/
    └── package-cockpit.sh    ← copies the v3 dist into Tauri's web root
```

## How to run (dev)

> Requires Node 20+, pnpm 9+, Rust stable, and the v3 cockpit already
> installed (`cd ../experiments/neural-showcase-v3 && pnpm install`).

```bash
cd desktop
pnpm install                    # installs @tauri-apps/cli
pnpm tauri:dev                  # spins up Vite + Tauri window
```

For a release build (no signing, just shape the artifact):

```bash
pnpm tauri:build
# artifacts land under desktop/src-tauri/target/release/bundle/
```

Eventually `pnpm release` will:

1. `pnpm --filter neural-showcase-v3 build`
2. `bash scripts/package-cockpit.sh`
3. `pnpm tauri build`
4. Compute SHA256 + upload via the release pipeline (out of scope here).

## Sidecar (shipped — Phase L9 A1)

CPython 3.12 + the repo are embedded via **pyoxidizer**
(`desktop/pyoxidizer.bzl`). Local build:

```
pyoxidizer build --release --target-triple aarch64-apple-darwin tars-backend
```

The Rust side (`src-tauri/src/sidecar.rs`) resolves the backend in
this order:

1. `$TARS_BACKEND_BIN` (explicit override; CI / dev).
2. `<resource_dir>/tars-backend(.exe)` (bundled pyoxidizer build
   shipped inside the `.dmg` / `.exe`).
3. `python3 serve.py` (local-dev fallback when running from source).

It spawns the child with `PORT=8765 HOST=127.0.0.1`, then polls
`http://127.0.0.1:8765/health` (250 ms cadence, 15 s ceiling). On
success it emits `desktop.sidecar.started`. On spawn error or health
timeout it emits `desktop.sidecar.failed`. On app shutdown the
`SidecarHandle` SIGTERMs the child, waits up to 5 s, then SIGKILLs,
and emits `desktop.sidecar.exited` with `exit_code` / `signal` /
`ran_ms`.

The event payload contract lives at
`desktop/src-tauri/sidecar-events.schema.json` (v1.0.0) and is
pinned by `tests/test_desktop_sidecar_events_contract.py`.

## Distribution

The website serves installers directly from our own HTTPS origin;
`/api/product/downloads` (Block B in `AGENT_HANDOFF.md`) returns a
machine-readable manifest the marketing site **and**
[meeet.world](https://meeet.world) consume. No App Store dependency.

## Acceptance for L9 v1

1. `pnpm tauri:dev` opens a window with the live cockpit on macOS + Windows.
2. `pnpm tauri:build` produces `.dmg` / `.exe` shaped artifacts (sign-ready).
3. The cockpit can hit `http://127.0.0.1:8765/health` of the sidecar
   when wired (currently mock-OK).
4. `tauri-plugin-updater` configured with the production update URL.
5. Smoke test recorded in `docs/AGENT_HANDOFF.md`.
