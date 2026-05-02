#!/usr/bin/env bash
# Bash completion for the TARS planner CLI.
#
# Install (one of):
#
#   # ad-hoc, current shell only
#   source scripts/planner-completion.bash
#
#   # persistent (Linux)
#   sudo cp scripts/planner-completion.bash /etc/bash_completion.d/tars-planner
#
#   # persistent (macOS, with homebrew bash-completion@2)
#   cp scripts/planner-completion.bash \
#       "$(brew --prefix)/etc/bash_completion.d/tars-planner"
#
# Then alias the long invocation if you have not already:
#
#   alias tars-planner='python -m backend.core.planner.cli'
#   complete -F _tars_planner tars-planner
#
# Provides:
#   - Subcommand completion (list, show, runs, full, stats,
#     synthesize, approve, reject, run, abort, clone, delete).
#   - Per-subcommand flag completion (--quiet is global, plus the
#     specific flags each subcommand accepts).
#   - Live plan_id completion sourced from
#     `python -m backend.core.planner.cli --quiet list` so you can
#     tab-complete actual plan ids that exist in the SQLite DB
#     pointed to by TARS_PLANNER_DB_PATH (or the default).
#
# The plan-id query is cached for 5 seconds inside the same shell
# session so back-to-back tabs do not re-shell into Python.

_TARS_PLANNER_CMDS="list show runs full stats synthesize approve reject run abort clone delete"

_TARS_PLANNER_GLOBAL_FLAGS="--quiet -h --help"

# Cache for plan ids: { value, expires_epoch }.
_TARS_PLANNER_CACHE_VAL=""
_TARS_PLANNER_CACHE_EXP=0

_tars_planner_plan_ids() {
    local now
    now=$(date +%s 2>/dev/null || printf 0)
    if [[ -n "$_TARS_PLANNER_CACHE_VAL" && "$now" -lt "$_TARS_PLANNER_CACHE_EXP" ]]; then
        printf '%s\n' "$_TARS_PLANNER_CACHE_VAL"
        return 0
    fi
    local raw
    # ``--quiet`` suppresses stderr noise; we ignore JSON parse
    # errors entirely (no plans / DB missing → empty completion
    # list, never a crash in the user's prompt).
    raw=$(python -m backend.core.planner.cli --quiet list 2>/dev/null \
        | python -c 'import json,sys
try:
    body = json.load(sys.stdin)
    plans = body.get("plans") or body.get("items") or []
    for p in plans:
        pid = p.get("id") if isinstance(p, dict) else None
        if pid:
            print(pid)
except Exception:
    pass' 2>/dev/null)
    _TARS_PLANNER_CACHE_VAL="$raw"
    _TARS_PLANNER_CACHE_EXP=$((now + 5))
    printf '%s\n' "$raw"
}

_tars_planner() {
    local cur prev words cword
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Walk left-to-right looking for the first non-flag word that
    # is one of our known subcommands.
    local i sub=""
    for ((i = 1; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        case " $_TARS_PLANNER_CMDS " in
            *" $w "*)
                sub="$w"
                break
                ;;
        esac
    done

    # Top-level: complete subcommands or the global --quiet flag.
    if [[ -z "$sub" ]]; then
        if [[ "$cur" == -* ]]; then
            COMPREPLY=( $(compgen -W "$_TARS_PLANNER_GLOBAL_FLAGS" -- "$cur") )
        else
            COMPREPLY=( $(compgen -W "$_TARS_PLANNER_CMDS" -- "$cur") )
        fi
        return 0
    fi

    # Per-subcommand flag tables. Kept in sync with cli.py's
    # _build_arg_parser.
    local flags=""
    case "$sub" in
        list)
            flags="--status --limit --thread-id"
            ;;
        synthesize)
            flags="--pinned-pack --thread-id"
            ;;
        run)
            flags="--mode"
            ;;
        clone)
            flags="--thread-id --goal --approve --run --mode"
            ;;
        delete)
            flags="--yes"
            ;;
        runs)
            flags="--limit"
            ;;
        full)
            flags="--limit"
            ;;
        show|approve|reject|abort|stats)
            flags=""
            ;;
    esac
    flags="$flags $_TARS_PLANNER_GLOBAL_FLAGS"

    # Value completion for flags that take an argument.
    case "$prev" in
        --status)
            COMPREPLY=( $(compgen -W "proposed approved rejected running completed aborted" -- "$cur") )
            return 0
            ;;
        --mode)
            COMPREPLY=( $(compgen -W "autopilot confirm dry_run" -- "$cur") )
            return 0
            ;;
        --limit|--thread-id|--pinned-pack|--goal)
            # Free-form value — let the shell fall through to file
            # completion (mostly useful for --goal copy-pastes).
            COMPREPLY=( $(compgen -- "$cur") )
            return 0
            ;;
    esac

    # If we are typing a flag, complete from the flag table.
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
        return 0
    fi

    # Subcommands that take a positional plan_id: complete from
    # the live plan list. ``synthesize`` takes a free-form goal,
    # ``stats``/``list`` take none.
    case "$sub" in
        show|runs|full|approve|reject|run|abort|clone|delete)
            local ids
            ids=$(_tars_planner_plan_ids)
            COMPREPLY=( $(compgen -W "$ids" -- "$cur") )
            return 0
            ;;
    esac

    return 0
}

complete -F _tars_planner -o default tars-planner 2>/dev/null
