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
        acceptance-tars-meeet qa-agent qa-agent-json qa-loop qa-loop-once \
        gate-release backend backend-dev desktop-dev desktop-build \
        smoke-core-bridge gate-control-tower ops-bridge-secret clean \
        planner planner-stats planner-list planner-runs planner-show \
        planner-smoke

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

gate-control-tower:  ## cockpit checks + core-bridge e2e smoke + planner smoke
	$(MAKE) cockpit-tsc
	$(MAKE) cockpit-test
	$(MAKE) smoke-core-bridge
	$(MAKE) planner-smoke

# ---------------------------------------------------------------------
# Planner CLI (operator scripting + control-tower smoke)
# ---------------------------------------------------------------------
#
# All targets shell into ``python -m backend.core.planner.cli`` so they
# share the same SQLite WAL DBs (``TARS_PLANNER_DB_PATH``,
# ``MEEET_STORE_PATH``) as the host process and can be run safely
# alongside a live cockpit.
#
# ``ARGS`` is a free-form passthrough for the targets that take a
# positional plan_id (e.g. ``make planner-show ARGS=pln_abc123``).

PLANNER ?= $(PY) -m backend.core.planner.cli
PLANNER_GOAL ?= traders.morning_check

planner:             ## raw passthrough: make planner ARGS="list --status approved"
	PYTHONPATH=. $(PLANNER) $(ARGS)

planner-stats:       ## summary counts by status
	PYTHONPATH=. $(PLANNER) stats

planner-list:        ## list plans newest-first (defaults to all statuses)
	PYTHONPATH=. $(PLANNER) list $(ARGS)

planner-runs:        ## reconstructed run history for ARGS=<plan_id>
	@if [ -z "$(ARGS)" ]; then echo "usage: make planner-runs ARGS=<plan_id>"; exit 2; fi
	PYTHONPATH=. $(PLANNER) runs $(ARGS)

planner-show:        ## inspect one plan: make planner-show ARGS=<plan_id>
	@if [ -z "$(ARGS)" ]; then echo "usage: make planner-show ARGS=<plan_id>"; exit 2; fi
	PYTHONPATH=. $(PLANNER) show $(ARGS)

planner-smoke:       ## end-to-end synthesize→stats sanity for the control tower
	@bash -c 'set -e; \
	    PYTHONPATH=. $(PLANNER) --quiet stats > /dev/null; \
	    plan_json=$$(PYTHONPATH=. $(PLANNER) --quiet synthesize "$(PLANNER_GOAL)"); \
	    plan_id=$$(echo "$$plan_json" | $(PY) -c "import json,sys; print(json.load(sys.stdin)[\"plan\"][\"id\"])"); \
	    PYTHONPATH=. $(PLANNER) --quiet show "$$plan_id" > /dev/null; \
	    PYTHONPATH=. $(PLANNER) --quiet delete --yes "$$plan_id" > /dev/null; \
	    echo "planner-smoke ok (plan_id=$$plan_id)"'

acceptance-tars-meeet:  ## production acceptance for tars.meeet.world (post-DNS)
	bash scripts/acceptance_tars_meeet.sh

qa-agent:            ## TARS QA Agent (python stdlib, no deps): autonomous probes
	$(PY) -m scripts.qa_agent

qa-agent-json:       ## QA agent in JSON mode (for CI / tooling)
	$(PY) -m scripts.qa_agent --json --no-color

qa-loop:             ## autonomous QA loop (every QA_LOOP_INTERVAL_S, default 300s)
	$(PY) -m scripts.qa_agent.loop

qa-loop-once:        ## single QA loop iteration; writes JSON report to .qa-runs/
	$(PY) -m scripts.qa_agent.loop --once

gate-release:        ## full release readiness gate: pytest + cockpit + bridge + QA
	bash scripts/gate_release.sh

ops-bridge-secret:   ## one-shot: paste BRIDGE_SHARED_SECRET (Pages env + GH secret + redeploy + QA)
	bash scripts/ops_set_bridge_shared_secret.sh

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
