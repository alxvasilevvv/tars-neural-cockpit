"""Overlay synthesis for custom roles.

The cockpit's "Custom" role asks the operator for a name + a free-form
description ("I'm a clinical psychologist running a private practice
solo, scheduling matters, intake forms, ethical guardrails matter").
We turn that into a deterministic system-prompt fragment that the
orchestrator can prepend.

We deliberately do NOT call out to a remote LLM here — synthesis is
local + deterministic so:

1. The first turn fires immediately (no extra round-trip).
2. The role overlay is reproducible from the same inputs (operators
   can rotate their TARS install and get the same behaviour).
3. The overlay is auditable — operators can read exactly what the
   assistant is told.

A future revision can opt into LLM synthesis behind a feature flag,
but the launch shape is deterministic.
"""

from __future__ import annotations

import hashlib
import re
import textwrap
from typing import Iterable


_DEFAULT_BACKING_PACKS: tuple[str, ...] = ()


def synthesise_overlay(
    *,
    name: str,
    description: str,
    backing_packs: Iterable[str] = _DEFAULT_BACKING_PACKS,
    samples: Iterable[str] | None = None,
) -> str:
    """Produce a TARS-shaped system-prompt overlay.

    The overlay always:
    - Names the role and how the operator self-identifies.
    - Anchors the operator's *priorities* extracted from the description.
    - Lists the backing packs so the assistant knows what tools to
      reach for first.
    - Echoes the operator's voice with up to 3 sample sentences when
      provided.
    """

    name_clean = (name or "operator").strip() or "operator"
    desc_clean = (description or "").strip()
    packs_list = [p for p in backing_packs if p]

    priority_lines = _extract_priority_bullets(desc_clean)
    samples_list = list(samples or [])[:3]

    overlay_parts: list[str] = []
    overlay_parts.append(
        f"You are TARS in the **{name_clean}** role for this operator."
    )
    if desc_clean:
        # Cap description at 600 chars so a verbose intake form doesn't
        # blow the token budget.
        clipped = (desc_clean[:600] + "…") if len(desc_clean) > 600 else desc_clean
        overlay_parts.append(f"Operator self-description:\n{clipped}")

    if priority_lines:
        overlay_parts.append("Priorities (in order):")
        overlay_parts.extend(f"- {line}" for line in priority_lines)

    if packs_list:
        overlay_parts.append(
            "Backing toolset (reach for these first when the operator's "
            "request implies a domain): "
            + ", ".join(packs_list)
            + "."
        )

    if samples_list:
        overlay_parts.append("Voice samples to mirror (style only — never "
                             "fabricate content from these):")
        for s in samples_list:
            line = " ".join(s.split())
            if len(line) > 200:
                line = line[:200] + "…"
            overlay_parts.append(f"> {line}")

    overlay_parts.append(textwrap.dedent("""\
        Always:
        - Treat the operator as the principal; never address an audience.
        - Be specific. Numbers, names, and dates beat adjectives.
        - When unsure, ask one focused question, not three.
        - Refuse anything that violates the operator's stated ethics
          or local law. Do not improvise consent.
        - Surface tradeoffs explicitly — don't hide cost behind upside.
    """).strip())

    overlay_parts.append(
        f"role_signature={_signature(name_clean, desc_clean, packs_list)}"
    )

    return "\n\n".join(overlay_parts).strip()


_PRIORITY_HINTS = re.compile(
    r"(?P<priority>"
    r"(?:i|we) (?:value|prioritise|prioritize|focus on|need to|want to|always|never|won't)\s+[^.;\n]+"
    r"|"
    r"matter[s]? (?:most|to me|to us)\s*[:\-]?\s*[^.;\n]+"
    r"|"
    r"(?:must|should|cannot)\s+[^.;\n]+"
    r")",
    re.IGNORECASE,
)


def _extract_priority_bullets(text: str) -> list[str]:
    """Pull at most 5 priority-style sentences out of free-form text.

    Heuristic, not perfect — but deterministic and good enough for
    a first-launch overlay. Custom roles can be edited by the operator
    afterwards.
    """

    if not text:
        return []
    # First pass: capture explicit hints.
    matches = [m.group("priority").strip() for m in _PRIORITY_HINTS.finditer(text)]
    out: list[str] = []
    seen: set[str] = set()
    for m in matches:
        norm = " ".join(m.split())
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
        if len(out) >= 5:
            break

    # Fallback: if no explicit hints, take the first 1-2 sentences as
    # priorities so the overlay isn't naked.
    if not out:
        first = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=2)
        out = [s.strip() for s in first[:2] if s.strip()]
    return out


def _signature(name: str, description: str, packs: list[str]) -> str:
    """Deterministic 12-char fingerprint, useful for audit / cache keys."""

    blob = "|".join([name.lower(), description.lower(), ",".join(sorted(packs))])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
