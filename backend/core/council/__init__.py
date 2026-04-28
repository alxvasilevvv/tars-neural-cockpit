"""Council — multi-voice orchestrator for TARS.

Two voices propose, an arbiter decides. The orchestrator emits a
``sampler.decision`` event for every deliberation so meeet can build
per-model leaderboards across products.
"""

from .llm import AnthropicVoice, OpenAIVoice, detect_llm_voice
from .orchestrator import CouncilOrchestrator, Deliberation, get_council
from .voices import (
    LocalVoice,
    MockCloudVoice,
    Proposal,
    Voice,
)

__all__ = [
    "AnthropicVoice",
    "CouncilOrchestrator",
    "Deliberation",
    "LocalVoice",
    "MockCloudVoice",
    "OpenAIVoice",
    "Proposal",
    "Voice",
    "detect_llm_voice",
    "get_council",
]
