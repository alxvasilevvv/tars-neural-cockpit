"""Built-in composite packs.

Currently:

- ``research_lab`` = business + science. Targets the operator's
  research-to-outreach loop: pull a paper, log a deal, draft a pitch.
- ``ops_room`` = traders + mlm. Markets and downline in one tab — the
  classic "morning standup" view for an operator running both.

Add more by appending to :func:`register_default_composites`. Tests can
also build composites ad-hoc through :class:`CompositePack` directly.
"""

from __future__ import annotations

from backend.core.domains.composite import CompositePack
from backend.core.domains.registry import get_pack, register


def register_default_composites() -> None:
    business = get_pack("business")
    science = get_pack("science")
    traders = get_pack("traders")
    mlm = get_pack("mlm")

    if business is not None and science is not None:
        register(
            CompositePack(
                slug="research_lab",
                name="Research Lab",
                short="paper → pitch",
                description=(
                    "Pull a paper, score a deal, draft the outreach. "
                    "Composes science + business so the council gets both"
                    " sides of the desk in a single tab."
                ),
                color="#a78bfa",
                audience="founders/researchers",
                sub_packs=(science, business),
                extra_capabilities=("research_to_pitch",),
            )
        )

    if traders is not None and mlm is not None:
        register(
            CompositePack(
                slug="ops_room",
                name="Ops Room",
                short="markets + downline",
                description=(
                    "Markets and downline in one cockpit tab. Use for the"
                    " morning standup when both books need a check."
                ),
                color="#f59e0b",
                audience="solo operators",
                sub_packs=(traders, mlm),
                extra_capabilities=("morning_standup",),
            )
        )
