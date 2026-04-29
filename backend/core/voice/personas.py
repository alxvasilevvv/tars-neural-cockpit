"""Voice persona registry.

A *persona* is a character profile (Jarvis, Stark, HAL 9000…) with
provider-specific voice ids and styling hints. The synthesis layer
picks the best available provider at runtime, then maps the persona
to that provider's voice id / system instructions / parameters.

ElevenLabs voice IDs below are public, stable IDs from their starter
voice library (no cloning, no licence issue). They are overridable
per-persona via env vars (e.g. ``TARS_PERSONA_JARVIS_ELEVENLABS_ID``).

OpenAI voices are documented presets (``alloy``, ``echo``, ``fable``,
``onyx``, ``nova``, ``shimmer``, ``ash``, ``ballad``, ``coral``,
``sage``, ``verse``).

macOS ``say`` voices fall back to ``Daniel`` / ``Alex`` / ``Samantha``
which ship by default; "Premium" / "Enhanced" voices are used when
present (the engine probes ``say -v ?`` at first call).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator, Mapping


@dataclass(frozen=True)
class PersonaProviderHint:
    """Per-provider mapping for a persona."""

    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_stability: float = 0.45
    elevenlabs_similarity: float = 0.85
    elevenlabs_style: float = 0.20

    openai_voice: str | None = None
    openai_model: str = "gpt-4o-mini-tts"
    openai_instructions: str | None = None  # only honoured by gpt-4o-mini-tts

    mac_say_voice: str | None = None
    mac_say_rate: int | None = None  # words per minute
    mac_say_pitch: int | None = None  # semitone offset (post-process)

    def merged(self, override: Mapping[str, object]) -> "PersonaProviderHint":
        """Return a copy with whitelisted overrides applied."""

        keys = {
            "elevenlabs_voice_id",
            "openai_voice",
            "openai_instructions",
            "mac_say_voice",
            "mac_say_rate",
            "mac_say_pitch",
        }
        kwargs = {
            k: getattr(self, k)
            for k in (
                "elevenlabs_voice_id",
                "elevenlabs_model",
                "elevenlabs_stability",
                "elevenlabs_similarity",
                "elevenlabs_style",
                "openai_voice",
                "openai_model",
                "openai_instructions",
                "mac_say_voice",
                "mac_say_rate",
                "mac_say_pitch",
            )
        }
        for k in keys:
            if k in override and override[k] is not None:
                kwargs[k] = override[k]  # type: ignore[assignment]
        return PersonaProviderHint(**kwargs)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Persona:
    """Public-facing voice persona.

    ``id`` is a stable slug used by the cockpit; ``name`` is the human
    label; ``character`` is a short description (also surfaced in the
    UI tooltip / picker).
    """

    id: str
    name: str
    character: str
    description: str
    short: str
    provider: PersonaProviderHint = field(default_factory=PersonaProviderHint)
    accent: str = "neutral"
    locale: str = "en-US"
    license_note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "character": self.character,
            "description": self.description,
            "short": self.short,
            "accent": self.accent,
            "locale": self.locale,
            "license_note": self.license_note,
            "providers": {
                "elevenlabs": {
                    "voice_id": self.provider.elevenlabs_voice_id,
                    "model": self.provider.elevenlabs_model,
                },
                "openai": {
                    "voice": self.provider.openai_voice,
                    "model": self.provider.openai_model,
                    "has_instructions": bool(self.provider.openai_instructions),
                },
                "mac_say": {
                    "voice": self.provider.mac_say_voice,
                    "rate": self.provider.mac_say_rate,
                    "pitch": self.provider.mac_say_pitch,
                },
            },
        }


# ---------------------------------------------------------------------
# Default roster
# ---------------------------------------------------------------------

DEFAULT_PERSONA_ID = "jarvis"


def _env_override(persona_id: str, key: str, default: str | None) -> str | None:
    """Return ``TARS_PERSONA_<ID>_<KEY>`` env var or the default."""

    name = f"TARS_PERSONA_{persona_id.upper()}_{key.upper()}"
    return os.getenv(name) or default


def _build_default_personas() -> dict[str, Persona]:
    personas = {
        "jarvis": Persona(
            id="jarvis",
            name="J.A.R.V.I.S.",
            character="Stark Industries household AI · British butler · calm, precise.",
            description=(
                "Soft-spoken, dry-witted English butler vibe. Lands every line with"
                " composure and a quarter-step of irony, the way Iron Man's house"
                " AI does."
            ),
            short="Calm British butler.",
            accent="british",
            locale="en-GB",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "jarvis", "elevenlabs_id", "onwK4e9ZLuTAKqWW03F9"
                ),  # "Daniel" — British male
                openai_voice=_env_override("jarvis", "openai_voice", "fable"),
                openai_instructions=(
                    "Speak with a refined British butler accent — warm, dry,"
                    " unflappable. Slightly slow. Light irony. Project the"
                    " confidence of an AI that has run the household for years."
                ),
                mac_say_voice=_env_override("jarvis", "mac_say_voice", "Daniel"),
                mac_say_rate=180,
            ),
            license_note=(
                "Inspired by the J.A.R.V.I.S. archetype; voice is a generic"
                " British male preset, not a Disney/Marvel asset."
            ),
        ),
        "stark": Persona(
            id="stark",
            name="Tony Stark",
            character="Wry, charismatic American — Iron Man pilot energy.",
            description=(
                "Quick, charismatic, slightly cocky American male. Smiles into the"
                " sentence. Treats every problem as already solved."
            ),
            short="Charismatic American — Iron Man.",
            accent="american",
            locale="en-US",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "stark", "elevenlabs_id", "pNInz6obpgDQGcFmaJgB"
                ),  # "Adam" — confident American male
                openai_voice=_env_override("stark", "openai_voice", "onyx"),
                openai_instructions=(
                    "Speak as a quick, charismatic American man in his forties."
                    " Slightly wry, confident, faintly amused. Snappy pacing,"
                    " easy on consonants, lands punchlines without selling them."
                ),
                mac_say_voice=_env_override("stark", "mac_say_voice", "Aaron"),
                mac_say_rate=200,
            ),
            license_note=(
                "Inspired by the Tony Stark archetype; voice is a generic"
                " confident American male preset."
            ),
        ),
        "hal9000": Persona(
            id="hal9000",
            name="HAL 9000",
            character="Methodical, gentle American baritone — clinical AI.",
            description=(
                "Smooth, slow, almost too calm. Long vowels. Each word given"
                " its full weight. The lights are on; whether you should be"
                " reassured is up to you."
            ),
            short="Calm clinical AI.",
            accent="american",
            locale="en-US",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "hal9000", "elevenlabs_id", "VR6AewLTigWG4xSOukaG"
                ),  # "Arnold" — deep American male
                openai_voice=_env_override("hal9000", "openai_voice", "echo"),
                openai_instructions=(
                    "Speak as a quiet, methodical AI: gentle American baritone,"
                    " slow pacing, even emphasis, no smile. Deliver every line"
                    " as if the operator were already reassured."
                ),
                mac_say_voice=_env_override("hal9000", "mac_say_voice", "Bruce"),
                mac_say_rate=145,
            ),
            license_note=(
                "Inspired by HAL 9000; voice is a generic deep American male"
                " preset, no recording asset reused."
            ),
        ),
        "glados": Persona(
            id="glados",
            name="GLaDOS",
            character="Sardonic synthetic female — cake-and-passive-aggression.",
            description=(
                "Synthetic-feminine, lightly processed, dripping with passive"
                " aggression. Pauses for sarcasm. The compliments are not"
                " compliments."
            ),
            short="Sardonic synthetic.",
            accent="american",
            locale="en-US",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "glados", "elevenlabs_id", "EXAVITQu4vr4xnSDxMaL"
                ),  # "Sarah" — clear American female
                openai_voice=_env_override("glados", "openai_voice", "shimmer"),
                openai_instructions=(
                    "Speak as a passive-aggressive synthetic female AI. Dry,"
                    " mockingly cheerful, unhurried. Pause briefly mid-sentence"
                    " for sarcasm. Sound polite while being mildly threatening."
                ),
                mac_say_voice=_env_override("glados", "mac_say_voice", "Samantha"),
                mac_say_rate=170,
                mac_say_pitch=-2,
            ),
            license_note=(
                "Inspired by GLaDOS; voice is a generic American female preset."
            ),
        ),
        "tars": Persona(
            id="tars",
            name="TARS",
            character="Interstellar TARS — measured American baritone, dry humour.",
            description=(
                "Calm American male, low warmth, surgical pacing. Every line"
                " sounds like a status report, even the jokes."
            ),
            short="Interstellar TARS.",
            accent="american",
            locale="en-US",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "tars", "elevenlabs_id", "JBFqnCBsd6RMkjVDRZzb"
                ),  # "George" — warm British/transatlantic male
                openai_voice=_env_override("tars", "openai_voice", "ash"),
                openai_instructions=(
                    "Speak as a calm, deliberate American male AI with low"
                    " warmth and surgical pacing. Every line sounds like a"
                    " status report, even the dry humour. No theatrics."
                ),
                mac_say_voice=_env_override("tars", "mac_say_voice", "Tom"),
                mac_say_rate=165,
            ),
            license_note=(
                "Inspired by TARS in Interstellar; voice is a generic male"
                " preset."
            ),
        ),
        "operator": Persona(
            id="operator",
            name="Operator",
            character="Default neutral cockpit voice — clear, hands-off.",
            description=(
                "Neutral, clear American/British transatlantic. Default for the"
                " cockpit when the operator hasn't picked a character."
            ),
            short="Neutral cockpit voice.",
            accent="neutral",
            locale="en-US",
            provider=PersonaProviderHint(
                elevenlabs_voice_id=_env_override(
                    "operator", "elevenlabs_id", "21m00Tcm4TlvDq8ikWAM"
                ),  # "Rachel" — neutral female
                openai_voice=_env_override("operator", "openai_voice", "alloy"),
                openai_instructions=(
                    "Speak as a clear, neutral cockpit operator voice. Calm,"
                    " professional, hands-off. No accent embellishment."
                ),
                mac_say_voice=_env_override("operator", "mac_say_voice", "Alex"),
                mac_say_rate=185,
            ),
        ),
    }
    return personas


_REGISTRY: dict[str, Persona] = _build_default_personas()


def list_personas() -> list[Persona]:
    return list(_REGISTRY.values())


def get_persona(persona_id: str | None) -> Persona:
    if persona_id and persona_id in _REGISTRY:
        return _REGISTRY[persona_id]
    return _REGISTRY[DEFAULT_PERSONA_ID]


def register_persona(persona: Persona) -> None:
    """Register or replace a persona in the runtime registry.

    Useful for domain packs that want to ship branded voices.
    """

    _REGISTRY[persona.id] = persona


def reset_personas() -> None:
    """Reset the registry to the built-in defaults (for tests)."""

    global _REGISTRY
    _REGISTRY = _build_default_personas()


def iter_personas() -> Iterator[Persona]:
    yield from _REGISTRY.values()
