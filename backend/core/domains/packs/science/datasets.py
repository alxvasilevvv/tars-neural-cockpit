"""Dataset reference extraction for the science pack.

Backs the ``science.extract_dataset`` action. Goal: given a paper's
abstract / title (or any operator-provided text), surface the
**concrete datasets** mentioned without an LLM in the loop. The
output is a deterministic, audit-friendly list — every match
carries an ``evidence`` snippet so an operator can verify the call
without re-reading the source.

Two complementary detectors:

1. **Named-dataset registry** (`KNOWN_DATASETS`) — a curated list of
   well-known ML / biotech / physics datasets with their aliases
   and (optional) homepage. The matcher walks the registry once,
   case-insensitive whole-word search, and dedupes by canonical
   id.
2. **Repository URL patterns** (`URL_PATTERNS`) — a small regex
   library for common dataset / artefact hosts (Zenodo, Figshare,
   HuggingFace Datasets, Kaggle, OpenML, OSF, Dryad, FigShare's
   ``doi:10.5281/zenodo.…`` shape). The matcher captures the DOI
   / id and reconstructs a canonical URL.

Both detectors are intentionally over-flagging-shy: they only fire
on clear, unambiguous evidence. False negatives are recoverable
(the operator can always re-run with explicit ``text=…``); false
positives clutter the cockpit and erode trust.

All output stays plain dataclasses + dicts — no new deps.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable


# ---------------------------------------------------------------------
# Named-dataset registry
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class KnownDataset:
    """A single entry in the curated registry."""

    canonical_id: str
    aliases: tuple[str, ...]
    homepage: str | None = None
    domain: str = "general"


KNOWN_DATASETS: tuple[KnownDataset, ...] = (
    # --- vision -----------------------------------------------------
    KnownDataset(
        canonical_id="imagenet",
        aliases=("ImageNet", "ImageNet-1K", "ImageNet 1K", "ILSVRC"),
        homepage="https://www.image-net.org/",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="coco",
        aliases=("MS-COCO", "MSCOCO", "Microsoft COCO", "COCO"),
        homepage="https://cocodataset.org/",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="cifar-10",
        aliases=("CIFAR-10", "CIFAR10"),
        homepage="https://www.cs.toronto.edu/~kriz/cifar.html",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="cifar-100",
        aliases=("CIFAR-100", "CIFAR100"),
        homepage="https://www.cs.toronto.edu/~kriz/cifar.html",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="mnist",
        aliases=("MNIST",),
        homepage="http://yann.lecun.com/exdb/mnist/",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="fashion-mnist",
        aliases=("Fashion-MNIST", "FashionMNIST"),
        homepage="https://github.com/zalandoresearch/fashion-mnist",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="open-images",
        aliases=("Open Images", "OpenImages"),
        homepage="https://storage.googleapis.com/openimages/web/index.html",
        domain="vision",
    ),
    KnownDataset(
        canonical_id="laion-5b",
        aliases=("LAION-5B", "LAION5B"),
        homepage="https://laion.ai/blog/laion-5b/",
        domain="vision",
    ),
    # --- nlp --------------------------------------------------------
    KnownDataset(
        canonical_id="glue",
        aliases=("GLUE",),
        homepage="https://gluebenchmark.com/",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="superglue",
        aliases=("SuperGLUE",),
        homepage="https://super.gluebenchmark.com/",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="squad",
        aliases=("SQuAD", "SQuAD 1.1", "SQuAD 2.0"),
        homepage="https://rajpurkar.github.io/SQuAD-explorer/",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="mmlu",
        aliases=("MMLU",),
        homepage="https://github.com/hendrycks/test",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="hellaswag",
        aliases=("HellaSwag",),
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="the-pile",
        aliases=("The Pile",),
        homepage="https://pile.eleuther.ai/",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="c4",
        aliases=("C4",),
        homepage="https://www.tensorflow.org/datasets/catalog/c4",
        domain="nlp",
    ),
    KnownDataset(
        canonical_id="wikitext-103",
        aliases=("WikiText-103", "WikiText103"),
        domain="nlp",
    ),
    # --- speech / audio --------------------------------------------
    KnownDataset(
        canonical_id="librispeech",
        aliases=("LibriSpeech",),
        homepage="https://www.openslr.org/12",
        domain="audio",
    ),
    KnownDataset(
        canonical_id="common-voice",
        aliases=("Common Voice", "CommonVoice"),
        homepage="https://commonvoice.mozilla.org/",
        domain="audio",
    ),
    # --- robotics / RL ---------------------------------------------
    KnownDataset(
        canonical_id="atari-arcade",
        aliases=("Atari 2600", "Arcade Learning Environment", "ALE"),
        domain="rl",
    ),
    KnownDataset(
        canonical_id="dm-control",
        aliases=("DM Control", "DeepMind Control Suite"),
        domain="rl",
    ),
    # --- biotech ---------------------------------------------------
    KnownDataset(
        canonical_id="uk-biobank",
        aliases=("UK Biobank",),
        homepage="https://www.ukbiobank.ac.uk/",
        domain="biotech",
    ),
    KnownDataset(
        canonical_id="tcga",
        aliases=("TCGA", "The Cancer Genome Atlas"),
        homepage="https://www.cancer.gov/ccg/research/genome-sequencing/tcga",
        domain="biotech",
    ),
    KnownDataset(
        canonical_id="alphafold-db",
        aliases=("AlphaFold DB", "AlphaFold Protein Structure Database"),
        homepage="https://alphafold.ebi.ac.uk/",
        domain="biotech",
    ),
    # --- cross-disciplinary ----------------------------------------
    KnownDataset(
        canonical_id="kaggle",
        aliases=("Kaggle Datasets",),
        homepage="https://www.kaggle.com/datasets",
        domain="general",
    ),
)


# Pre-build a single regex that matches any alias as a whole word.
# We anchor at word boundaries on either side so "MNIST" doesn't
# match "MNISTpaper" but does match "MNIST," or "(MNIST)".
def _build_alias_regex(registry: Iterable[KnownDataset]) -> re.Pattern[str]:
    parts: list[str] = []
    for entry in registry:
        for alias in entry.aliases:
            parts.append(re.escape(alias))
    parts.sort(key=len, reverse=True)
    pattern = r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])"
    return re.compile(pattern, re.IGNORECASE)


_ALIAS_REGEX: re.Pattern[str] | None = None


def _alias_regex() -> re.Pattern[str]:
    global _ALIAS_REGEX
    if _ALIAS_REGEX is None:
        _ALIAS_REGEX = _build_alias_regex(KNOWN_DATASETS)
    return _ALIAS_REGEX


def _alias_to_entry() -> dict[str, KnownDataset]:
    """Lower-cased alias → canonical entry."""

    out: dict[str, KnownDataset] = {}
    for entry in KNOWN_DATASETS:
        for alias in entry.aliases:
            out[alias.lower()] = entry
    return out


# ---------------------------------------------------------------------
# Repository URL patterns
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class RepoPattern:
    """Regex + canonical URL builder for a dataset host."""

    source: str
    regex: re.Pattern[str]
    template: str  # group 1 + (optional) group 2 substituted with {0}/{1}
    label: str  # short human label for the cockpit


URL_PATTERNS: tuple[RepoPattern, ...] = (
    RepoPattern(
        source="zenodo",
        regex=re.compile(
            r"\bzenodo(?:\.org)?/(?:record|records)/(\d+)\b", re.IGNORECASE
        ),
        template="https://zenodo.org/record/{0}",
        label="Zenodo record",
    ),
    RepoPattern(
        source="zenodo",
        regex=re.compile(r"\b10\.5281/zenodo\.(\d+)\b", re.IGNORECASE),
        template="https://doi.org/10.5281/zenodo.{0}",
        label="Zenodo DOI",
    ),
    RepoPattern(
        source="figshare",
        regex=re.compile(r"\bfigshare\.com/articles/[^\s\)]+/(\d+)\b", re.IGNORECASE),
        template="https://figshare.com/articles/{0}",
        label="Figshare article",
    ),
    RepoPattern(
        source="huggingface",
        regex=re.compile(
            r"\bhuggingface\.co/datasets/([\w\-]+/[\w\-\.]+)\b", re.IGNORECASE
        ),
        template="https://huggingface.co/datasets/{0}",
        label="HuggingFace Dataset",
    ),
    RepoPattern(
        source="kaggle",
        regex=re.compile(
            r"\bkaggle\.com/(?:datasets|competitions)/([\w\-]+/[\w\-]+)\b",
            re.IGNORECASE,
        ),
        template="https://www.kaggle.com/datasets/{0}",
        label="Kaggle dataset",
    ),
    RepoPattern(
        source="openml",
        regex=re.compile(r"\bopenml\.org/d/(\d+)\b", re.IGNORECASE),
        template="https://www.openml.org/d/{0}",
        label="OpenML dataset",
    ),
    RepoPattern(
        source="osf",
        regex=re.compile(r"\bosf\.io/([a-z0-9]{4,8})\b", re.IGNORECASE),
        template="https://osf.io/{0}/",
        label="OSF project",
    ),
    RepoPattern(
        source="dryad",
        regex=re.compile(r"\b10\.5061/dryad\.([a-z0-9]+)\b", re.IGNORECASE),
        template="https://doi.org/10.5061/dryad.{0}",
        label="Dryad DOI",
    ),
)


# ---------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetMention:
    """One dataset reference detected in the input."""

    canonical_id: str
    name: str
    source: str  # "known_dataset" | "zenodo" | "huggingface" | …
    evidence: str  # short snippet around the match
    url: str | None = None
    domain: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        body = asdict(self)
        if not body["extra"]:
            body.pop("extra")
        if body.get("url") is None:
            body.pop("url")
        if body.get("domain") is None:
            body.pop("domain")
        return body


# ---------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------


def _evidence_snippet(text: str, start: int, end: int, *, window: int = 60) -> str:
    """Trim the input around the match so the cockpit can show context."""

    lo = max(0, start - window)
    hi = min(len(text), end + window)
    snippet = text[lo:hi].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if lo > 0:
        snippet = "…" + snippet
    if hi < len(text):
        snippet = snippet + "…"
    return snippet


def extract_datasets_from_text(text: str) -> list[DatasetMention]:
    """Return all dataset references detected in ``text``.

    Dedupe rules:

    - One mention per ``(canonical_id, source)`` pair — the first
      match wins, and its ``evidence`` is the surrounding snippet.
    - Named datasets and URL patterns can both fire for the same
      canonical id (e.g. an abstract that mentions "ImageNet" plus
      a figshare DOI for an ImageNet subset). The cockpit can then
      group them.

    Empty / whitespace-only input returns ``[]`` without raising.
    """

    if not text or not text.strip():
        return []

    out: list[DatasetMention] = []
    seen: set[tuple[str, str]] = set()
    alias_to_entry = _alias_to_entry()

    for match in _alias_regex().finditer(text):
        alias = match.group(0)
        entry = alias_to_entry.get(alias.lower())
        if entry is None:
            continue
        key = (entry.canonical_id, "known_dataset")
        if key in seen:
            continue
        seen.add(key)
        out.append(
            DatasetMention(
                canonical_id=entry.canonical_id,
                name=alias,
                source="known_dataset",
                evidence=_evidence_snippet(text, match.start(), match.end()),
                url=entry.homepage,
                domain=entry.domain,
            )
        )

    for pattern in URL_PATTERNS:
        for match in pattern.regex.finditer(text):
            captured = match.group(1)
            canonical_id = f"{pattern.source}:{captured.lower()}"
            key = (canonical_id, pattern.source)
            if key in seen:
                continue
            seen.add(key)
            url = pattern.template.format(*match.groups())
            out.append(
                DatasetMention(
                    canonical_id=canonical_id,
                    name=f"{pattern.label}: {captured}",
                    source=pattern.source,
                    evidence=_evidence_snippet(text, match.start(), match.end()),
                    url=url,
                )
            )

    return out


__all__ = [
    "DatasetMention",
    "KNOWN_DATASETS",
    "KnownDataset",
    "RepoPattern",
    "URL_PATTERNS",
    "extract_datasets_from_text",
]
