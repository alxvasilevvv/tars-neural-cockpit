#!/usr/bin/env bash
# Bash completion for the TARS awareness CLI.
#
# Install (one of):
#
#   # ad-hoc, current shell only
#   source scripts/awareness-completion.bash
#
#   # persistent (Linux)
#   sudo cp scripts/awareness-completion.bash /etc/bash_completion.d/tars-awareness
#
#   # persistent (macOS, with homebrew bash-completion@2)
#   cp scripts/awareness-completion.bash \
#       "$(brew --prefix)/etc/bash_completion.d/tars-awareness"
#
# Then alias the long invocation if you have not already:
#
#   alias tars-awareness='python -m backend.core.domains.awareness_cli'
#   complete -F _tars_awareness tars-awareness
#
# Provides:
#   - Subcommand completion (list, snapshot, snapshot-all).
#   - Per-subcommand flag completion (--quiet is global, plus
#     --thread-id / --trace-id on the snapshot subcommands).
#   - Live pack-slug completion sourced from
#     `python -m backend.core.domains.awareness_cli --quiet list`
#     so you can tab-complete the slugs that actually exist in
#     the registered domain packs.
#   - Live source-id completion (per-pack) for ``snapshot``'s
#     second positional, sourced from the same CLI by listing
#     the chosen pack.
#
# Both id queries are cached for 5 seconds inside the same shell
# session so back-to-back tabs do not re-shell into Python.
# Cache is keyed by query type (slug list vs per-pack source
# list) so completing slug A then slug B doesn't pollute B's
# cache with A's source ids.

_TARS_AWARENESS_CMDS="list snapshot snapshot-all"

_TARS_AWARENESS_GLOBAL_FLAGS="--quiet -h --help"

# Cache for pack slugs.
_TARS_AWARENESS_SLUGS_VAL=""
_TARS_AWARENESS_SLUGS_EXP=0

# Cache for per-pack source ids: the cache key is the slug name,
# stored alongside the value so we re-query when the slug changes.
_TARS_AWARENESS_SOURCES_KEY=""
_TARS_AWARENESS_SOURCES_VAL=""
_TARS_AWARENESS_SOURCES_EXP=0

_tars_awareness_slugs() {
    local now
    now=$(date +%s 2>/dev/null || printf 0)
    if [[ -n "$_TARS_AWARENESS_SLUGS_VAL" && "$now" -lt "$_TARS_AWARENESS_SLUGS_EXP" ]]; then
        printf '%s\n' "$_TARS_AWARENESS_SLUGS_VAL"
        return 0
    fi
    local raw
    # ``--quiet`` (global flag) suppresses the indented JSON; we
    # ignore parse errors entirely (no packs / module missing →
    # empty completion list, never a crash in the user's prompt).
    # NOTE: --quiet must precede the subcommand; see the planner
    # / playbooks completion bug fixed in PR #130.
    raw=$(python -m backend.core.domains.awareness_cli --quiet list 2>/dev/null \
        | python -c 'import json,sys
try:
    body = json.load(sys.stdin)
    rows = body.get("packs") or []
    for p in rows:
        slug = p.get("slug") if isinstance(p, dict) else None
        if slug:
            print(slug)
except Exception:
    pass' 2>/dev/null)
    _TARS_AWARENESS_SLUGS_VAL="$raw"
    _TARS_AWARENESS_SLUGS_EXP=$((now + 5))
    printf '%s\n' "$raw"
}

_tars_awareness_sources() {
    local slug="$1"
    if [[ -z "$slug" ]]; then
        return 0
    fi
    local now
    now=$(date +%s 2>/dev/null || printf 0)
    if [[ "$_TARS_AWARENESS_SOURCES_KEY" == "$slug" \
        && -n "$_TARS_AWARENESS_SOURCES_VAL" \
        && "$now" -lt "$_TARS_AWARENESS_SOURCES_EXP" ]]; then
        printf '%s\n' "$_TARS_AWARENESS_SOURCES_VAL"
        return 0
    fi
    local raw
    raw=$(python -m backend.core.domains.awareness_cli --quiet list "$slug" 2>/dev/null \
        | python -c 'import json,sys
try:
    body = json.load(sys.stdin)
    rows = body.get("awareness") or []
    for s in rows:
        sid = s.get("id") if isinstance(s, dict) else None
        if sid:
            print(sid)
except Exception:
    pass' 2>/dev/null)
    _TARS_AWARENESS_SOURCES_KEY="$slug"
    _TARS_AWARENESS_SOURCES_VAL="$raw"
    _TARS_AWARENESS_SOURCES_EXP=$((now + 5))
    printf '%s\n' "$raw"
}

_tars_awareness() {
    local cur prev words cword
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Walk left-to-right looking for the first non-flag word that
    # is one of our known subcommands.
    local i sub=""
    for ((i = 1; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        case " $_TARS_AWARENESS_CMDS " in
            *" $w "*)
                sub="$w"
                break
                ;;
        esac
    done

    # Top-level: complete subcommands or the global --quiet flag.
    if [[ -z "$sub" ]]; then
        if [[ "$cur" == -* ]]; then
            COMPREPLY=( $(compgen -W "$_TARS_AWARENESS_GLOBAL_FLAGS" -- "$cur") )
        else
            COMPREPLY=( $(compgen -W "$_TARS_AWARENESS_CMDS" -- "$cur") )
        fi
        return 0
    fi

    # Per-subcommand flag tables. Kept in sync with cli.py's
    # _build_arg_parser.
    local flags=""
    case "$sub" in
        list)
            flags=""
            ;;
        snapshot|snapshot-all)
            flags="--thread-id --trace-id"
            ;;
    esac
    flags="$flags $_TARS_AWARENESS_GLOBAL_FLAGS"

    # Value completion for flags that take an argument.
    case "$prev" in
        --thread-id|--trace-id)
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

    # Positional completion is subcommand-specific:
    #   - list:          one optional positional (<slug>).
    #   - snapshot-all:  one positional (<slug>).
    #   - snapshot:      two positionals (<slug> <source_id>).
    #
    # We count non-flag positional words AFTER the subcommand to
    # decide which positional we are currently at. This keeps the
    # flag flexibility intact (--quiet can appear anywhere).
    local positional_idx=0
    local seen_sub=0
    local positionals=()
    for ((i = 1; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        if [[ $seen_sub -eq 0 ]]; then
            if [[ "$w" == "$sub" ]]; then
                seen_sub=1
            fi
            continue
        fi
        # Skip flags and their values.
        if [[ "$w" == -* ]]; then
            # If this flag takes a value, skip the next word too.
            case "$w" in
                --thread-id|--trace-id)
                    ((i++))
                    ;;
            esac
            continue
        fi
        positionals+=("$w")
    done
    positional_idx=${#positionals[@]}

    case "$sub" in
        list|snapshot-all)
            if [[ $positional_idx -eq 0 ]]; then
                local slugs
                slugs=$(_tars_awareness_slugs)
                COMPREPLY=( $(compgen -W "$slugs" -- "$cur") )
            fi
            return 0
            ;;
        snapshot)
            if [[ $positional_idx -eq 0 ]]; then
                local slugs
                slugs=$(_tars_awareness_slugs)
                COMPREPLY=( $(compgen -W "$slugs" -- "$cur") )
            elif [[ $positional_idx -eq 1 ]]; then
                # Source-id completion is per-pack — feed the
                # already-typed slug into the per-pack source query.
                local slug="${positionals[0]}"
                local sources
                sources=$(_tars_awareness_sources "$slug")
                COMPREPLY=( $(compgen -W "$sources" -- "$cur") )
            fi
            return 0
            ;;
    esac

    return 0
}

complete -F _tars_awareness -o default tars-awareness 2>/dev/null
