#!/usr/bin/env bash
# Bash completion for the TARS playbooks CLI.
#
# Install (one of):
#
#   # ad-hoc, current shell only
#   source scripts/playbooks-completion.bash
#
#   # persistent (Linux)
#   sudo cp scripts/playbooks-completion.bash /etc/bash_completion.d/tars-playbooks
#
#   # persistent (macOS, with homebrew bash-completion@2)
#   cp scripts/playbooks-completion.bash \
#       "$(brew --prefix)/etc/bash_completion.d/tars-playbooks"
#
# Then alias the long invocation if you have not already:
#
#   alias tars-playbooks='python -m backend.core.playbooks.cli'
#   complete -F _tars_playbooks tars-playbooks
#
# Provides:
#   - Subcommand completion (list, show, run, validate,
#     validate-all, reload).
#   - Per-subcommand flag completion (--quiet is global, plus the
#     specific flags each subcommand accepts).
#   - Live playbook_id completion sourced from
#     `python -m backend.core.playbooks.cli --quiet list` so you can
#     tab-complete actual playbook ids that exist in the
#     ``$TARS_PLAYBOOKS_DIR`` (or the default ``playbooks/`` tree).
#   - Path completion for ``--context-file``.
#
# The playbook-id query is cached for 5 seconds inside the same
# shell session so back-to-back tabs do not re-shell into Python.

_TARS_PLAYBOOKS_CMDS="list show run validate validate-all reload"

_TARS_PLAYBOOKS_GLOBAL_FLAGS="--quiet -h --help"

# Cache for playbook ids: { value, expires_epoch }.
_TARS_PLAYBOOKS_CACHE_VAL=""
_TARS_PLAYBOOKS_CACHE_EXP=0

_tars_playbooks_ids() {
    local now
    now=$(date +%s 2>/dev/null || printf 0)
    if [[ -n "$_TARS_PLAYBOOKS_CACHE_VAL" && "$now" -lt "$_TARS_PLAYBOOKS_CACHE_EXP" ]]; then
        printf '%s\n' "$_TARS_PLAYBOOKS_CACHE_VAL"
        return 0
    fi
    local raw
    # ``--quiet`` suppresses stderr noise; we ignore JSON parse
    # errors entirely (no playbooks / dir missing → empty
    # completion list, never a crash in the user's prompt).
    raw=$(python -m backend.core.playbooks.cli --quiet list 2>/dev/null \
        | python -c 'import json,sys
try:
    body = json.load(sys.stdin)
    rows = body.get("playbooks") or body.get("items") or []
    for p in rows:
        pid = p.get("id") if isinstance(p, dict) else None
        if pid:
            print(pid)
except Exception:
    pass' 2>/dev/null)
    _TARS_PLAYBOOKS_CACHE_VAL="$raw"
    _TARS_PLAYBOOKS_CACHE_EXP=$((now + 5))
    printf '%s\n' "$raw"
}

_tars_playbooks() {
    local cur prev words cword
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Walk left-to-right looking for the first non-flag word that
    # is one of our known subcommands. ``validate-all`` contains a
    # hyphen so the standard word-split inside ``case`` still works
    # because COMP_WORDS already keeps it as a single token.
    local i sub=""
    for ((i = 1; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        case " $_TARS_PLAYBOOKS_CMDS " in
            *" $w "*)
                sub="$w"
                break
                ;;
        esac
    done

    # Top-level: complete subcommands or the global --quiet flag.
    if [[ -z "$sub" ]]; then
        if [[ "$cur" == -* ]]; then
            COMPREPLY=( $(compgen -W "$_TARS_PLAYBOOKS_GLOBAL_FLAGS" -- "$cur") )
        else
            COMPREPLY=( $(compgen -W "$_TARS_PLAYBOOKS_CMDS" -- "$cur") )
        fi
        return 0
    fi

    # Per-subcommand flag tables. Kept in sync with cli.py's
    # _build_arg_parser.
    local flags=""
    case "$sub" in
        list)
            flags="--pack --refresh"
            ;;
        show)
            flags="--refresh"
            ;;
        run)
            flags="--mode --context --context-file --thread-id --trace-id"
            ;;
        validate|validate-all|reload)
            flags=""
            ;;
    esac
    flags="$flags $_TARS_PLAYBOOKS_GLOBAL_FLAGS"

    # Value completion for flags that take an argument.
    case "$prev" in
        --mode)
            COMPREPLY=( $(compgen -W "autopilot confirm dry_run" -- "$cur") )
            return 0
            ;;
        --context-file)
            # File path completion is the canonical use case
            # (cron-baked sidecar JSON). Use the default
            # filename completer so paths with spaces / globs
            # behave the same as in plain bash.
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --pack|--thread-id|--trace-id|--context)
            # Free-form value — let the shell fall through to
            # default completion.
            COMPREPLY=( $(compgen -- "$cur") )
            return 0
            ;;
    esac

    # If we are typing a flag, complete from the flag table.
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
        return 0
    fi

    # Subcommands that take a positional playbook_id: complete
    # from the live playbook list. ``list`` / ``validate-all`` /
    # ``reload`` take no positionals.
    case "$sub" in
        show|run|validate)
            local ids
            ids=$(_tars_playbooks_ids)
            COMPREPLY=( $(compgen -W "$ids" -- "$cur") )
            return 0
            ;;
    esac

    return 0
}

complete -F _tars_playbooks -o default tars-playbooks 2>/dev/null
