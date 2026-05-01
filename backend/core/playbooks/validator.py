"""Playbook schema validator.

A separate module from :mod:`backend.core.playbooks.loader` because
the loader is purposefully lenient (accepts a dict and casts) — the
validator is *strict* and produces a structured list of issues so
operators authoring a custom playbook can fix every error in one
pass instead of bouncing on each load attempt.

The validator runs against the **JSON-shape** of a playbook (the
input to ``loader._from_dict``), not against the dataclass, so it
covers cases the dataclass would coerce away (numeric ids, mixed
list contents, unknown ``on_error`` values, etc.).

Issue model
-----------

Each violation is a :class:`Issue` with ``severity`` (``"error"`` |
``"warning"``), a ``code`` (machine-friendly slug), a ``path`` into
the JSON document (`steps[2].args.foo`), and a human ``message``.

A document with zero ``error``-level issues is :func:`Issue.is_valid`
even when it has warnings (e.g. unknown but non-destructive top-
level keys). Warnings are surfaced verbatim so the cockpit can
show them as "best-practice nits" without blocking the load.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


# ---------------------------------------------------------------------
# Allowed vocabulary
# ---------------------------------------------------------------------


# Action handler shape: <slug>.<action_id> OR
# <slug>.awareness.<source_id>.snapshot. Slugs are lowercase
# alphanumerics + underscores. Action ids use the same alphabet
# plus dots (sub-namespacing like ``pack.memory.set``).
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTION_ID_RE = re.compile(r"^[a-z][a-z0-9_.]*$")
_AWARENESS_SUFFIX = ".snapshot"

ALLOWED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "name",
        "description",
        "pack",
        "tags",
        "on_block",
        "steps",
    }
)
ALLOWED_STEP_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "action",
        "args",
        "store_as",
        "when",
        "on_error",
        "parallel",
    }
)
ALLOWED_ON_BLOCK: frozenset[str] = frozenset({"stop", "continue"})
ALLOWED_ON_ERROR: frozenset[str] = frozenset({"stop", "continue"})


# ---------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------


_ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_.-]*$", re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    severity: str  # "error" | "warning"
    code: str
    path: str  # JSON-like path: "steps[2].args.foo"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a validation pass.

    ``ok`` is True iff there are zero ``error``-level issues; warnings
    do not invalidate the playbook.
    """

    ok: bool
    issues: tuple[Issue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
            "issue_count": len(self.issues),
        }


# ---------------------------------------------------------------------
# Validator core
# ---------------------------------------------------------------------


class _Builder:
    """Accumulates issues during a single validation pass."""

    def __init__(self) -> None:
        self._items: list[Issue] = []

    def err(self, code: str, path: str, message: str) -> None:
        self._items.append(Issue("error", code, path, message))

    def warn(self, code: str, path: str, message: str) -> None:
        self._items.append(Issue("warning", code, path, message))

    @property
    def issues(self) -> tuple[Issue, ...]:
        return tuple(self._items)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self._items)


def validate_playbook(blob: Any) -> ValidationResult:
    """Validate the JSON-shape of a single playbook.

    Returns a :class:`ValidationResult` even on totally malformed
    input — the validator never raises.
    """

    b = _Builder()

    if not isinstance(blob, Mapping):
        b.err(
            "playbook_must_be_object",
            "$",
            f"playbook root must be a JSON object, got {_typename(blob)}",
        )
        return ValidationResult(ok=False, issues=b.issues)

    _validate_top_level(blob, b)
    _validate_steps(blob.get("steps"), b)

    return ValidationResult(ok=not b.has_errors, issues=b.issues)


def validate_payload(blob: Any) -> ValidationResult:
    """Convenience alias used by the HTTP layer (any future
    rename only touches one site)."""

    return validate_playbook(blob)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _typename(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _validate_top_level(blob: Mapping[str, Any], b: _Builder) -> None:
    pid = blob.get("id")
    if pid is None or not isinstance(pid, str) or not pid.strip():
        b.err(
            "id_required",
            "$.id",
            "playbook must have a non-empty `id` string",
        )
    elif not _ID_RE.match(pid):
        b.err(
            "id_invalid_chars",
            "$.id",
            f"id {pid!r} must match [A-Za-z0-9_.-]+",
        )

    name = blob.get("name")
    if name is not None and not isinstance(name, str):
        b.err(
            "name_must_be_string",
            "$.name",
            f"name must be a string, got {_typename(name)}",
        )

    desc = blob.get("description")
    if desc is not None and not isinstance(desc, str):
        b.err(
            "description_must_be_string",
            "$.description",
            f"description must be a string, got {_typename(desc)}",
        )

    pack = blob.get("pack")
    if pack is not None:
        if not isinstance(pack, str) or not pack.strip():
            b.err(
                "pack_must_be_nonempty_string",
                "$.pack",
                "pack must be a non-empty string when present",
            )
        elif not _SLUG_RE.match(pack):
            b.err(
                "pack_invalid_slug",
                "$.pack",
                f"pack {pack!r} must be a lowercase slug (a-z0-9_)",
            )

    tags = blob.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            b.err(
                "tags_must_be_array",
                "$.tags",
                f"tags must be an array, got {_typename(tags)}",
            )
        else:
            for i, t in enumerate(tags):
                if not isinstance(t, str) or not t.strip():
                    b.err(
                        "tag_must_be_nonempty_string",
                        f"$.tags[{i}]",
                        "each tag must be a non-empty string",
                    )

    on_block = blob.get("on_block")
    if on_block is not None and on_block not in ALLOWED_ON_BLOCK:
        b.err(
            "on_block_invalid",
            "$.on_block",
            f"on_block must be one of {sorted(ALLOWED_ON_BLOCK)}, "
            f"got {on_block!r}",
        )

    for key in blob.keys():
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            b.warn(
                "unknown_top_level_key",
                f"$.{key}",
                f"unknown top-level key {key!r} (allowed: "
                f"{sorted(ALLOWED_TOP_LEVEL_KEYS)})",
            )


def _validate_steps(steps: Any, b: _Builder) -> None:
    if steps is None:
        b.err(
            "steps_required",
            "$.steps",
            "playbook must declare at least one step",
        )
        return
    if not isinstance(steps, list):
        b.err(
            "steps_must_be_array",
            "$.steps",
            f"steps must be an array, got {_typename(steps)}",
        )
        return
    if not steps:
        b.err(
            "steps_empty",
            "$.steps",
            "playbook must declare at least one step",
        )
        return

    seen_ids: dict[str, int] = {}
    for idx, raw in enumerate(steps):
        path = f"$.steps[{idx}]"
        if not isinstance(raw, Mapping):
            b.err(
                "step_must_be_object",
                path,
                f"step #{idx} must be a JSON object, got "
                f"{_typename(raw)}",
            )
            continue

        sid = raw.get("id")
        if sid is None or not isinstance(sid, str) or not sid.strip():
            b.err(
                "step_id_required",
                f"{path}.id",
                f"step #{idx} must have a non-empty `id` string",
            )
        elif not _ID_RE.match(sid):
            b.err(
                "step_id_invalid_chars",
                f"{path}.id",
                f"step id {sid!r} must match [A-Za-z0-9_.-]+",
            )
        elif sid in seen_ids:
            b.err(
                "step_id_duplicate",
                f"{path}.id",
                f"step id {sid!r} duplicates an earlier step at "
                f"steps[{seen_ids[sid]}]",
            )
        else:
            seen_ids[sid] = idx

        action = raw.get("action")
        if action is None or not isinstance(action, str) or not action.strip():
            b.err(
                "action_required",
                f"{path}.action",
                f"step #{idx} must have a non-empty `action` string",
            )
        else:
            _validate_action_target(action, f"{path}.action", b)

        args = raw.get("args")
        if args is not None and not isinstance(args, (Mapping, list, str)):
            b.err(
                "args_invalid_type",
                f"{path}.args",
                f"args must be an object/array/string, got "
                f"{_typename(args)}",
            )

        store_as = raw.get("store_as")
        if store_as is not None:
            if not isinstance(store_as, str) or not store_as.strip():
                b.err(
                    "store_as_must_be_nonempty_string",
                    f"{path}.store_as",
                    "store_as must be a non-empty string when present",
                )
            elif not _ID_RE.match(store_as):
                b.err(
                    "store_as_invalid_chars",
                    f"{path}.store_as",
                    f"store_as {store_as!r} must match [A-Za-z0-9_.-]+",
                )

        when = raw.get("when")
        if when is not None and not isinstance(when, str):
            b.err(
                "when_must_be_string",
                f"{path}.when",
                f"when must be a string expression, got "
                f"{_typename(when)}",
            )

        on_error = raw.get("on_error")
        if on_error is not None and on_error not in ALLOWED_ON_ERROR:
            b.err(
                "on_error_invalid",
                f"{path}.on_error",
                f"on_error must be one of {sorted(ALLOWED_ON_ERROR)}, "
                f"got {on_error!r}",
            )

        parallel = raw.get("parallel")
        if parallel is not None and not isinstance(parallel, bool):
            b.err(
                "parallel_must_be_bool",
                f"{path}.parallel",
                f"parallel must be a boolean, got {_typename(parallel)}",
            )

        for key in raw.keys():
            if key not in ALLOWED_STEP_KEYS:
                b.warn(
                    "unknown_step_key",
                    f"{path}.{key}",
                    f"unknown step key {key!r} on step #{idx} "
                    f"(allowed: {sorted(ALLOWED_STEP_KEYS)})",
                )

    # First step cannot be "parallel" — the runner batches a parallel
    # step with the *previous* sibling, so a leading parallel is
    # always a no-op authoring mistake.
    if steps and isinstance(steps[0], Mapping) and bool(steps[0].get("parallel")):
        b.warn(
            "leading_parallel_no_op",
            "$.steps[0].parallel",
            "first step has parallel=true, which has no sibling to "
            "batch with (the runner will execute it sequentially)",
        )

    # Cross-step ${steps.<id>...} references that point at non-
    # existent step ids are a frequent typo source. Surface as
    # warnings (the runner already handles missing context paths
    # by yielding None — but the cockpit should flag them).
    _validate_template_references(steps, seen_ids, b)


def _validate_action_target(action: str, path: str, b: _Builder) -> None:
    """Validate the ``<slug>.<action_id>`` or
    ``<slug>.awareness.<source_id>.snapshot`` shape.
    """

    if action.endswith(_AWARENESS_SUFFIX):
        # awareness.<source_id>.snapshot → at least 4 dotted parts.
        parts = action.split(".")
        if len(parts) < 4 or parts[1] != "awareness" or parts[-1] != "snapshot":
            b.err(
                "action_awareness_malformed",
                path,
                "awareness target must be "
                "`<slug>.awareness.<source_id>.snapshot`, "
                f"got {action!r}",
            )
            return
        slug, source_id = parts[0], ".".join(parts[2:-1])
        if not _SLUG_RE.match(slug):
            b.err(
                "action_slug_invalid",
                path,
                f"awareness slug {slug!r} must be lowercase a-z0-9_",
            )
        if not source_id or not _ACTION_ID_RE.match(source_id):
            b.err(
                "action_source_id_invalid",
                path,
                f"awareness source id {source_id!r} must match "
                "[a-z][a-z0-9_.]*",
            )
        return

    if "." not in action:
        b.err(
            "action_malformed",
            path,
            f"action {action!r} must be `<slug>.<action_id>` or "
            "`<slug>.awareness.<source>.snapshot`",
        )
        return
    slug, _, action_id = action.partition(".")
    if not slug or not _SLUG_RE.match(slug):
        b.err(
            "action_slug_invalid",
            path,
            f"action slug {slug!r} must be lowercase a-z0-9_",
        )
    if not action_id or not _ACTION_ID_RE.match(action_id):
        b.err(
            "action_id_invalid",
            path,
            f"action id {action_id!r} must match [a-z][a-z0-9_.]*",
        )


_TEMPLATE_REF_RE = re.compile(r"\$\{steps\.([A-Za-z0-9_.-]+)")


def _validate_template_references(
    steps: list[Any],
    seen_ids: Mapping[str, int],
    b: _Builder,
) -> None:
    for idx, raw in enumerate(steps):
        if not isinstance(raw, Mapping):
            continue
        sid = raw.get("id")
        if not isinstance(sid, str):
            sid = f"#{idx}"

        for key in ("when", "args"):
            value = raw.get(key)
            for ref in _gather_step_references(value):
                head = ref.split(".", 1)[0]
                if head not in seen_ids:
                    b.warn(
                        "step_ref_unknown",
                        f"$.steps[{idx}].{key}",
                        f"step {sid!r} references "
                        f"${{steps.{ref}...}} but no step with id "
                        f"{head!r} is declared above it",
                    )
                    continue
                if seen_ids[head] >= idx:
                    # Forward reference (step references itself or
                    # a later sibling). Forward refs only resolve
                    # via parallel batching so we surface as a
                    # warning when the referenced step is later in
                    # the document.
                    if seen_ids[head] != idx:
                        b.warn(
                            "step_ref_forward",
                            f"$.steps[{idx}].{key}",
                            f"step {sid!r} references "
                            f"${{steps.{head}...}} which is declared "
                            "later — value will be unset at run time",
                        )


def _gather_step_references(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        for m in _TEMPLATE_REF_RE.finditer(value):
            yield m.group(1)
        return
    if isinstance(value, Mapping):
        for v in value.values():
            yield from _gather_step_references(v)
        return
    if isinstance(value, list):
        for v in value:
            yield from _gather_step_references(v)
