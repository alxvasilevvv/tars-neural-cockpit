# TARS — convenience targets.
#
# Stdlib-only philosophy: this Makefile prefers `python -m`, `pnpm`, and
# `bash` invocations that already exist; we deliberately don't pull in
# `just`, `task`, or any other runner.

PY        ?= .venv/bin/python
PIP       ?= .venv/bin/pip
PORT      ?= 8765
HOST      ?= 127.0.0.1
PYTEST    ?= $(PY) -m pytest -q
COCKPIT   ?= experiments/neural-showcase-v3
DESKTOP   ?= desktop

.PHONY: help test test-product lint cockpit cockpit-build cockpit-tsc \
        acceptance-tars-meeet \
        backend backend-dev desktop-dev desktop-build smoke-core-bridge \
        gate-control-tower clean

help:                ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' 'BEGIN{FS=":.*?## "}{printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------

backend:             ## run uvicorn against the cockpit FastAPI app
	PYTHONPATH=. $(PY) -m uvicorn web_extras.app:app --host $(HOST) --port $(PORT)

backend-dev:         ## same, with --reload
	PYTHONPATH=. $(PY) -m uvicorn web_extras.app:app --host $(HOST) --port $(PORT) --reload

test:                ## full pytest suite
	PYTHONPATH=. $(PYTEST) tests

test-product:        ## focused tests for the new download manifest surface
	PYTHONPATH=. $(PYTEST) tests/test_product_downloads.py tests/test_search_router.py

# ---------------------------------------------------------------------
# Cockpit (React)
# ---------------------------------------------------------------------

cockpit:             ## run the v3 cockpit dev server
	pnpm --dir $(COCKPIT) dev

cockpit-build:       ## production build (output: dist/)
	pnpm --dir $(COCKPIT) build

cockpit-tsc:         ## type-check only
	pnpm --dir $(COCKPIT) exec tsc --noEmit

cockpit-test:        ## run the cockpit Vitest suite (jsdom + lib/downloads.ts)
	pnpm --dir $(COCKPIT) test

test-all:            ## pytest + vitest in one go (CI default)
	$(MAKE) test
	$(MAKE) cockpit-test

# ---------------------------------------------------------------------
# Desktop (Tauri)
# ---------------------------------------------------------------------

desktop-dev:         ## run the Tauri shell against the dev cockpit
	pnpm --dir $(DESKTOP) tauri:dev

desktop-build:       ## bundle the cockpit + Tauri release artifacts
	pnpm --dir $(DESKTOP) release

# ---------------------------------------------------------------------
# Control tower smoke (Supabase bridge)
# ---------------------------------------------------------------------

smoke-core-bridge:   ## end-to-end smoke: old core-bridge -> new tars-ingest
	bash scripts/smoke_core_bridge_e2e.sh

gate-control-tower:  ## cockpit checks + core-bridge e2e smoke
	$(MAKE) cockpit-tsc
	$(MAKE) cockpit-test
	$(MAKE) smoke-core-bridge

acceptance-tars-meeet:  ## production acceptance for tars.meeet.world (post-DNS)
	bash scripts/acceptance_tars_meeet.sh

# ---------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------

clean:               ## drop build outputs, keep node_modules / .venv
	rm -rf $(COCKPIT)/dist
	rm -rf $(DESKTOP)/src-tauri/target
	rm -rf $(DESKTOP)/src-tauri/web
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	@find . -name '.pytest_cache' -type d -prune -exec rm -rf {} +
	@find . -name '*.pyc' -delete
