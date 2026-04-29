"""TTS engines — three provider tiers, all stdlib-only.

- :class:`ElevenLabsEngine` — best character voices, highest cost.
- :class:`OpenAITTSEngine` — very natural, supports stylistic
  ``instructions`` field on ``gpt-4o-mini-tts``.
- :class:`MacSayEngine` — offline fallback via ``/usr/bin/say``,
  ships with macOS, free, lower fidelity but always available on the
  operator's mac.

Each engine returns :class:`SynthesisResult` (audio bytes + MIME +
length estimate). They never raise on remote / process failures —
they return ``None`` and let the synthesiser fall through to the
next provider.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Optional

from backend.core.vault import get_secret

from .personas import Persona


log = logging.getLogger("tars.voice")


@dataclass(frozen=True)
class SynthesisResult:
    """One synthesised utterance.

    ``provider`` is the engine that produced the audio (``"elevenlabs"``
    / ``"openai"`` / ``"mac_say"``). ``mime`` distinguishes ``audio/mpeg``
    (mp3) from ``audio/wav``.
    """

    audio: bytes
    mime: str
    provider: str
    voice_id: str
    duration_estimate_ms: int
    bytes_total: int

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "voice_id": self.voice_id,
            "mime": self.mime,
            "bytes_total": self.bytes_total,
            "duration_estimate_ms": self.duration_estimate_ms,
        }


class TTSEngine(ABC):
    """Each engine knows how to render text → bytes for one provider."""

    name: str

    @abstractmethod
    async def is_available(self) -> bool:  # pragma: no cover - abstract
        ...

    @abstractmethod
    async def synthesise(
        self, text: str, persona: Persona
    ) -> SynthesisResult | None:  # pragma: no cover - abstract
        ...


# ---------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------

_ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class ElevenLabsEngine(TTSEngine):
    """ElevenLabs streaming TTS — best character voices."""

    name = "elevenlabs"

    def __init__(self, *, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    async def is_available(self) -> bool:
        return bool(_elevenlabs_key())

    async def synthesise(
        self, text: str, persona: Persona
    ) -> SynthesisResult | None:
        key = _elevenlabs_key()
        voice_id = persona.provider.elevenlabs_voice_id
        if not key or not voice_id:
            return None
        body = {
            "text": text,
            "model_id": persona.provider.elevenlabs_model,
            "voice_settings": {
                "stability": persona.provider.elevenlabs_stability,
                "similarity_boost": persona.provider.elevenlabs_similarity,
                "style": persona.provider.elevenlabs_style,
                "use_speaker_boost": True,
            },
        }
        url = f"{_ELEVENLABS_URL}/{voice_id}?output_format=mp3_44100_128"
        headers = {
            "xi-api-key": key,
            "content-type": "application/json",
            "accept": "audio/mpeg",
        }

        def _post() -> bytes | None:
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                log.warning("elevenlabs synth failed: %s", exc)
                return None

        audio = await asyncio.to_thread(_post)
        if not audio:
            return None
        return SynthesisResult(
            audio=audio,
            mime="audio/mpeg",
            provider=self.name,
            voice_id=voice_id,
            duration_estimate_ms=_rough_duration_ms(text),
            bytes_total=len(audio),
        )


# ---------------------------------------------------------------------
# OpenAI TTS
# ---------------------------------------------------------------------

_OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"


class OpenAITTSEngine(TTSEngine):
    """OpenAI text-to-speech (``gpt-4o-mini-tts`` by default).

    On ``gpt-4o-mini-tts`` we send the persona's ``instructions`` so
    the voice picks up the styling (British butler, sarcastic AI, …).
    On older ``tts-1``/``tts-1-hd`` models the field is ignored.
    """

    name = "openai"

    def __init__(self, *, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    async def is_available(self) -> bool:
        return bool(get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY"))

    async def synthesise(
        self, text: str, persona: Persona
    ) -> SynthesisResult | None:
        key = get_secret("TARS_OPENAI_API_KEY") or get_secret("OPENAI_API_KEY")
        voice = persona.provider.openai_voice
        model = persona.provider.openai_model or "gpt-4o-mini-tts"
        if not key or not voice:
            return None

        body: dict[str, object] = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "mp3",
        }
        if persona.provider.openai_instructions and "gpt-4o" in model:
            body["instructions"] = persona.provider.openai_instructions

        headers = {
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "accept": "audio/mpeg",
        }

        def _post() -> bytes | None:
            try:
                req = urllib.request.Request(
                    _OPENAI_TTS_URL,
                    data=json.dumps(body).encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                log.warning("openai tts failed: %s", exc)
                return None

        audio = await asyncio.to_thread(_post)
        if not audio:
            return None
        return SynthesisResult(
            audio=audio,
            mime="audio/mpeg",
            provider=self.name,
            voice_id=voice,
            duration_estimate_ms=_rough_duration_ms(text),
            bytes_total=len(audio),
        )


# ---------------------------------------------------------------------
# macOS `say`
# ---------------------------------------------------------------------


class MacSayEngine(TTSEngine):
    """``/usr/bin/say`` wrapper — offline, zero-config on macOS."""

    name = "mac_say"

    def __init__(self) -> None:
        self._available_cache: Optional[bool] = None
        self._installed_voices_cache: Optional[set[str]] = None

    async def is_available(self) -> bool:
        if self._available_cache is not None:
            return self._available_cache
        if platform.system() != "Darwin":
            self._available_cache = False
            return False
        binary = shutil.which("say")
        self._available_cache = bool(binary)
        return self._available_cache

    async def installed_voices(self) -> set[str]:
        if self._installed_voices_cache is not None:
            return self._installed_voices_cache
        if not await self.is_available():
            self._installed_voices_cache = set()
            return self._installed_voices_cache

        def _list() -> set[str]:
            try:
                out = subprocess.run(
                    ["say", "-v", "?"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5.0,
                )
            except (FileNotFoundError, subprocess.SubprocessError):
                return set()
            voices: set[str] = set()
            for line in (out.stdout or "").splitlines():
                # `Daniel              en_GB    # Hello, my name is Daniel.`
                head = line.split()
                if head:
                    voices.add(head[0])
            return voices

        self._installed_voices_cache = await asyncio.to_thread(_list)
        return self._installed_voices_cache

    async def synthesise(
        self, text: str, persona: Persona
    ) -> SynthesisResult | None:
        if not await self.is_available():
            return None
        voice = persona.provider.mac_say_voice or "Alex"
        installed = await self.installed_voices()
        if installed and voice not in installed:
            voice = self._pick_fallback_voice(persona, installed)
        rate = persona.provider.mac_say_rate or 180

        def _say() -> bytes | None:
            with tempfile.NamedTemporaryFile(
                suffix=".aiff", delete=False
            ) as tmp:
                out_path = tmp.name
            try:
                cmd = [
                    "say",
                    "-v",
                    voice,
                    "-r",
                    str(int(rate)),
                    "-o",
                    out_path,
                    "--data-format=LEI16@22050",
                    "--file-format=WAVE",
                    text,
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=20.0,
                    check=False,
                )
                if proc.returncode != 0:
                    log.warning(
                        "mac say returned %s: %s",
                        proc.returncode,
                        proc.stderr.decode("utf-8", "replace")[:200],
                    )
                    return None
                with open(out_path, "rb") as fh:
                    return fh.read()
            except (subprocess.SubprocessError, OSError) as exc:
                log.warning("mac say failed: %s", exc)
                return None
            finally:
                try:
                    os.unlink(out_path)
                except OSError:
                    pass

        audio = await asyncio.to_thread(_say)
        if not audio:
            return None
        return SynthesisResult(
            audio=audio,
            mime="audio/wav",
            provider=self.name,
            voice_id=voice,
            duration_estimate_ms=_rough_duration_ms(text),
            bytes_total=len(audio),
        )

    @staticmethod
    def _pick_fallback_voice(persona: Persona, installed: set[str]) -> str:
        """Pick a sensible fallback when the persona's preferred voice
        isn't installed on this Mac.

        Strategy: walk a per-accent preference list, then a global list
        of historically-shipped voices, then fall through to whatever
        the system has. We deliberately avoid ``next(iter(set))`` —
        Python's set iteration order is implementation-defined and that
        was making Stark sometimes speak Spanish.
        """

        if persona.accent == "british":
            preference = ("Daniel", "Oliver", "Serena", "Kate", "Alex")
        elif persona.accent == "american":
            preference = ("Alex", "Tom", "Aaron", "Fred", "Bruce", "Daniel")
        else:
            preference = ("Alex", "Daniel", "Samantha", "Tom")
        for candidate in preference:
            if candidate in installed:
                return candidate
        # Final fallback: deterministic alphabetical pick.
        for candidate in sorted(installed):
            return candidate
        return persona.provider.mac_say_voice or "Alex"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _elevenlabs_key() -> str | None:
    return get_secret("TARS_ELEVENLABS_API_KEY") or get_secret("ELEVENLABS_API_KEY")


def _rough_duration_ms(text: str) -> int:
    """Cheap heuristic: ~150 wpm, 5 chars/word average."""

    if not text:
        return 0
    words = max(1, len(text) // 5)
    seconds = words / (150 / 60.0)
    return int(seconds * 1000)
