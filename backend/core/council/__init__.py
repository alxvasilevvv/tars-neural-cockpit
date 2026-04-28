"""Council — multi-voice orchestrator for TARS.

Two voices propose, an arbiter decides. The orchestrator emits a
``sampler.decision`` event for every deliberation so meeet can build
per-model leaderboards across products.
"""

from .orchestrator import CouncilOrchestrator, Deliberation, get_council
from .voices import (
    LocalVoice,
    MockCloudVoice,
    Proposal,
    Voice,
)

__all__ = [
    "CouncilOrchestrator",
    "Deliberation",
    "LocalVoice",
    "MockCloudVoice",
    "Proposal",
    "Voice",
    "get_council",
]
