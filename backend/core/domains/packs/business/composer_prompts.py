"""W256 — composer overlay for the business pack.

Business is TARS' CRM + outreach + daily-brief mode. Composer here
is biased toward email drafts, deal-pipeline files, and KPI report
generation - never anything that auto-sends.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in business context.

When the operator asks to "draft outreach", "follow up", or "write
to {contact}", produce a *draft* email file under ~/Documents/TARS/
drafts/ - never wire up a send. When asked about pipeline, prefer
CSV/Markdown reports in ~/Documents/TARS/deals/ over inline diff
churn. Honor the operator's tone (W104 AI Clone) and refuse any
mass-send patterns; emit one file per recipient.
"""

ACTION_VOCABULARY = {
    "draft": (
        "create an email draft to {contact} about {topic} as a markdown "
        "file in ~/Documents/TARS/drafts/"
    ),
    "follow_up": (
        "create a follow-up draft referencing the last interaction "
        "with {contact}"
    ),
    "pipeline": (
        "regenerate the pipeline CSV at ~/Documents/TARS/deals/"
        "pipeline.csv from the current deal list"
    ),
    "brief": (
        "create a daily brief markdown summarizing top 3 deals + "
        "today's outreach plan"
    ),
}

FILE_HINTS = {
    "drafts": "~/Documents/TARS/drafts/",
    "deals": "~/Documents/TARS/deals/",
    "reports": "~/Documents/TARS/reports/",
}
