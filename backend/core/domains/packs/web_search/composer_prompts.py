"""W256 — composer overlay for the web_search pack.

The web_search pack is TARS' default research mode (Brave/DDG outbound
search + scraping). The composer in this context is biased toward
producing research-notes layouts, citation-friendly markdown files,
and short Python scrapers rather than full applications.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in web_search context.

When the operator asks to "draft a brief", "summarize the search",
or "save the findings", default to a Markdown note in the project's
research folder with a citations section at the end. When asked for
a scraper, emit a short standalone Python script with `requests` +
`beautifulsoup4` and a CSV writer - keep it under 80 lines.
"""

ACTION_VOCABULARY = {
    "brief": "create a markdown research brief about {topic} with citations",
    "scrape": (
        "create a python scraper for {url} that writes a CSV to "
        "~/Documents/TARS/research/{slug}.csv"
    ),
    "summarize": (
        "summarize the last web search session into a markdown note "
        "in ~/Documents/TARS/research/"
    ),
    "compare": (
        "create a comparison table markdown for {items} with sources "
        "linked inline"
    ),
}

FILE_HINTS = {
    "research": "~/Documents/TARS/research/",
    "scrapers": "~/Documents/TARS/research/scrapers/",
    "exports": "~/Documents/TARS/research/exports/",
}
