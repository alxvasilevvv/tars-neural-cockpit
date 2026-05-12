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
DESKTOP   ?= desktop

.PHONY: help test test-all test-product test-commercial-readiness lint changelog-public-check acceptance-tars-meeet qa-agent qa-agent-json qa-loop qa-loop-once \
        gate-release backend backend-dev desktop-dev desktop-build \
        smoke-core-bridge smoke-billing-tars backend-tars-up dev-tars-stack gate-control-tower ops-bridge-secret ops-billing-remote-wizard ops-cf-pages-token clean \
        install-hooks check-python-version bootstrap \
        planner planner-stats planner-list planner-runs planner-show \
        planner-full planner-clone planner-rerun planner-replay-run \
        planner-repush-run planner-smoke \
        awareness awareness-list awareness-snapshot awareness-snapshot-all \
        playbooks playbooks-list playbooks-show playbooks-run \
        playbooks-validate playbooks-validate-all playbooks-reload \
        morning-bundle morning-bundle-dry

# Picks the highest-version python3 the operator has on PATH, falling
# back to plain `python3`. Lets fresh-machine operators run
# `make bootstrap` without first installing 3.12 — the runtime is
# happy on 3.10+.
PYTHON_BOOTSTRAP ?= $(shell command -v python3.12 2>/dev/null || command -v python3.11 2>/dev/null || command -v python3.10 2>/dev/null || command -v python3 2>/dev/null)

bootstrap:           ## fresh-machine setup: create .venv + install requirements (no-op if already done)
	@if [[ -x "./.venv/bin/python" ]]; then \
	    echo "[bootstrap] .venv already exists at ./.venv — skipping create."; \
	else \
	    if [[ -z "$(PYTHON_BOOTSTRAP)" ]]; then \
	        echo "[bootstrap] no python3 in PATH — install Python 3.10+ (e.g. brew install python@3.12) and re-run." >&2; \
	        exit 2; \
	    fi; \
	    echo "[bootstrap] creating .venv with $(PYTHON_BOOTSTRAP)"; \
	    "$(PYTHON_BOOTSTRAP)" -m venv .venv; \
	fi
	@./.venv/bin/python -m pip install --upgrade pip --quiet
	@./.venv/bin/python -m pip install -r requirements.txt --quiet
	@echo "[bootstrap] python ready at $$(./.venv/bin/python -V); $$(./.venv/bin/python -m pip list 2>/dev/null | wc -l | tr -d ' ') packages installed."
	@echo "[bootstrap] next: 'cp .env.example .env' (fill secrets), then 'make dev-tars-stack' or 'make qa-agent'."

install-hooks:       ## symlink scripts/git-hooks/* into .git/hooks (re-run after fresh clone)
	@for hook in scripts/git-hooks/*; do \
	  name="$$(basename $$hook)"; \
	  target=".git/hooks/$$name"; \
	  rm -f "$$target"; \
	  ln -s "../../$$hook" "$$target"; \
	  echo "  linked $$target -> ../../$$hook"; \
	done

check-python-version:  ## fail fast if python3 < 3.10 (required by pinned FastAPI stack)
	@python3 -c 'import sys; v=sys.version_info[:2]; assert v >= (3, 10), ("Need Python 3.10+ (found %s.%s). brew install python@3.12 && PATH=/opt/homebrew/opt/python@3.12/bin:$$PATH make test" % v); print("python ok:", sys.version.split()[0])'

help:                ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk -F':.*?## ' 'BEGIN{FS=":.*?## "}{printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------

backend:             ## run uvicorn against the FastAPI app
	PYTHONPATH=. $(PY) -m uvicorn web_extras.app:app --host $(HOST) --port $(PORT)

backend-dev:         ## same, with --reload
	PYTHONPATH=. $(PY) -m uvicorn web_extras.app:app --host $(HOST) --port $(PORT) --reload

test:                ## full pytest suite
	PYTHONPATH=. $(PYTEST) tests

test-product:        ## focused tests for the new download manifest surface
	PYTHONPATH=. $(PYTEST) tests/test_product_downloads.py tests/test_search_router.py

test-commercial-readiness:  ## chain sweep: sell surfaces (domains, entitlements, product, policy, meeet, playbooks) + B-001 redirects
	PYTHONPATH=. $(PYTEST) tests/test_commercial_readiness_chain.py -q

# ---------------------------------------------------------------------
# Public changelog trim (docs artefact; no SPA)
# ---------------------------------------------------------------------

changelog-public-check:  ## committed CHANGELOG_PUBLIC matches generator
	$(PY) scripts/generate_public_changelog.py --check

test-all:            ## pytest + changelog check (CI default)
	$(MAKE) test
	$(MAKE) changelog-public-check

# ---------------------------------------------------------------------
# Desktop (Tauri)
# ---------------------------------------------------------------------

desktop-dev:         ## run the Tauri shell (serves bundled web from src-tauri/web)
	pnpm --dir $(DESKTOP) tauri:dev

desktop-build:       ## bundle the Tauri desktop (uses committed src-tauri/web)
	pnpm --dir $(DESKTOP) release

# ---------------------------------------------------------------------
# Control tower smoke (Supabase bridge)
# ---------------------------------------------------------------------

smoke-core-bridge:   ## end-to-end smoke: old core-bridge -> new tars-ingest
	bash scripts/with_repo_env.sh bash scripts/smoke_core_bridge_e2e.sh

gate-control-tower:  ## changelog trim + core-bridge e2e smoke + planner / playbooks gates
	$(MAKE) changelog-public-check
	$(MAKE) smoke-core-bridge
	$(MAKE) planner-smoke
	$(MAKE) playbooks-validate-all

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

planner-full:        ## plan + runs + lifetime usage: make planner-full ARGS=<plan_id>
	@if [ -z "$(ARGS)" ]; then echo "usage: make planner-full ARGS=<plan_id>"; exit 2; fi
	PYTHONPATH=. $(PLANNER) full $(ARGS)

planner-clone:       ## fork plan w/o running: make planner-clone ARGS="<plan_id> [target_thread]"
	@if [ -z "$(ARGS)" ]; then echo 'usage: make planner-clone ARGS="<plan_id> [target_thread]"'; exit 2; fi
	@bash -c 'set -e; \
	    set -- $(ARGS); \
	    plan_id=$$1; \
	    target_thread=$${2:-}; \
	    if [ -z "$$plan_id" ]; then echo "usage: make planner-clone ARGS=\"<plan_id> [target_thread]\""; exit 2; fi; \
	    if [ -n "$$target_thread" ]; then \
	        PYTHONPATH=. $(PLANNER) clone "$$plan_id" --thread-id "$$target_thread"; \
	    else \
	        PYTHONPATH=. $(PLANNER) clone "$$plan_id"; \
	    fi'

planner-rerun:       ## clone+approve+run in one: make planner-rerun ARGS=<plan_id> [MODE=autopilot|confirm|dry_run]
	@if [ -z "$(ARGS)" ]; then echo "usage: make planner-rerun ARGS=<plan_id> [MODE=autopilot|confirm|dry_run]"; exit 2; fi
	@if [ -n "$(MODE)" ]; then \
	    PYTHONPATH=. $(PLANNER) clone $(ARGS) --approve --run --mode "$(MODE)"; \
	else \
	    PYTHONPATH=. $(PLANNER) clone $(ARGS) --approve --run; \
	fi

# Dumps one run's events to JSONL for backfill / audit. The plan_id
# is informational (used in the default filename) so cron jobs can
# tail .meeet-replays/<plan_id>-<run_trace>.jsonl after a meeet
# ingest outage. OUT= overrides the path; MEEET_REPLAY_DIR overrides
# the default directory.
MEEET_REPLAY_DIR ?= .meeet-replays
planner-replay-run:  ## dump one run to JSONL: make planner-replay-run ARGS="<plan_id> <run_trace>" [OUT=<path>]
	@if [ -z "$(ARGS)" ]; then echo 'usage: make planner-replay-run ARGS="<plan_id> <run_trace>" [OUT=<path>]'; exit 2; fi
	@bash -c 'set -e; \
	    set -- $(ARGS); \
	    plan_id=$$1; \
	    run_trace=$${2:-}; \
	    if [ -z "$$plan_id" ] || [ -z "$$run_trace" ]; then \
	        echo "usage: make planner-replay-run ARGS=\"<plan_id> <run_trace>\" [OUT=<path>]"; \
	        exit 2; \
	    fi; \
	    out_path="$(OUT)"; \
	    if [ -z "$$out_path" ]; then \
	        mkdir -p "$(MEEET_REPLAY_DIR)"; \
	        out_path="$(MEEET_REPLAY_DIR)/$$plan_id-$$run_trace.jsonl"; \
	    fi; \
	    PYTHONPATH=. $(PY) -m backend.core.meeet.replay_cli \
	        --export "$$out_path" --trace-id "$$run_trace" --limit 1000; \
	    echo "planner-replay-run wrote $$out_path"'

# Force-repushes every event for one trace upstream, regardless of
# the existing pushed flag. Use after a meeet ingest outage /
# contract bump when you need to re-emit one run's events for
# billing backfill or audit. LIMIT= caps rows scanned (default
# 1000 — same as the CLI default).
planner-repush-run:  ## re-emit one run upstream: make planner-repush-run ARGS=<run_trace> [LIMIT=N]
	@if [ -z "$(ARGS)" ]; then echo "usage: make planner-repush-run ARGS=<run_trace> [LIMIT=N]"; exit 2; fi
	@if [ -n "$(LIMIT)" ]; then \
	    PYTHONPATH=. $(PY) -m backend.core.meeet.replay_cli --repush-trace $(ARGS) --limit $(LIMIT); \
	else \
	    PYTHONPATH=. $(PY) -m backend.core.meeet.replay_cli --repush-trace $(ARGS); \
	fi

planner-smoke:       ## end-to-end synthesize→stats sanity for the control tower
	@bash -c 'set -e; \
	    PYTHONPATH=. $(PLANNER) --quiet stats > /dev/null; \
	    plan_json=$$(PYTHONPATH=. $(PLANNER) --quiet synthesize "$(PLANNER_GOAL)"); \
	    plan_id=$$(echo "$$plan_json" | $(PY) -c "import json,sys; print(json.load(sys.stdin)[\"plan\"][\"id\"])"); \
	    PYTHONPATH=. $(PLANNER) --quiet show "$$plan_id" > /dev/null; \
	    PYTHONPATH=. $(PLANNER) --quiet delete --yes "$$plan_id" > /dev/null; \
	    echo "planner-smoke ok (plan_id=$$plan_id)"'

# ---------------------------------------------------------------------
# Awareness CLI (operator parity with planner CLI)
# ---------------------------------------------------------------------
#
# All targets shell into ``python -m backend.core.domains.awareness_cli``
# so they share the same domain registry as the host process and emit
# the same ``awareness.snapshot.*`` events the cockpit's HTTP path
# does (cockpit dashboards see CLI invocations the same as HTTP ones).
#
# ARGS is a free-form passthrough for the targets that take positional
# args (e.g. ``make awareness-snapshot ARGS="traders binance_ws"``).

AWARENESS ?= $(PY) -m backend.core.domains.awareness_cli

awareness:           ## raw passthrough: make awareness ARGS="snapshot traders binance_ws"
	PYTHONPATH=. $(AWARENESS) $(ARGS)

awareness-list:      ## list awareness sources (all packs or one): make awareness-list [ARGS=<slug>]
	PYTHONPATH=. $(AWARENESS) list $(ARGS)

awareness-snapshot:  ## materialise one source: make awareness-snapshot ARGS="<slug> <source_id>"
	@if [ -z "$(ARGS)" ]; then echo 'usage: make awareness-snapshot ARGS="<slug> <source_id>"'; exit 2; fi
	@bash -c 'set -e; \
	    set -- $(ARGS); \
	    slug=$$1; \
	    source_id=$${2:-}; \
	    if [ -z "$$slug" ] || [ -z "$$source_id" ]; then \
	        echo "usage: make awareness-snapshot ARGS=\"<slug> <source_id>\""; \
	        exit 2; \
	    fi; \
	    PYTHONPATH=. $(AWARENESS) snapshot "$$slug" "$$source_id"'

awareness-snapshot-all:  ## materialise every fetcher-bearing source: make awareness-snapshot-all ARGS=<slug>
	@if [ -z "$(ARGS)" ]; then echo "usage: make awareness-snapshot-all ARGS=<slug>"; exit 2; fi
	PYTHONPATH=. $(AWARENESS) snapshot-all $(ARGS)

# ---------------------------------------------------------------------
# Playbooks CLI (operator parity with planner / awareness CLIs)
# ---------------------------------------------------------------------
#
# All targets shell into ``python -m backend.core.playbooks.cli`` so
# they share the same loader + runner as the FastAPI route in
# ``web_extras/routers/playbooks.py``. Emitted ``playbook.*`` events
# land in the local meeet buffer the cockpit reads from, so a
# cron-driven invocation is indistinguishable from a HTTP one in
# the dashboards.
#
# ARGS is a free-form passthrough for targets that take a positional
# ``<id>`` (e.g. ``make playbooks-show ARGS=traders.morning_check``).
# Run target also accepts standalone ``CONTEXT=...`` and ``MODE=...``
# vars so the common cron pattern reads cleanly:
#
#   make playbooks-run ARGS=traders.morning_check MODE=autopilot \
#                      CONTEXT='{"basket":["BTC","ETH"]}'

PLAYBOOKS ?= $(PY) -m backend.core.playbooks.cli

playbooks:           ## raw passthrough: make playbooks ARGS="run <id>"
	PYTHONPATH=. $(PLAYBOOKS) $(ARGS)

playbooks-list:      ## list playbooks (optionally one pack): make playbooks-list [ARGS=--pack=<pack>]
	PYTHONPATH=. $(PLAYBOOKS) list $(ARGS)

playbooks-show:      ## show one playbook: make playbooks-show ARGS=<id>
	@if [ -z "$(ARGS)" ]; then echo 'usage: make playbooks-show ARGS=<id>'; exit 2; fi
	PYTHONPATH=. $(PLAYBOOKS) show $(ARGS)

playbooks-run:       ## execute a playbook: make playbooks-run ARGS=<id> [MODE=<mode>] [CONTEXT='<json>']
	@if [ -z "$(ARGS)" ]; then echo 'usage: make playbooks-run ARGS=<id> [MODE=<mode>] [CONTEXT='\''<json>'\'']'; exit 2; fi
	@bash -c 'set -e; \
	    extra=""; \
	    if [ -n "$(MODE)" ]; then extra="$$extra --mode $(MODE)"; fi; \
	    if [ -n "$(CONTEXT)" ]; then extra="$$extra --context $(CONTEXT)"; fi; \
	    PYTHONPATH=. $(PLAYBOOKS) run $(ARGS) $$extra'

playbooks-validate:  ## strict-validate one playbook: make playbooks-validate ARGS=<id>
	@if [ -z "$(ARGS)" ]; then echo 'usage: make playbooks-validate ARGS=<id>'; exit 2; fi
	PYTHONPATH=. $(PLAYBOOKS) validate $(ARGS)

playbooks-validate-all:  ## strict-validate every playbook on disk (CI gate)
	PYTHONPATH=. $(PLAYBOOKS) validate-all

playbooks-reload:    ## reset loader cache + re-scan playbooks dir
	PYTHONPATH=. $(PLAYBOOKS) reload

# ---------------------------------------------------------------------
# Morning bundle (cron-shipped multi-playbook wrapper)
# ---------------------------------------------------------------------
#
# Wraps every playbook tagged ``morning`` (or the override list in
# ``MORNING_PLAYBOOKS``) into one cron-friendly invocation that:
#   - runs each playbook sequentially in MORNING_MODE
#     (default ``confirm``; cron should set ``autopilot``);
#   - flushes the meeet replay buffer at the end so events from
#     this morning's runs reach upstream;
#   - writes an aggregate evidence JSON to MORNING_OUTPUT_DIR
#     (default ``.morning-runs``);
#   - exits 1 on any playbook failure, 2 on operator error
#     (no playbooks discovered, missing dep), 0 on full green.
#
# See ``scripts/playbooks_morning_cron.sh`` for the full env knob
# matrix; the Make targets are thin wrappers that surface the
# common cron pattern (``morning-bundle MODE=autopilot``) and a
# DRY-mode variant (``morning-bundle-dry``) that runs in
# ``dry_run`` policy mode for safe local rehearsal.

morning-bundle:      ## run every morning-tagged playbook + flush meeet [MODE=<mode>] [PLAYBOOKS=<csv>]
	@MORNING_MODE=$${MODE:-$(MODE)} \
	  MORNING_PLAYBOOKS=$${PLAYBOOKS:-$(PLAYBOOKS_OVERRIDE)} \
	  bash scripts/playbooks_morning_cron.sh

morning-bundle-dry:  ## same as morning-bundle but forced dry_run mode (safe rehearsal)
	@MORNING_MODE=dry_run bash scripts/playbooks_morning_cron.sh

acceptance-tars-meeet:  ## production acceptance for tars.meeet.world (post-DNS)
	bash scripts/with_repo_env.sh bash scripts/acceptance_tars_meeet.sh

qa-agent:            ## TARS QA Agent (python stdlib, no deps): autonomous probes
	bash scripts/with_repo_env.sh $(PY) -m scripts.qa_agent

qa-agent-json:       ## QA agent in JSON mode (for CI / tooling)
	bash scripts/with_repo_env.sh $(PY) -m scripts.qa_agent --json --no-color

qa-loop:             ## autonomous QA loop (every QA_LOOP_INTERVAL_S, default 300s)
	bash scripts/with_repo_env.sh $(PY) -m scripts.qa_agent.loop

qa-loop-once:        ## single QA loop iteration; writes JSON report to .qa-runs/
	bash scripts/with_repo_env.sh $(PY) -m scripts.qa_agent.loop --once

gate-release:        ## full release readiness gate: pytest + changelog + bridge + QA
	bash scripts/gate_release.sh

ops-bridge-secret:   ## one-shot: paste BRIDGE_SHARED_SECRET (Pages env + GH secret + redeploy + QA)
	bash scripts/ops_set_bridge_shared_secret.sh

ops-billing-remote-wizard:  ## paste MEEET_BILLING_API_KEY; prod smoke + optional .env merge + pytest
	bash scripts/ops_billing_remote_wizard.sh

smoke-billing-tars:  ## with .env: stdlib GET remote operator (no uvicorn)
	bash scripts/smoke_billing_tars_backend.sh

backend-tars-up:  ## kill :8765 if busy; start uvicorn+.env in bg; curl /api/entitlements
	bash scripts/backend_tars_up.sh

dev-tars-stack:  ## backend-tars-up then leaves API running (no separate SPA)
	bash scripts/dev_tars_stack.sh

launch-precheck:  ## Wave 64: single-command verification before tagging v9.1.0
	bash scripts/launch_precheck.sh

launch-precheck-full:  ## launch-precheck + cargo check + smoke-billing-tars
	bash scripts/launch_precheck.sh --full

ops-cf-pages-token:  ## cf-operator.env (id+cfat_) → GitHub secret + run Pages deploy workflow
	bash scripts/ops_push_cloudflare_pages_api_token.sh

# ---------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------

clean:               ## drop build outputs, keep node_modules / .venv
	rm -rf $(DESKTOP)/src-tauri/target
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	@find . -name '.pytest_cache' -type d -prune -exec rm -rf {} +
	@find . -name '*.pyc' -delete
