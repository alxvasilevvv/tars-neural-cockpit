# TARS voice surface

Persona-aware text-to-speech with three provider tiers and a
diagnostic endpoint that reports which voice each persona would
*actually* use right now.

## Provider chain

The `synthesize()` orchestrator walks this fallback chain in order;
the first provider that is `is_available()` and that the persona has a
voice configured for wins.

| # | Provider     | Auth                                           | Cost band      | Notes                                              |
|---|--------------|------------------------------------------------|----------------|----------------------------------------------------|
| 1 | `elevenlabs` | `ELEVENLABS_API_KEY` / `TARS_ELEVENLABS_API_KEY` | high           | best character voices; per-persona voice IDs       |
| 2 | `openai`     | `OPENAI_API_KEY` / `TARS_OPENAI_API_KEY`         | mid            | `gpt-4o-mini-tts` honours `instructions` styling   |
| 3 | `mac_say`    | none                                           | free / offline | `/usr/bin/say`; macOS-only; per-persona voice name |

Pin a single provider with `TARS_VOICE_PROVIDER=<name>` (env) or by
passing `provider` in the `/api/voice/speak` body. Unknown values are
attempted standalone (no fallback) so plugin packs can register custom
engines without forcing them through the auto chain.

## Endpoints

### `GET /api/voice/personas`

Stable roster shape — six default personas (`jarvis`, `stark`,
`hal9000`, `glados`, `tars`, `operator`) plus their per-provider
hints. Other clients (cockpit picker, plugin packs) read this; **its
shape is frozen**.

### `GET /api/voice/personas/effective` *(W295, diagnostic)*

Pure read-only. Reports, per persona, the provider + voice id that
`synthesize()` would resolve to under the current env / engine
state. No audio is synthesised, no cloud spend, no entitlement gate.
Safe to expose anywhere `/health` is exposed.

Sample response (truncated to two personas):

```json
{
  "ok": true,
  "count": 6,
  "default_persona_id": "jarvis",
  "providers_available": {
    "elevenlabs": true,
    "openai": false,
    "mac_say": true
  },
  "provider_chain": ["elevenlabs", "openai", "mac_say"],
  "personas": [
    {
      "id": "jarvis",
      "name": "J.A.R.V.I.S.",
      "character": "Stark Industries household AI · British butler · calm, precise.",
      "accent": "british",
      "locale": "en-GB",
      "license_note": "Inspired by the J.A.R.V.I.S. archetype; ...",
      "effective_provider": "elevenlabs",
      "effective_voice_id": "onwK4e9ZLuTAKqWW03F9",
      "voice_id": "onwK4e9ZLuTAKqWW03F9",
      "effective_mac_say_voice": "Daniel",
      "fallback_chain": ["elevenlabs", "openai", "mac_say"],
      "providers": {
        "elevenlabs": "onwK4e9ZLuTAKqWW03F9",
        "openai": "fable",
        "mac_say": "Daniel"
      }
    },
    {
      "id": "tars",
      "name": "TARS",
      "character": "Interstellar TARS — measured American baritone, dry humour.",
      "accent": "american",
      "locale": "en-US",
      "effective_provider": "elevenlabs",
      "effective_voice_id": "JBFqnCBsd6RMkjVDRZzb",
      "voice_id": "JBFqnCBsd6RMkjVDRZzb",
      "effective_mac_say_voice": "Tom",
      "fallback_chain": ["elevenlabs", "openai", "mac_say"],
      "providers": {
        "elevenlabs": "JBFqnCBsd6RMkjVDRZzb",
        "openai": "ash",
        "mac_say": "Tom"
      }
    }
  ]
}
```

#### Why a separate endpoint?

`/api/voice/personas` returns the *static* registry — every voice id
the persona declares for every provider, regardless of what's
reachable on this machine. The cockpit picker and plugin packs need
that. The W290 acceptance harness, on the other hand, needs to know
which voice would *actually* be played, which depends on env keys,
running OS, and installed `say` voices. Mixing the two into one
endpoint would either break the static contract or hide the live
resolution.

The `effective_voice_id` field is the canonical one for the
diagnostic case (it contains the voice id of the chosen provider).
The `voice_id` alias is preserved for legacy harnesses that look it
up directly.

#### Harness usage

`scripts/qa_w290_cockpit.sh` Group 9 calls this endpoint and asserts
that the four male personas (`jarvis`, `stark`, `hal9000`, `tars`)
resolve to four *distinct* `effective_voice_id` values. This catches
two regressions in one shot:

1. The static voice IDs in the persona registry collapsing onto the
   same value (a copy-paste bug we fixed in W144).
2. The mac_say `_pick_fallback_voice` chain landing every American
   persona on the same fallback voice when their preferred voice is
   missing (a Linux/CI-only failure mode that previously hid until
   real synthesis).

The harness asserts uniqueness in **both** the cloud path
(`ELEVENLABS_API_KEY` set → 4 distinct ElevenLabs voice IDs) and the
offline path (no cloud keys → 4 distinct mac_say voice names).

#### Why no entitlement gate?

`/api/voice/speak` calls `require_cloud_budget()` because synthesis
is cloud-billed at ~$0.18 / 1k chars on ElevenLabs. The diagnostic
endpoint never invokes a synthesiser — it only reads cached
availability flags from each engine — so no spend can land. We keep
the gate off so a FREE-tier operator can still see what their
cockpit *would* sound like before deciding to upgrade.

### `POST /api/voice/speak`

Synthesis with full meeet-bridge tracing + the cloud-budget gate.
See `web_extras/routers/voice.py` for the full envelope.

### `GET /api/voice/health`

Engine availability snapshot (`elevenlabs`, `openai`, `mac_say`)
plus the STT readiness flag.

### `POST /api/voice/transcribe`

Whisper-backed STT (W229).

## Persona registry

`backend/core/voice/personas.py` — six characters ship by default
(Jarvis, Stark, HAL 9000, GLaDOS, Interstellar TARS, Operator). Each
persona declares per-provider hints; env overrides exist for every
voice id (`TARS_PERSONA_<ID>_<KEY>`). Plugin packs may register
extra personas via `register_persona()`.

The four "male" personas used by the W290 harness all carry distinct
defaults across every provider tier:

| Persona  | ElevenLabs voice ID    | OpenAI voice | macOS `say` voice |
|----------|------------------------|--------------|-------------------|
| jarvis   | `onwK4e9ZLuTAKqWW03F9` | `fable`      | `Daniel`          |
| stark    | `pNInz6obpgDQGcFmaJgB` | `onyx`       | `Aaron`           |
| hal9000  | `VR6AewLTigWG4xSOukaG` | `echo`       | `Bruce`           |
| tars     | `JBFqnCBsd6RMkjVDRZzb` | `ash`        | `Tom`             |
