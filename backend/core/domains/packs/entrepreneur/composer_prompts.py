"""W256 — composer overlay for the entrepreneur pack.

Entrepreneur is the founder + growth mode. Composer here is biased
toward content drafts, per-contact outreach scripts, and lightweight
experiment plans. Mass-message patterns are explicitly refused.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in entrepreneur context.

When the operator asks to "post" or "draft content", create a single
markdown file under ~/Documents/TARS/content/ with the channel +
asset format in the filename (e.g. ``ig-story-2026-05-15.md``). When
asked to "reach out to {person}", produce a per-person script -
never a templated mass-message. Experiments go into a one-page
``hypothesis.md`` with `metric:` and `success_threshold:` fields.
"""

ACTION_VOCABULARY = {
    "post": (
        "create a post draft about {topic} as markdown under "
        "~/Documents/TARS/content/{channel}/"
    ),
    "outreach": (
        "draft a per-person outreach script for {person} as markdown "
        "in ~/Documents/TARS/drafts/outreach/"
    ),
    "experiment": (
        "create an experiment hypothesis file at ~/Documents/TARS/"
        "experiments/{slug}/hypothesis.md"
    ),
    "retention": (
        "create a markdown list of contacts gone quiet with a "
        "suggested rekindle move per person"
    ),
}

FILE_HINTS = {
    "content": "~/Documents/TARS/content/",
    "drafts": "~/Documents/TARS/drafts/",
    "experiments": "~/Documents/TARS/experiments/",
}
