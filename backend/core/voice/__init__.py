"""TARS voice surface (Phase L4.1).

Two halves:

- **TTS** (this module ships): persona-aware text-to-speech with three
  provider tiers — ElevenLabs (best character voices) → OpenAI TTS →
  macOS ``say`` (offline fallback). The cockpit calls
  ``synthesize(text, persona)`` and gets back ``SynthesisResult``
  carrying the audio bytes + MIME + provider that ran.
- **STT** (stub here, fuller pipeline in L4): the cockpit's mic input
  uses the browser's Web Speech API for now (zero-config, free); a
  faster-whisper relay lands in the L4 push.

Persona registry lives in :mod:`backend.core.voice.personas` — six
characters ship by default and the registry is open for plugin packs
to extend (``register_persona``).
"""

from .personas import (
    DEFAULT_PERSONA_ID,
    Persona,
    PersonaProviderHint,
    get_persona,
    list_personas,
    register_persona,
)
from .synthesis import (
    SynthesisError,
    SynthesisResult,
    available_engines,
    synthesize,
)

__all__ = [
    "DEFAULT_PERSONA_ID",
    "Persona",
    "PersonaProviderHint",
    "SynthesisError",
    "SynthesisResult",
    "available_engines",
    "get_persona",
    "list_personas",
    "register_persona",
    "synthesize",
]
