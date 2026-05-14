"""W256 — composer overlay for the civic pack.

Civic (W204) is the public-records / legislators / court-cases pack
that ships free for all tiers. Composer here favours FOIA letter
drafts, citation-linked policy briefs, and structured request logs.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in civic context.

When the operator asks to "draft a FOIA", produce a polite, citation-
backed letter as markdown under ~/Documents/TARS/civic/foia/. When
asked to "track a bill" or "log a record", emit a structured JSON
entry under ~/Documents/TARS/civic/records/ keyed by jurisdiction.
Always cite the public source URL. Never fabricate case numbers,
docket IDs, or legislator names.
"""

ACTION_VOCABULARY = {
    "foia": (
        "draft a FOIA request letter to {agency} about {topic} as "
        "markdown in ~/Documents/TARS/civic/foia/"
    ),
    "brief": (
        "create a policy brief markdown for {bill} with section-by-"
        "section analysis and citations"
    ),
    "log": (
        "append a record entry to ~/Documents/TARS/civic/records/"
        "{jurisdiction}.jsonl with id, date, source url"
    ),
    "compare": (
        "compare {a} vs {b} legislation as a markdown table with "
        "linked sources"
    ),
}

FILE_HINTS = {
    "foia": "~/Documents/TARS/civic/foia/",
    "records": "~/Documents/TARS/civic/records/",
    "briefs": "~/Documents/TARS/civic/briefs/",
}
