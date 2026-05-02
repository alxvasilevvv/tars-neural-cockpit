"""Deterministic plan synthesizer.

V1 maps a free-form goal onto either an existing registered playbook
(if the goal mentions one by name / id) or a single-action fallback
(if the goal mentions a known pack action). Cloud LLM planning is
reserved for a follow-up PR — this v1 stays stdlib-only and 100%
reproducible so the planner stack can be tested without network.

Order of resolution (first match wins):

1. Explicit playbook match: any token in the goal that case-
   insensitively matches a playbook id, name, or one of its tags.
2. Explicit action match: any ``pack.action`` substring in the goal.
3. Single-action fallback: if the goal contains a single registered
   pack slug, propose a single non-destructive *snapshot* action
   from that pack (typically the pack's primary awareness source).
4. Otherwise raise :class:`PlannerError` (``no_match`` reason).

The synthesizer never executes any action — it only proposes the
plan. The runner (follow-up PR) takes the persisted plan and feeds
it to ``PlaybookRunner``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from .types import Plan, PlanStatus, PlanStep


class PlannerError(Exception):
    """Raised when the synthesizer cannot map a goal to a plan."""

    def __init__(self, reason: str, *, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


@dataclass(frozen=True)
class PlannerSynthesisRequest:
    """Inputs for :func:`synthesize_plan`.

    Kept as a dataclass so the HTTP layer can build it from the
    request body and the planner module can grow new optional inputs
    (e.g. ``pinned_pack``) without changing the function signature.
    """

    goal: str
    thread_id: Optional[str] = None
    trace_id: Optional[str] = None
    pinned_pack: Optional[str] = None  # restrict resolution to this pack
    available_playbooks: tuple = ()  # tuple[backend.core.playbooks.Playbook]
    available_actions: tuple = ()  # tuple[(slug, action_id, destructive, snapshot?)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+(?:[._-][A-Za-z0-9_]+)*")


def _tokenize(text: str) -> list[str]:
    """Lowercased token list extracted from free-form text.

    Tokens may contain ``.``, ``_`` and ``-`` so identifiers like
    ``traders.morning_check`` survive intact.
    """

    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _match_playbook(goal: str, playbooks: Sequence) -> Optional[object]:
    """First playbook whose id / name / tag appears in the goal."""

    if not playbooks:
        return None
    tokens = set(_tokenize(goal))
    norm_goal = (goal or "").lower()
    # Pass 1: exact id match (most specific signal).
    for pb in playbooks:
        pb_id = (getattr(pb, "id", "") or "").lower()
        if pb_id and pb_id in norm_goal:
            return pb
    # Pass 2: name substring match.
    for pb in playbooks:
        pb_name = (getattr(pb, "name", "") or "").lower()
        if pb_name and pb_name in norm_goal:
            return pb
    # Pass 3: tag-token match (any tag word among the tokens).
    for pb in playbooks:
        pb_tags = {str(t).lower() for t in (getattr(pb, "tags", ()) or ())}
        if pb_tags & tokens:
            return pb
    return None


def _match_action(
    goal: str, actions: Sequence[tuple[str, str, bool, bool]]
) -> Optional[tuple[str, str, bool, bool]]:
    """First ``(slug, action_id, destructive, is_snapshot)`` whose
    ``slug.action_id`` substring appears in the goal."""

    if not actions:
        return None
    norm = (goal or "").lower()
    # Most-specific-first: longer ids match before ambiguous prefixes.
    sorted_actions = sorted(
        actions, key=lambda r: -(len(r[0]) + len(r[1]))
    )
    for slug, action_id, destructive, is_snapshot in sorted_actions:
        needle = f"{slug}.{action_id}".lower()
        if needle in norm:
            return slug, action_id, destructive, is_snapshot
    return None


def _packs_in_goal(
    goal: str, actions: Sequence[tuple[str, str, bool, bool]]
) -> list[str]:
    """Distinct pack slugs whose name appears as a token in ``goal``."""

    if not actions:
        return []
    tokens = set(_tokenize(goal))
    seen: list[str] = []
    seen_set: set[str] = set()
    for slug, _action, _destr, _snap in actions:
        slug_l = slug.lower()
        if slug_l in tokens and slug_l not in seen_set:
            seen.append(slug)
            seen_set.add(slug_l)
    return seen


def _playbook_to_steps(playbook: object) -> tuple[PlanStep, ...]:
    """Convert a registered playbook's steps into PlanStep entries.

    The Plan retains the playbook's ordering, ``store_as`` /
    ``when`` clauses, ``on_error`` semantics, and ``parallel`` flag
    so the runner can replay it 1:1.
    """

    out: list[PlanStep] = []
    for step in getattr(playbook, "steps", ()):
        out.append(
            PlanStep(
                id=str(getattr(step, "id", "")),
                action=str(getattr(step, "action", "")),
                args=dict(getattr(step, "args", {}) or {}),
                store_as=getattr(step, "store_as", None),
                when=getattr(step, "when", None),
                on_error=str(getattr(step, "on_error", "stop")),
                parallel=bool(getattr(step, "parallel", False)),
                rationale=(
                    f"From playbook {getattr(playbook, 'id', '')!r}"
                ),
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def synthesize_plan(req: PlannerSynthesisRequest) -> Plan:
    """Map a free-form goal to a structured Plan.

    Raises :class:`PlannerError` with stable reason codes
    (``empty_goal`` / ``no_match`` / ``ambiguous_packs`` / ``unknown_pack``)
    so callers can render the right error envelope without parsing
    English.
    """

    goal = (req.goal or "").strip()
    if not goal:
        raise PlannerError("empty_goal", message="goal is required")

    # 1. Explicit playbook match.
    candidates = req.available_playbooks
    if req.pinned_pack:
        candidates = tuple(
            pb
            for pb in candidates
            if (getattr(pb, "pack", None) or "").lower()
            == req.pinned_pack.lower()
        )
    matched_pb = _match_playbook(goal, candidates)
    if matched_pb is not None:
        steps = _playbook_to_steps(matched_pb)
        return Plan(
            id="",
            goal=goal,
            steps=steps,
            status=PlanStatus.PROPOSED,
            rationale=(
                f"Matched playbook {getattr(matched_pb, 'id', '')!r} from "
                f"the goal text."
            ),
            model="heuristic-v1",
            pack_slug=getattr(matched_pb, "pack", None),
            playbook_id=getattr(matched_pb, "id", None),
            thread_id=req.thread_id,
            trace_id=req.trace_id,
        )

    # 2. Explicit action match.
    actions = req.available_actions
    if req.pinned_pack:
        actions = tuple(
            (s, a, d, snap)
            for (s, a, d, snap) in actions
            if s.lower() == req.pinned_pack.lower()
        )
    matched_action = _match_action(goal, actions)
    if matched_action is not None:
        slug, action_id, destructive, _snap = matched_action
        return Plan(
            id="",
            goal=goal,
            steps=(
                PlanStep(
                    id="step-1",
                    action=f"{slug}.{action_id}",
                    args={},
                    store_as=action_id,
                    on_error="stop",
                    rationale=(
                        f"Direct call to {slug}.{action_id} matched the goal "
                        "verbatim."
                    ),
                    destructive=destructive,
                ),
            ),
            status=PlanStatus.PROPOSED,
            rationale=(
                f"Single-action plan: {slug}.{action_id}."
            ),
            model="heuristic-v1",
            pack_slug=slug,
            thread_id=req.thread_id,
            trace_id=req.trace_id,
        )

    # 3. Single-pack fallback: propose a non-destructive snapshot action.
    if req.pinned_pack:
        pack_candidates = [req.pinned_pack]
    else:
        pack_candidates = _packs_in_goal(goal, actions)
    if len(pack_candidates) > 1:
        raise PlannerError(
            "ambiguous_packs",
            message=(
                "goal mentions multiple packs ("
                + ", ".join(pack_candidates)
                + "); pin one with `pinned_pack` and retry"
            ),
        )
    if len(pack_candidates) == 1:
        slug = pack_candidates[0]
        # First non-destructive snapshot action under that pack.
        snap = next(
            (
                (s, a, d, snap)
                for (s, a, d, snap) in actions
                if s == slug and snap and not d
            ),
            None,
        )
        if snap is not None:
            slug, action_id, destructive, _ = snap
            return Plan(
                id="",
                goal=goal,
                steps=(
                    PlanStep(
                        id="step-1",
                        action=f"{slug}.{action_id}",
                        args={},
                        store_as=action_id,
                        on_error="stop",
                        rationale=(
                            f"No specific action requested; defaulting to a "
                            f"non-destructive snapshot action under "
                            f"{slug!r}."
                        ),
                        destructive=destructive,
                    ),
                ),
                status=PlanStatus.PROPOSED,
                rationale=(
                    f"Pack-only goal: defaulted to a snapshot under "
                    f"{slug!r}."
                ),
                model="heuristic-v1",
                pack_slug=slug,
                thread_id=req.thread_id,
                trace_id=req.trace_id,
            )
        # No snapshot action available for this pack.
        raise PlannerError(
            "unknown_pack",
            message=(
                f"pack {slug!r} has no snapshot action to default to; "
                "name a specific action in your goal"
            ),
        )

    raise PlannerError(
        "no_match",
        message=(
            "goal did not match any registered playbook, action, or pack; "
            "name an action explicitly (e.g. `traders.summarize_market`) "
            "or run a registered playbook (e.g. `traders.morning_check`)"
        ),
    )
