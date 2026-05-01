"""Deterministic content drafter for ``mlm.generate_post``.

The original ``generate_post`` was a one-line three-channel stub.
Operators asked for tone + language knobs and a richer per-channel
voice — this module is the upgrade.

Surface
-------

All knobs are optional with safe defaults so existing playbooks
keep working unchanged:

- ``channel`` ∈ ``ig | tg | wa | linkedin`` (default ``ig``).
- ``format`` ∈ ``post | story | reel | dm`` (default ``post``).
- ``tone`` ∈ ``warm | professional | urgent | celebratory``
  (default ``warm``).
- ``language`` ∈ ``en | ru | es`` (default ``en``).
- ``topic`` — string, falls back to ``"team momentum"``.
- ``cta`` — string, falls back to a tone-appropriate default.

Determinism
-----------

The drafter is pure: same inputs → same output. There is no RNG
or LLM call. We do not pretend to be the council; we deliberately
produce a starting draft an operator can edit.

Hashtags
--------

Generated only for ``ig`` and ``linkedin``. Capped at 8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


KNOWN_CHANNELS: tuple[str, ...] = ("ig", "tg", "wa", "linkedin")
KNOWN_FORMATS: tuple[str, ...] = ("post", "story", "reel", "dm")
KNOWN_TONES: tuple[str, ...] = ("warm", "professional", "urgent", "celebratory")
KNOWN_LANGUAGES: tuple[str, ...] = ("en", "ru", "es")

DEFAULT_TOPIC = "team momentum"


@dataclass(frozen=True)
class PostDraft:
    """Render-ready output of the drafter."""

    channel: str
    format: str
    tone: str
    language: str
    topic: str
    draft: str
    cta: str
    hashtags: tuple[str, ...] = field(default_factory=tuple)
    char_count: int = 0
    word_count: int = 0
    model: str = "drafter-v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "format": self.format,
            "tone": self.tone,
            "language": self.language,
            "topic": self.topic,
            "draft": self.draft,
            "cta": self.cta,
            "hashtags": list(self.hashtags),
            "char_count": self.char_count,
            "word_count": self.word_count,
            "model": self.model,
        }


# ---------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------
#
# Layered lookup: templates[language][channel][tone] → str.
# Each template can use the placeholder ``{topic}``. Format-specific
# tweaks live in `_format_overlay` below.
#
# The strings are intentionally short and operator-editable. Length
# tuned to: IG ≤ 280, TG/WA ≤ 220, LinkedIn ≤ 320.

_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "en": {
        "ig": {
            "warm": (
                "Three things this week: traction, learning, and {topic}. "
                "Tag a teammate who's pushing the same direction."
            ),
            "professional": (
                "Update on {topic}. Numbers are trending. "
                "Sharing what's working in the comments."
            ),
            "urgent": (
                "Heads up: {topic} is the priority for the next 48h. "
                "If you're in, drop a comment."
            ),
            "celebratory": (
                "Big week for {topic}. Proud of the team. "
                "Tag the person who pushed you forward."
            ),
        },
        "tg": {
            "warm": (
                "Quick update — {topic}. Reply with one win and one block. "
                "Will sync at 18:00."
            ),
            "professional": (
                "Update on {topic}. Forward-looking note in next message. "
                "Sync at 18:00."
            ),
            "urgent": (
                "Priority shift: {topic}. Need replies by 17:00. "
                "Yes/No is enough — details after."
            ),
            "celebratory": (
                "{topic} — done. Sharing the receipts in the next message. "
                "Sync at 18:00 to debrief."
            ),
        },
        "wa": {
            "warm": (
                "Hi! Sharing today's note on {topic}. "
                "Read in 60s; reply ✅ if useful."
            ),
            "professional": (
                "Hi, sharing the daily on {topic}. "
                "Confirm receipt with a quick reply."
            ),
            "urgent": (
                "Quick — {topic} needs attention today. "
                "Reply ASAP if you need help."
            ),
            "celebratory": (
                "Win to share: {topic}. Tap ✅ if you saw it; "
                "we'll deconstruct on tomorrow's call."
            ),
        },
        "linkedin": {
            "warm": (
                "A quick thought on {topic}. "
                "Sharing what we tried, what worked, what didn't — "
                "comments are open."
            ),
            "professional": (
                "Notes on {topic}. Three observations from the field, "
                "one decision we changed. Curious what others see."
            ),
            "urgent": (
                "{topic} — worth a closer look this week. "
                "We're shifting attention there; happy to compare notes."
            ),
            "celebratory": (
                "Milestone: {topic}. Crediting the team behind it. "
                "Sharing the playbook in a follow-up post."
            ),
        },
    },
    "ru": {
        "ig": {
            "warm": (
                "Три вещи за неделю: рост, уроки и {topic}. "
                "Отметь того, кто двигается в том же направлении."
            ),
            "professional": (
                "Сводка по {topic}. Цифры идут в рост. "
                "Что сработало — расскажу в комментариях."
            ),
            "urgent": (
                "Внимание: {topic} — приоритет на ближайшие 48 часов. "
                "В деле? Оставь комментарий."
            ),
            "celebratory": (
                "Сильная неделя по {topic}. Горжусь командой. "
                "Отметь того, кто помог."
            ),
        },
        "tg": {
            "warm": (
                "Короткий апдейт — {topic}. Ответь одним успехом и одной "
                "проблемой. Синхронимся в 18:00."
            ),
            "professional": (
                "Апдейт по {topic}. Подробности в следующем сообщении. "
                "Синк в 18:00."
            ),
            "urgent": (
                "Срочно: {topic}. Ответы нужны до 17:00. "
                "Да/Нет — этого достаточно, детали потом."
            ),
            "celebratory": (
                "{topic} — готово. Скоро пришлю «доказательства». "
                "Дебрифим в 18:00."
            ),
        },
        "wa": {
            "warm": (
                "Привет! Делюсь заметкой по {topic}. "
                "60 секунд — и ответь ✅ если полезно."
            ),
            "professional": (
                "Привет, отправляю дневной апдейт по {topic}. "
                "Подтверди коротким ответом."
            ),
            "urgent": (
                "Быстро — {topic} требует внимания сегодня. "
                "Ответь сразу, если нужна помощь."
            ),
            "celebratory": (
                "Хочу поделиться победой: {topic}. ✅ если увидел, "
                "разберём на завтрашнем созвоне."
            ),
        },
        "linkedin": {
            "warm": (
                "Мысль про {topic}. Делюсь тем, что попробовали, "
                "что сработало и что нет — рад комментариям."
            ),
            "professional": (
                "Заметки по {topic}. Три наблюдения из практики, "
                "одно решение, которое изменили. Что видите вы?"
            ),
            "urgent": (
                "{topic} — стоит присмотреться на этой неделе. "
                "Сместили фокус сюда; готов сравнить наблюдения."
            ),
            "celebratory": (
                "Веха: {topic}. Команде — отдельное спасибо. "
                "Подробности отдельным постом."
            ),
        },
    },
    "es": {
        "ig": {
            "warm": (
                "Tres cosas esta semana: tracción, aprendizaje y {topic}. "
                "Etiqueta a alguien que vaya en la misma dirección."
            ),
            "professional": (
                "Actualización sobre {topic}. Las métricas van bien. "
                "Lo que funcionó está en los comentarios."
            ),
            "urgent": (
                "Atención: {topic} es la prioridad de las próximas 48h. "
                "Si te sumas, deja un comentario."
            ),
            "celebratory": (
                "Semana grande para {topic}. Orgullo del equipo. "
                "Etiqueta a quien te empujó."
            ),
        },
        "tg": {
            "warm": (
                "Actualización rápida — {topic}. Responde con una victoria "
                "y un bloqueo. Sincronizamos a las 18:00."
            ),
            "professional": (
                "Update sobre {topic}. Detalles en el siguiente mensaje. "
                "Sincronización a las 18:00."
            ),
            "urgent": (
                "Cambio de prioridad: {topic}. Respuestas antes de las 17:00. "
                "Sí/No basta — detalles después."
            ),
            "celebratory": (
                "{topic} — hecho. Pruebas en el siguiente mensaje. "
                "Debrief a las 18:00."
            ),
        },
        "wa": {
            "warm": (
                "¡Hola! Comparto la nota del día sobre {topic}. "
                "60s y responde ✅ si te sirve."
            ),
            "professional": (
                "Hola, envío el daily de {topic}. "
                "Confirma con una respuesta rápida."
            ),
            "urgent": (
                "Rápido — {topic} necesita atención hoy. "
                "Responde ya si necesitas ayuda."
            ),
            "celebratory": (
                "Victoria para compartir: {topic}. ✅ si lo viste; "
                "lo desglosamos mañana en la call."
            ),
        },
        "linkedin": {
            "warm": (
                "Una reflexión sobre {topic}. Comparto lo que intentamos, "
                "lo que funcionó y lo que no — abro comentarios."
            ),
            "professional": (
                "Notas sobre {topic}. Tres observaciones de campo, "
                "una decisión que cambiamos. ¿Qué ven ustedes?"
            ),
            "urgent": (
                "{topic} — vale la pena mirar esta semana. "
                "Estamos enfocados ahí; encantado de comparar notas."
            ),
            "celebratory": (
                "Hito: {topic}. Crédito al equipo detrás. "
                "Comparto el playbook en un post de seguimiento."
            ),
        },
    },
}


_DEFAULT_CTAS: dict[str, dict[str, str]] = {
    "en": {
        "warm": "Reply with your take.",
        "professional": "Open to a quick exchange — DM me.",
        "urgent": "Reply by EOD.",
        "celebratory": "Tag the person who made it possible.",
    },
    "ru": {
        "warm": "Поделись мнением.",
        "professional": "Открыт к обмену — пиши в личку.",
        "urgent": "Ответ к концу дня.",
        "celebratory": "Отметь того, кто помог.",
    },
    "es": {
        "warm": "Comparte tu opinión.",
        "professional": "Abierto a intercambiar ideas — escríbeme.",
        "urgent": "Respuesta antes del fin del día.",
        "celebratory": "Etiqueta a quien lo hizo posible.",
    },
}


def _format_overlay(format_: str, draft: str) -> str:
    """Light, format-aware tweak on top of the channel/tone template.

    ``story`` adds an engagement hook; ``reel`` collapses to a
    punchier two-line read; ``dm`` strips the trailing CTA so the
    operator can drop the message into a 1:1 chat without sounding
    like a broadcast.
    """

    if format_ == "story":
        return draft + " Swipe up if you're in."
    if format_ == "reel":
        # Take the first sentence + a short close.
        first = re.split(r"(?<=[.!?])\s+", draft, maxsplit=1)[0]
        return f"{first} 👀"
    if format_ == "dm":
        # Trim the broadcast-y close (anything past the first sentence).
        first = re.split(r"(?<=[.!?])\s+", draft, maxsplit=1)[0]
        return first
    return draft


def _coerce(value: Any, allowed: tuple[str, ...], default: str) -> str:
    if not isinstance(value, str):
        return default
    s = value.strip().lower()
    return s if s in allowed else default


def _slugify_topic(topic: str) -> str:
    """Lower-case, ASCII-only, hyphen-separated tag stem.

    Used for hashtags so the operator doesn't end up with weird
    cyrillic / accented hash symbols on a russian/spanish post —
    real ig/linkedin clients don't mind those, but mixing scripts
    in tags makes the cockpit preview ugly. Falls back to ``topic``
    if no ASCII stems survive.
    """

    cleaned = re.sub(r"[^a-zA-Z0-9\s_-]", "", topic).strip().lower()
    return re.sub(r"[\s_]+", "-", cleaned)


def _hashtags_for(channel: str, topic: str) -> tuple[str, ...]:
    if channel not in {"ig", "linkedin"}:
        return ()
    base = ("#momentum", "#team")
    slug = _slugify_topic(topic)
    if slug:
        base = base + ("#" + slug.replace("-", ""),)
    if channel == "linkedin":
        base = base + ("#leadership", "#growth")
    seen: list[str] = []
    for tag in base:
        if tag not in seen:
            seen.append(tag)
        if len(seen) >= 8:
            break
    return tuple(seen)


def draft_post(args: Mapping[str, Any]) -> PostDraft:
    """Render a :class:`PostDraft` from a loose ``args`` mapping.

    Unknown enum values fall back to defaults so the caller can be
    sloppy about input. Topic falls back to ``"team momentum"``.
    """

    channel = _coerce(args.get("channel"), KNOWN_CHANNELS, "ig")
    format_ = _coerce(args.get("format"), KNOWN_FORMATS, "post")
    tone = _coerce(args.get("tone"), KNOWN_TONES, "warm")
    language = _coerce(args.get("language"), KNOWN_LANGUAGES, "en")

    topic_raw = args.get("topic")
    topic = (str(topic_raw).strip() if topic_raw else "") or DEFAULT_TOPIC

    template = _TEMPLATES[language][channel][tone]
    draft = template.format(topic=topic)
    draft = _format_overlay(format_, draft)

    cta_raw = args.get("cta")
    cta = (
        str(cta_raw).strip()
        if isinstance(cta_raw, str) and cta_raw.strip()
        else _DEFAULT_CTAS[language][tone]
    )

    hashtags = _hashtags_for(channel, topic)

    word_count = len(re.findall(r"\b\w+\b", draft))
    char_count = len(draft)

    return PostDraft(
        channel=channel,
        format=format_,
        tone=tone,
        language=language,
        topic=topic,
        draft=draft,
        cta=cta,
        hashtags=hashtags,
        char_count=char_count,
        word_count=word_count,
    )


__all__ = [
    "DEFAULT_TOPIC",
    "KNOWN_CHANNELS",
    "KNOWN_FORMATS",
    "KNOWN_LANGUAGES",
    "KNOWN_TONES",
    "PostDraft",
    "draft_post",
]
