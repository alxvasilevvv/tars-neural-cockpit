"""Telegram outreach drafter (deterministic).

Closes the ``mlm.tg_outreach_draft`` slot from IDEAS' real-
adapters list. The action takes structured intent / tone /
language / signature inputs and produces a Telegram-flavoured
markdown draft plus a plain-text fallback, ready for the
operator to review and send manually. **Never auto-sends** —
this is a preview surface only.

Templates live in this module so a single edit fans out to every
draft. They are deterministic by design (no LLM, no I/O) so
playbooks can chain `tg_outreach_draft` between awareness
snapshots and ``mlm.retention_round``-style recommendations
without paying a model round-trip.

Languages
---------

EN (default), RU, ES — three first-class locales because the
existing operator mix sits on those. Adding a language is one
dict entry per intent; missing keys silently fall back to EN.

Intents
-------

- ``welcome``  — onboard a fresh recruit.
- ``checkin``  — light-touch stay-in-contact.
- ``winback``  — re-engage someone gone quiet.
- ``recruit``  — first cold-ish outreach.
- ``celebrate``— call out a milestone.
- ``upsell``   — pitch a paid step-up to an existing member.

Tones
-----

- ``warm`` (default), ``direct``, ``celebratory``. Each tone
  picks an opener / closer style so the same intent reads
  differently across operator personas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


KNOWN_INTENTS: tuple[str, ...] = (
    "welcome",
    "checkin",
    "winback",
    "recruit",
    "celebrate",
    "upsell",
)
KNOWN_TONES: tuple[str, ...] = ("warm", "direct", "celebratory")
KNOWN_LANGUAGES: tuple[str, ...] = ("en", "ru", "es")
DEFAULT_LANGUAGE = "en"
DEFAULT_TONE = "warm"

MAX_CTA_CHARS = 140
MAX_NAME_CHARS = 80
MAX_DRAFT_CHARS = 4096  # Telegram message limit


# ---------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class OutreachDraft:
    ok: bool
    intent: str
    tone: str
    language: str
    recipient: str
    cta: str
    markdown: str = ""
    plain_text: str = ""
    subject_hint: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    length_chars: int = 0
    error: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ok": self.ok,
            "intent": self.intent,
            "tone": self.tone,
            "language": self.language,
            "recipient": self.recipient,
            "cta": self.cta,
            "markdown": self.markdown,
            "plain_text": self.plain_text,
            "subject_hint": self.subject_hint,
            "tags": list(self.tags),
            "length_chars": self.length_chars,
            # Mirrored on every response so the cockpit doesn't have to
            # know about the secondary "no-auto-send" promise.
            "send_status": "draft",
        }
        if self.error is not None:
            body["error"] = self.error
        if self.detail is not None:
            body["detail"] = self.detail
        return body


# ---------------------------------------------------------------------
# Template tables
# ---------------------------------------------------------------------


# Each (intent, language) maps to:
#   - openers: keyed by tone
#   - body: a single sentence (or ${cta} substitution)
#   - closers: keyed by tone
#   - subject_hint: short label for the cockpit / channel pin
#   - tags: hashtag suggestions
_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    "welcome": {
        "en": {
            "openers": {
                "warm": "Welcome aboard, {name}! Glad you joined the team.",
                "direct": "Welcome, {name}. Quick onboarding steps below.",
                "celebratory": "🎉 Welcome, {name}! Excited to have you with us.",
            },
            "body": (
                "Here is what helps in the first week — set a 15-minute "
                "intro call, finish your profile, and pick one daily "
                "rep you can hold for 30 days."
            ),
            "closers": {
                "warm": "Reply when you've picked your rep — I'll match you with a buddy.",
                "direct": "Reply with your rep choice and I'll lock the buddy match.",
                "celebratory": "Tell me your rep and I'll pair you with the perfect partner!",
            },
            "subject_hint": "Welcome / first week",
            "tags": ("welcome", "onboarding", "team"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}! Рад, что ты с нами.",
                "direct": "Привет, {name}. Краткий онбординг ниже.",
                "celebratory": "🎉 Поздравляю, {name}! Очень рад видеть тебя в команде.",
            },
            "body": (
                "В первую неделю помогают три шага: 15-минутный созвон, "
                "оформление профиля и одна ежедневная задача, которую "
                "ты выдержишь 30 дней."
            ),
            "closers": {
                "warm": "Напиши свой выбор задачи — подберу напарника.",
                "direct": "Назови задачу — закреплю напарника.",
                "celebratory": "Назови задачу, и я найду тебе идеального партнёра!",
            },
            "subject_hint": "Онбординг / первая неделя",
            "tags": ("welcome", "onboarding", "team"),
        },
        "es": {
            "openers": {
                "warm": "¡Bienvenido, {name}! Me alegra que te unas al equipo.",
                "direct": "Bienvenido, {name}. Pasos de onboarding abajo.",
                "celebratory": "🎉 ¡Bienvenido, {name}! Genial tenerte aquí.",
            },
            "body": (
                "En la primera semana ayudan tres pasos: una llamada de "
                "15 minutos, completar tu perfil y elegir una práctica "
                "diaria que mantengas 30 días."
            ),
            "closers": {
                "warm": "Cuéntame tu práctica y te asigno un compañero.",
                "direct": "Dime tu práctica y cierro el match con tu compañero.",
                "celebratory": "¡Cuéntame tu práctica y te empareja con un partner!",
            },
            "subject_hint": "Bienvenida / primera semana",
            "tags": ("welcome", "onboarding", "team"),
        },
    },
    "checkin": {
        "en": {
            "openers": {
                "warm": "Hey {name}, just a quick check-in.",
                "direct": "{name}, quick check-in.",
                "celebratory": "Hey {name}! Hope your week's been a great one.",
            },
            "body": (
                "How are this week's reps going? One sentence on what's "
                "working and one on what's stuck is enough."
            ),
            "closers": {
                "warm": "Reply when you have a sec — happy to brainstorm anything sticky.",
                "direct": "Send me both lines — I'll suggest a fix for what's stuck.",
                "celebratory": "Drop me both lines and I'll cheer you across the line!",
            },
            "subject_hint": "Weekly check-in",
            "tags": ("checkin", "team"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}, короткий чек-ин.",
                "direct": "{name}, чек-ин.",
                "celebratory": "Привет, {name}! Надеюсь, неделя проходит мощно.",
            },
            "body": (
                "Как идут задачи на этой неделе? Одна строка о том, что "
                "работает, и одна — что застряло."
            ),
            "closers": {
                "warm": "Напиши, когда будет минута — придумаем как разрулить застрявшее.",
                "direct": "Скинь обе строки — предложу шаг по застрявшему.",
                "celebratory": "Жду две строки — поддержу и предложу решение!",
            },
            "subject_hint": "Еженедельный чек-ин",
            "tags": ("checkin", "team"),
        },
        "es": {
            "openers": {
                "warm": "Hola {name}, un check-in rápido.",
                "direct": "{name}, check-in.",
                "celebratory": "¡Hola {name}! Espero que tu semana esté siendo fenomenal.",
            },
            "body": (
                "¿Cómo van las prácticas de esta semana? Una línea con "
                "lo que funciona y otra con lo que está atascado."
            ),
            "closers": {
                "warm": "Cuando tengas un momento, lo desbloqueamos juntos.",
                "direct": "Mándame las dos líneas y te sugiero un próximo paso.",
                "celebratory": "¡Cuéntame y celebro contigo el avance!",
            },
            "subject_hint": "Check-in semanal",
            "tags": ("checkin", "team"),
        },
    },
    "winback": {
        "en": {
            "openers": {
                "warm": "Hey {name}, been a while — thinking of you.",
                "direct": "{name}, you've been quiet — what's up?",
                "celebratory": "Hey {name}! Missed you — what's the latest?",
            },
            "body": (
                "If life took the wheel for a stretch, that's fine. The "
                "team kept moving and there are easy ways to slot back "
                "in without restarting from zero."
            ),
            "closers": {
                "warm": "Open to a 10-minute catch-up this week?",
                "direct": "Reply 'yes' and I'll send a 10-minute slot.",
                "celebratory": "Hit me back and let's pick a fun re-entry plan!",
            },
            "subject_hint": "Win-back / re-entry",
            "tags": ("winback", "retention"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}, давно не виделись — думал о тебе.",
                "direct": "{name}, ты пропал(а) — всё ок?",
                "celebratory": "Привет, {name}! Скучал — как дела?",
            },
            "body": (
                "Если жизнь забрала на время — это нормально. Команда "
                "движется, и есть лёгкий способ вернуться без старта "
                "с нуля."
            ),
            "closers": {
                "warm": "Готов(а) к 10-минутному созвону на этой неделе?",
                "direct": "Ответь «да» — пришлю слот на 10 минут.",
                "celebratory": "Напиши, и придумаем тебе классное возвращение!",
            },
            "subject_hint": "Возвращение",
            "tags": ("winback", "retention"),
        },
        "es": {
            "openers": {
                "warm": "Hola {name}, ha pasado un tiempo — pensaba en ti.",
                "direct": "{name}, has estado en silencio — ¿qué tal?",
                "celebratory": "¡Hola {name}! Te extraño — ¿cómo va todo?",
            },
            "body": (
                "Si la vida te llevó un rato, está bien. El equipo sigue "
                "y hay forma fácil de reincorporarte sin empezar de "
                "cero."
            ),
            "closers": {
                "warm": "¿Te animas a un café virtual de 10 minutos esta semana?",
                "direct": "Responde 'sí' y te paso un slot de 10 minutos.",
                "celebratory": "¡Escríbeme y armamos un regreso divertido!",
            },
            "subject_hint": "Reincorporación",
            "tags": ("winback", "retention"),
        },
    },
    "recruit": {
        "en": {
            "openers": {
                "warm": "Hi {name}, I follow your work — you've been on my mind.",
                "direct": "{name}, quick pitch — 60 seconds, then you decide.",
                "celebratory": "Hi {name}! Loved your recent posts — let's talk.",
            },
            "body": (
                "We are a small team building income on top of skills you "
                "already have. The first week is no money down, just a "
                "fit-check call and one rep."
            ),
            "closers": {
                "warm": "Open to a 15-minute intro call this or next week?",
                "direct": "If yes, reply with two slots and I'll lock one.",
                "celebratory": "If you're curious, send two slots and I'll match the timezone!",
            },
            "subject_hint": "Cold-ish recruit",
            "tags": ("recruit", "outreach"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}, давно слежу за тобой — ты в голове.",
                "direct": "{name}, быстро — 60 секунд, дальше решаешь сам(а).",
                "celebratory": "Привет, {name}! Понравились твои посты — давай поговорим.",
            },
            "body": (
                "Мы небольшая команда, строим доход на навыках, которые "
                "у тебя уже есть. Первая неделя — без вложений, только "
                "звонок-fit-check и одна задача."
            ),
            "closers": {
                "warm": "Готов(а) к 15-минутному созвону на этой или следующей?",
                "direct": "Если да — пришли два слота, поставлю один.",
                "celebratory": "Если интересно — два слота, я подстроюсь под таймзону!",
            },
            "subject_hint": "Холодный набор",
            "tags": ("recruit", "outreach"),
        },
        "es": {
            "openers": {
                "warm": "Hola {name}, sigo tu trabajo — te tengo en mente.",
                "direct": "{name}, pitch rápido — 60 segundos y tú decides.",
                "celebratory": "¡Hola {name}! Me encantaron tus posts — hablemos.",
            },
            "body": (
                "Somos un equipo pequeño que construye ingreso sobre "
                "habilidades que ya tienes. La primera semana es sin "
                "inversión: una llamada de fit y una práctica."
            ),
            "closers": {
                "warm": "¿Te animas a una intro de 15 minutos esta semana o la próxima?",
                "direct": "Si sí, responde con dos slots y cierro uno.",
                "celebratory": "Si te suena, mándame dos slots y ajusto la zona horaria.",
            },
            "subject_hint": "Reclutamiento en frío",
            "tags": ("recruit", "outreach"),
        },
    },
    "celebrate": {
        "en": {
            "openers": {
                "warm": "Hey {name}, just heard the news — congrats.",
                "direct": "{name}, well done.",
                "celebratory": "🎉🥂 {name}! HUGE — congrats!",
            },
            "body": (
                "This kind of result compounds — keep the same daily rep "
                "and protect the momentum on noisy weeks."
            ),
            "closers": {
                "warm": "Drop a one-liner on what unlocked it — others will learn from you.",
                "direct": "One-liner on what unlocked it, please — pinning it for the team.",
                "celebratory": "Tell us what unlocked it — I want to amplify across the team!",
            },
            "subject_hint": "Milestone celebration",
            "tags": ("celebrate", "win", "team"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}, только узнал — поздравляю.",
                "direct": "{name}, красиво.",
                "celebratory": "🎉🥂 {name}! Огромная победа — поздравляю!",
            },
            "body": (
                "Такие результаты складываются — держи ту же "
                "ежедневную задачу и береги темп в шумные недели."
            ),
            "closers": {
                "warm": "Напиши одной строкой, что сработало — команда выучится.",
                "direct": "Одна строка про то, что сработало — закреплю в команде.",
                "celebratory": "Расскажи, что сработало — раскачаю это по команде!",
            },
            "subject_hint": "Поздравление",
            "tags": ("celebrate", "win", "team"),
        },
        "es": {
            "openers": {
                "warm": "Hola {name}, me enteré — ¡felicitaciones!",
                "direct": "{name}, bien hecho.",
                "celebratory": "🎉🥂 ¡{name}! ¡Tremendo — felicitaciones!",
            },
            "body": (
                "Este tipo de resultado compone — mantén la misma "
                "práctica diaria y protege el momentum en semanas "
                "ruidosas."
            ),
            "closers": {
                "warm": "Cuéntame en una línea qué destrabó — el equipo aprende.",
                "direct": "Una línea sobre qué lo destrabó — la fijo para el equipo.",
                "celebratory": "¡Cuéntanos qué lo destrabó y lo amplifico al equipo!",
            },
            "subject_hint": "Logro / hito",
            "tags": ("celebrate", "win", "team"),
        },
    },
    "upsell": {
        "en": {
            "openers": {
                "warm": "Hey {name}, been thinking about your trajectory.",
                "direct": "{name}, fast question — about your next step.",
                "celebratory": "Hey {name}! You're crushing it — let's level up.",
            },
            "body": (
                "Based on what you have already shipped, the next tier "
                "actually pays for itself fast. Want a 1-pager that "
                "shows the math?"
            ),
            "closers": {
                "warm": "Reply '1-pager' and I'll send it over.",
                "direct": "Reply '1-pager' if yes, '✗' if no.",
                "celebratory": "Reply '1-pager' and I'll send the math + a discount code!",
            },
            "subject_hint": "Tier upgrade",
            "tags": ("upsell", "growth"),
        },
        "ru": {
            "openers": {
                "warm": "Привет, {name}, думал о твоей траектории.",
                "direct": "{name}, короткий вопрос — про следующий шаг.",
                "celebratory": "Привет, {name}! Ты на ходу — давай на новый уровень.",
            },
            "body": (
                "Учитывая то, что ты уже отгрузил(а), следующий тариф "
                "окупается быстро. Хочешь one-pager с цифрами?"
            ),
            "closers": {
                "warm": "Ответь «one-pager» — пришлю.",
                "direct": "«one-pager» если да, «✗» если нет.",
                "celebratory": "Ответь «one-pager» — пришлю цифры и промокод!",
            },
            "subject_hint": "Апгрейд тарифа",
            "tags": ("upsell", "growth"),
        },
        "es": {
            "openers": {
                "warm": "Hola {name}, pensaba en tu trayectoria.",
                "direct": "{name}, pregunta corta — sobre el próximo paso.",
                "celebratory": "¡Hola {name}! Vienes con todo — subamos el nivel.",
            },
            "body": (
                "Por lo que ya entregaste, el siguiente tier se paga "
                "rápido. ¿Quieres un one-pager con los números?"
            ),
            "closers": {
                "warm": "Responde 'one-pager' y te lo envío.",
                "direct": "'one-pager' si sí, '✗' si no.",
                "celebratory": "Responde 'one-pager' y te mando números + código!",
            },
            "subject_hint": "Upgrade de tier",
            "tags": ("upsell", "growth"),
        },
    },
}


# ---------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------


_NAME_SAFE_RE = re.compile(r"[\r\n]+")


def _coerce_intent(raw: Any) -> tuple[str | None, str | None]:
    if not isinstance(raw, str):
        return None, "intent_required"
    intent = raw.strip().lower()
    if not intent:
        return None, "intent_required"
    if intent not in KNOWN_INTENTS:
        return None, "invalid_intent"
    return intent, None


def _coerce_tone(raw: Any) -> str:
    if not isinstance(raw, str):
        return DEFAULT_TONE
    tone = raw.strip().lower()
    return tone if tone in KNOWN_TONES else DEFAULT_TONE


def _coerce_language(raw: Any) -> str:
    if not isinstance(raw, str):
        return DEFAULT_LANGUAGE
    lang = raw.strip().lower()
    return lang if lang in KNOWN_LANGUAGES else DEFAULT_LANGUAGE


def _safe_name(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    s = _NAME_SAFE_RE.sub(" ", s)
    return s[:MAX_NAME_CHARS]


def _safe_cta(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    s = _NAME_SAFE_RE.sub(" ", s)
    return s[:MAX_CTA_CHARS]


def _safe_signature(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    s = _NAME_SAFE_RE.sub(" ", s)
    return s[:MAX_NAME_CHARS]


def _format_markdown(
    *, opener: str, body: str, closer: str, signature: str
) -> str:
    """Telegram MarkdownV2 has a tricky escape table — we keep
    the output to *plain* markdown (bold via ``**...**``) so the
    operator can paste it into either MarkdownV2-aware clients
    or a vanilla Telegram chat without surprises.
    """

    parts = [opener, "", body]
    if closer:
        parts.extend(["", closer])
    if signature:
        parts.extend(["", "—", signature])
    return "\n".join(parts).strip()


def _format_plain_text(
    *, opener: str, body: str, closer: str, signature: str
) -> str:
    return _format_markdown(
        opener=opener, body=body, closer=closer, signature=signature
    )


def _safe_template_for(
    intent: str, language: str
) -> tuple[Mapping[str, Any], str]:
    """Resolve a template, falling back to EN for missing
    translations so we never raise on a missing dict key."""

    by_lang = _TEMPLATES.get(intent, {})
    chosen = by_lang.get(language)
    if chosen:
        return chosen, language
    fallback = by_lang.get(DEFAULT_LANGUAGE)
    if fallback:
        return fallback, DEFAULT_LANGUAGE
    return {}, language


async def tg_outreach_draft(args: Mapping[str, Any]) -> Mapping[str, Any]:
    """Action handler.

    Args
    ----
    intent : str (required) — see :data:`KNOWN_INTENTS`.
    name : str (default "") — recipient's display name.
    tone : str (default "warm") — see :data:`KNOWN_TONES`.
    language : str (default "en") — see :data:`KNOWN_LANGUAGES`.
    cta : str (optional) — operator-supplied call-to-action; if
        provided, replaces the default closer.
    signature : str (optional) — signs the draft.
    """

    intent, intent_err = _coerce_intent(args.get("intent"))
    if intent is None:
        return OutreachDraft(
            ok=False,
            intent="",
            tone=DEFAULT_TONE,
            language=DEFAULT_LANGUAGE,
            recipient="",
            cta="",
            error=intent_err or "intent_required",
            detail=(
                "intent must be one of "
                f"{list(KNOWN_INTENTS)}"
                if intent_err == "invalid_intent"
                else None
            ),
        ).to_dict()

    tone = _coerce_tone(args.get("tone"))
    language = _coerce_language(args.get("language"))
    name = _safe_name(args.get("name"))
    cta_override = _safe_cta(args.get("cta"))
    signature = _safe_signature(args.get("signature"))

    template, used_language = _safe_template_for(intent, language)
    openers: Mapping[str, str] = template.get("openers") or {}
    body_template: str = str(template.get("body") or "")
    closers: Mapping[str, str] = template.get("closers") or {}
    subject_hint = str(template.get("subject_hint") or "")
    tags: tuple[str, ...] = tuple(template.get("tags") or ())

    opener_str = str(openers.get(tone) or openers.get(DEFAULT_TONE) or "")
    closer_default = str(
        closers.get(tone) or closers.get(DEFAULT_TONE) or ""
    )
    closer_str = cta_override or closer_default

    rendered_opener = opener_str.format(name=name or "there")

    markdown = _format_markdown(
        opener=rendered_opener,
        body=body_template,
        closer=closer_str,
        signature=signature,
    )
    plain = _format_plain_text(
        opener=rendered_opener,
        body=body_template,
        closer=closer_str,
        signature=signature,
    )

    # Hard cap on length — Telegram drops messages over 4096 chars.
    if len(markdown) > MAX_DRAFT_CHARS:
        return OutreachDraft(
            ok=False,
            intent=intent,
            tone=tone,
            language=used_language,
            recipient=name,
            cta=closer_str,
            error="draft_too_long",
            detail=(
                f"draft is {len(markdown)} chars; Telegram caps at "
                f"{MAX_DRAFT_CHARS}"
            ),
        ).to_dict()

    return OutreachDraft(
        ok=True,
        intent=intent,
        tone=tone,
        language=used_language,
        recipient=name,
        cta=closer_str,
        markdown=markdown,
        plain_text=plain,
        subject_hint=subject_hint,
        tags=tags,
        length_chars=len(markdown),
    ).to_dict()


__all__ = [
    "DEFAULT_LANGUAGE",
    "DEFAULT_TONE",
    "KNOWN_INTENTS",
    "KNOWN_LANGUAGES",
    "KNOWN_TONES",
    "MAX_CTA_CHARS",
    "MAX_DRAFT_CHARS",
    "MAX_NAME_CHARS",
    "OutreachDraft",
    "tg_outreach_draft",
]
