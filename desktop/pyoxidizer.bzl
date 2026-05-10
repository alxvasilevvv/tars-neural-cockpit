# pyoxidizer.bzl — embed CPython 3.12 + the TARS repo into a single
# binary (`tars-backend`) that the Tauri shell spawns as a sidecar
# (see `desktop/src-tauri/src/sidecar.rs:bundled_backend`).
#
# Usage (locally):
#
#     pyoxidizer build --release \
#         --target-triple aarch64-apple-darwin \
#         tars-backend
#
# Cross-target builds are driven by CI from the same file via
# `--target-triple {x86_64-apple-darwin,aarch64-apple-darwin,
# x86_64-pc-windows-msvc,aarch64-pc-windows-msvc,x86_64-unknown-linux-gnu,
# aarch64-unknown-linux-gnu}`.
#
# The packaged binary boots uvicorn against ``web_extras.app:app`` on
# 127.0.0.1:$PORT (default 8765). Tauri reads $PORT and gates the
# splash on /health.
#
# ────────────────────────────────────────────────────────────────────
# Single source of truth contract
# ────────────────────────────────────────────────────────────────────
#
# RUNTIME_REQUIREMENTS below MUST stay in lockstep with the
# repository-root `requirements.txt`. The parity guard
# `tests/test_pyoxidizer_requirements_parity.py` fails CI if they
# drift, so the bundle never ships a stale dependency pin.
#
# Test extras (pytest, pytest-asyncio, jsonschema) deliberately stay
# OUT of the bundle — the sidecar is a runtime-only artefact.
#
# Runtime data directories (`data/`, `playbooks/`, `prompts/`) are
# bundled as `read_package_root` resources rather than file-manifest
# entries because every TARS module that touches them imports them
# through Python paths (e.g. `backend.core.domains.packs.<slug>`).
# Adjacent non-Python data files (CSV / JSON seeds) ride along via
# `include_distribution_resources` on the packaging policy.

REPO_ROOT = CWD + "/.."

# ⚠ Pinned to the same versions as `requirements.txt`. The parity
# test reads both files; a drift here will fail the test. To bump a
# pin, edit `requirements.txt` and mirror the change here in the
# same commit.
RUNTIME_REQUIREMENTS = [
    # Web / API
    "fastapi==0.136.1",
    "uvicorn[standard]==0.46.0",
    "pydantic==2.13.3",
    "pydantic-settings==2.14.0",
    # HTTP clients
    "httpx==0.28.1",
    "httpx-sse==0.4.3",
    # Attachment ingest (PDF parsing).
    "pypdf>=5.0,<6.0",
    # Phase L5 — encrypted sync envelope (X25519 + XChaCha20-Poly1305).
    "pynacl>=1.5,<2.0",
    # Phase M2 / N3 — EVM wallet signing.
    "eth-account>=0.13,<0.14",
    # Phase N4 — TON wallet.
    "tonsdk>=1.0,<2.0",
    # Phase N5 — Solana transaction signing.
    "solders>=0.21,<1.0",
    # Phase O / observability — OpenTelemetry traces shipped from
    # `backend/core/observability/otel.py`. The SDK degrades gracefully
    # at runtime when missing, but shipping it in the sidecar avoids
    # the "trace export silently disabled in installed app" footgun
    # operators hit when comparing dev (venv) vs prod (pyoxidizer).
    "opentelemetry-api>=1.27,<2",
    "opentelemetry-sdk>=1.27,<2",
    "opentelemetry-exporter-otlp-proto-http>=1.27,<2",
]

def make_dist():
    return default_python_distribution(python_version = "3.12")

def make_packaging_policy(dist):
    policy = dist.make_python_packaging_policy()
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.include_distribution_sources = True
    # Adjacent CSV/JSON seeds in `data/` ride along with the package
    # so loaders that read them by relative path still find them.
    policy.include_distribution_resources = True
    policy.include_test = False
    return policy

def make_python_config(dist):
    cfg = dist.make_python_interpreter_config()
    cfg.run_command = (
        "import os; "
        "import uvicorn; "
        "uvicorn.run("
        "    'web_extras.app:app', "
        "    host=os.environ.get('HOST', '127.0.0.1'), "
        "    port=int(os.environ.get('PORT', '8765')), "
        "    log_level=os.environ.get('LOG_LEVEL', 'info'), "
        ")"
    )
    return cfg

def make_exe():
    dist = make_dist()
    policy = make_packaging_policy(dist)
    config = make_python_config(dist)

    exe = dist.to_python_executable(
        name = "tars-backend",
        packaging_policy = policy,
        config = config,
    )

    # Pull every runtime requirement into the bundle. Pins mirror
    # `requirements.txt` — see the parity guard test.
    exe.add_python_resources(exe.pip_install(RUNTIME_REQUIREMENTS))

    # Ship the repo source verbatim under `lib/`. Both packages are
    # required by the uvicorn entrypoint (`web_extras.app:app` →
    # `backend.core.*` chain). `tests/` and `experiments/` stay out.
    exe.add_python_resources(exe.read_package_root(
        path = REPO_ROOT,
        packages = [
            "backend",
            "web_extras",
        ],
    ))

    return exe

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files

register_target("exe", make_exe)
register_target("install", make_install, depends = ["exe"], default = True)
register_target("tars-backend", make_install, depends = ["exe"], default = True)

resolve_targets()
