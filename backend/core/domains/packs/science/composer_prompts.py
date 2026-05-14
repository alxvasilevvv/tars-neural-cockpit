"""W256 — composer overlay for the science pack.

Science (arXiv triage + citation graph + hypothesis logs) wants
composer biased toward LaTeX/markdown notes, BibTeX entries, and
reproducible experiment scripts.
"""

from __future__ import annotations

SYSTEM_PROMPT_OVERLAY = """\
Composer is operating in science context.

When the operator says "log a hypothesis", emit a markdown file
under ~/Documents/TARS/science/hypotheses/ with `id:`, `claim:`,
`prediction:`, `falsifier:`. When asked to "cite" or "add a paper",
append a BibTeX entry to ~/Documents/TARS/science/refs.bib and a
brief summary markdown alongside it. Reproducible scripts go under
~/Documents/TARS/science/experiments/{slug}/run.py with a fixed
random seed and a results.md output.
"""

ACTION_VOCABULARY = {
    "hypothesis": (
        "create a hypothesis log file at ~/Documents/TARS/science/"
        "hypotheses/{slug}.md"
    ),
    "cite": (
        "append a BibTeX entry for {arxiv_id} to ~/Documents/TARS/"
        "science/refs.bib plus a summary markdown next to it"
    ),
    "experiment": (
        "scaffold a reproducible experiment at ~/Documents/TARS/"
        "science/experiments/{slug}/ with run.py and results.md"
    ),
    "review": (
        "create a markdown paper-review under ~/Documents/TARS/"
        "science/reviews/{arxiv_id}.md"
    ),
}

FILE_HINTS = {
    "hypotheses": "~/Documents/TARS/science/hypotheses/",
    "experiments": "~/Documents/TARS/science/experiments/",
    "refs": "~/Documents/TARS/science/refs.bib",
}
