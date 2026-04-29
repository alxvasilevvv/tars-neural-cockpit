# pyoxidizer.bzl — embed CPython 3.12 + the TARS repo into a single
# binary (`tars-backend`) that the Tauri shell spawns as a sidecar.
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

REPO_ROOT = CWD + "/.."

def make_dist():
    return default_python_distribution(python_version = "3.12")

def make_packaging_policy(dist):
    policy = dist.make_python_packaging_policy()
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.include_distribution_sources = True
    policy.include_distribution_resources = False
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

    # Pull every requirements pin into the binary. Test extras stay out.
    exe.add_python_resources(exe.pip_install([
        "fastapi==0.115.0",
        "uvicorn[standard]==0.30.6",
        "pynacl==1.5.0",
        "pydantic==2.9.2",
    ]))

    # Ship the repo source verbatim under `lib/`.
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
