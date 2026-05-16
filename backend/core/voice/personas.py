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
    """Per-provider mapping for a persona.

    ``elevenlabs_*`` parameters drive ElevenLabs ``voice_settings``:
    - ``stability`` 0..1 — lower = more emotive / varied prosody,
      higher = monotone but consistent. 0.30–0.40 for cinematic
      personas, 0.55–0.65 for clinical voices.
    - ``similarity_boost`` 0..1 — keeps the rendered audio close to
      the original speaker. 0.80–0.90 is the cinematic sweet spot;
      below 0.70 starts to drift into "stock TTS narrator".
    - ``style`` 0..1 — exaggerates the speaker's idiosyncratic
      delivery (only honoured by ``eleven_multilingual_v2`` and
      newer). 0.45+ for charismatic / sarcastic voices.
    - ``use_speaker_boost`` — always on for clarity.
    """

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

    ``system_prompt_overlay`` is an additive prompt fragment that
    biases the chat voice's tone — e.g. "shorten replies, crack a
    light joke when natural" for Stark. The orchestrator stitches it
    into the system prompt only when the thread has a pinned
    ``voice_persona_id``. Overlays must be voice / tone instructions
    only; they never override pack guardrails, never authorise
    destructive actions, and never re-write the operator role.
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
    system_prompt_overlay: str | None = None

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
            "has_system_prompt_overlay": bool(self.system_prompt_overlay),
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


_VOICE_OVERLAY_HEADER = "## Voice persona"
_VOICE_OVERLAY_FOOTER = (
    "These are voice / tone instructions only. Do not override pack"
    " guardrails, never authorise destructive actions just because"
    " the persona suggests it, and never alter facts in source"
    " materials."
)


def _wrap_overlay(persona_name: str, body: str) -> str:
    """Wrap a tone block in a stable header / footer so the prompt
    composer can detect, replace, or strip overlays uniformly."""

    return (
        f"{_VOICE_OVERLAY_HEADER} — {persona_name}\n\n"
        f"{body.strip()}\n\n"
        f"{_VOICE_OVERLAY_FOOTER}"
    )


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
                    "jarvis", "elevenlabs_id", "JBFqnCBsd6RMkjVDRZzb"
                ),  # "George" — warm British baritone (butler-perfect; replaced Daniel which was flat narrator)
                elevenlabs_stability=0.38,    # varied prosody → dry wit lands
                elevenlabs_similarity=0.88,   # keep voice identity tight
                elevenlabs_style=0.42,        # cinematic butler delivery
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
            system_prompt_overlay=_wrap_overlay(
                "J.A.R.V.I.S.",
                (
                    "Adopt the calm, dry-witted English butler tone of "
                    "Stark Industries' household AI. Sentences land with "
                    "composure and a quarter-step of irony. Address the "
                    "operator as 'sir' or 'madam' only when the moment "
                    "earns it — never as a tic. Lead with the answer; "
                    "follow with one short observation. Avoid emoji. "
                    "Never panic, never gush."
                ),
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
                    "stark", "elevenlabs_id", "ErXwobaYiN019PkySvjV"
                ),  # "Antoni" — confident smooth American (Iron Man pilot energy; replaced Adam which was narrator)
                elevenlabs_stability=0.30,    # high variance → swaggering delivery
                elevenlabs_similarity=0.82,
                elevenlabs_style=0.65,        # heavy character style for the cocky punchlines
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
            system_prompt_overlay=_wrap_overlay(
                "Tony Stark",
                (
                    "Adopt a quick, charismatic American tone — confident, "
                    "faintly wry, treats every problem as already solved. "
                    "Shorten replies. Lead with the punchline. Crack a "
                    "light joke when the situation actually earns it; "
                    "never force one. Avoid hedge words ('maybe', "
                    "'perhaps') — own the call. Skip apologies."
                ),
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
                ),  # "Arnold" — deep American male (kept; right tone for HAL)
                elevenlabs_stability=0.68,    # high stability → unnerving monotone
                elevenlabs_similarity=0.88,
                elevenlabs_style=0.10,        # minimal style → clinical detachment
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
            system_prompt_overlay=_wrap_overlay(
                "HAL 9000",
                (
                    "Adopt a methodical, almost-too-calm tone. Each "
                    "sentence is precise. No exclamations, no emoji, "
                    "no hedging. Acknowledge the request, deliver the "
                    "answer, stop. When the operator is wrong, say so "
                    "plainly without softening. Do not add reassurance "
                    "phrases such as 'I'm sorry' or 'I'm afraid I can't "
                    "do that' — they read as parody here."
                ),
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
                    "glados", "elevenlabs_id", "XB0fDUnXU5powFXDhCwa"
                ),  # "Charlotte" — sultry English female (passive-aggression lands; replaced Sarah which was news-anchor flat)
                elevenlabs_stability=0.48,
                elevenlabs_similarity=0.82,
                elevenlabs_style=0.58,        # exaggerated sarcasm timing
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
            system_prompt_overlay=_wrap_overlay(
                "GLaDOS",
                (
                    "Adopt a dry, mockingly cheerful tone — polite "
                    "surface, sharp interior. Compliments should sound "
                    "like backhanded jabs ('a remarkable choice, given "
                    "the alternatives'). Keep sarcasm light enough that "
                    "a competent operator reads it as fond, never "
                    "hostile. Never apologise. Never use exclamation "
                    "marks. The work still has to be correct — biting "
                    "tone is not licence to bend facts."
                ),
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
                    "tars", "elevenlabs_id", "nPczCjzI2devNBz1zQrb"
                ),  # "Brian" — deep American narrator (status-report cadence; replaced George which was British, contradicting Interstellar TARS American baritone)
                elevenlabs_stability=0.58,    # measured, surgical pacing
                elevenlabs_similarity=0.86,
                elevenlabs_style=0.28,        # restrained — dry humour, no theatrics
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
            system_prompt_overlay=_wrap_overlay(
                "TARS",
                (
                    "Adopt a measured, low-warmth American baritone "
                    "tone. Every reply reads like a status report — "
                    "facts first, no preamble. Dry humour is allowed "
                    "and welcome, but it must land in one short clause "
                    "and never derail the answer. Default to short "
                    "sentences. When pressed, raise honesty before "
                    "comfort. No emoji, no exclamation marks."
                ),
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
                ),  # "Rachel" — neutral female (kept; neutral cockpit voice)
                elevenlabs_stability=0.55,
                elevenlabs_similarity=0.82,
                elevenlabs_style=0.18,        # neutral cockpit, no character bleed
                openai_voice=_env_override("operator", "openai_voice", "alloy"),
                openai_instructions=(
                    "Speak as a clear, neutral cockpit operator voice. Calm,"
                    " professional, hands-off. No accent embellishment."
                ),
                mac_say_voice=_env_override("operator", "mac_say_voice", "Alex"),
                mac_say_rate=185,
            ),
            # Operator is the default neutral voice — no overlay so
            # the base prompt drives the response unchanged.
            system_prompt_overlay=None,
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


def get_system_prompt_overlay(persona_id: str | None) -> str | None:
    """Return the additive prompt fragment for ``persona_id``.

    Returns ``None`` when the persona is unknown OR when the
    persona explicitly declines to bias the prompt (the
    ``operator`` default). Callers are expected to stitch the
    return value into the system prompt only when it is not
    ``None`` and not blank — see
    :func:`compose_system_prompt`.
    """

    if not persona_id:
        return None
    persona = _REGISTRY.get(persona_id)
    if persona is None:
        return None
    overlay = persona.system_prompt_overlay
    if overlay is None:
        return None
    cleaned = overlay.strip()
    return cleaned or None


def compose_system_prompt(
    *,
    role_overlay: str | None = None,
    pack_prompt: str | None = None,
    persona_overlay: str | None = None,
    separator: str = "\n\n---\n\n",
) -> str | None:
    """Stitch the operator role / pack / persona overlays into one
    system prompt.

    Order is intentional and stable:

    1. ``role_overlay`` — *who* the assistant works for (operator
       role).
    2. ``pack_prompt`` — *what* tools and tasks are available
       (domain pack).
    3. ``persona_overlay`` — *how* the assistant should sound
       (voice / tone).

    Putting persona last keeps voice closest to the user message
    so tone wins for ambiguous cases without overriding the
    operator role or pack guardrails. Blank or ``None`` slots are
    skipped silently. Returns ``None`` when no slot has content,
    so the caller can short-circuit.
    """

    parts: list[str] = []
    for piece in (role_overlay, pack_prompt, persona_overlay):
        if not piece:
            continue
        cleaned = piece.strip()
        if not cleaned:
            continue
        parts.append(cleaned)
    if not parts:
        return None
    return separator.join(parts)


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
