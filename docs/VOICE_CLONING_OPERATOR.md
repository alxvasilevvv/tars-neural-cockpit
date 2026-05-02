# Operator guide — custom voice (ElevenLabs IVC)

TARS ships built-in personas (`backend.core.voice`); this note is for
operators who want a **cloned** voice via ElevenLabs **Instant Voice
Clone** (IVC) and wire it into the vault.

## Prerequisites

- ElevenLabs account with API access and a quota for IVC / voice library.
- Local TARS with vault configured (`docs/SECOND_MACHINE_HANDOFF.md`).

## Capture (≈3 minutes)

1. Record **clean** speech in a quiet room: **44.1 kHz or 48 kHz** WAV
   or high-bitrate M4A. Aim for **≥ 1 minute**, ideally **2–3 minutes**
   of continuous, varied prosody (questions, statements, numbers), no
   background music.
2. Normalise levels offline (avoid clipping; peak around **-6 dBFS**).
3. Do **not** ship raw audio in the repo — keep samples in a private
   disk location only.

## Mint the IVC on ElevenLabs

1. In the ElevenLabs dashboard, create an **Instant Voice Clone** from
   the prepared file; wait until the voice is **ready** (dashboard shows
   active).
2. Copy the **voice id** (string) from the voice settings page.

## Bind into TARS

Set the operator persona env knob (see `docs/IDEAS.md` → Voice cloning):

```bash
export TARS_PERSONA_OPERATOR_ELEVENLABS_ID="<voice_id_from_dashboard>"
```

Prefer storing the **API key** in the macOS Keychain / vault, not in
shell history; the ElevenLabs **voice id** is non-secret but keeping it
in `.env` keeps machine profiles consistent.

Restart the backend / desktop shell so `POST /api/voice/speak` picks up
the new default provider mapping for the operator persona.

## Verify

1. Cockpit → voice controls → **speak** a short test line.
2. Watch `GET /api/vault/status` — ElevenLabs should show as a
   configured source (key present), never echoing the secret.
3. Optional: tail meeet store / trace viewer for `usage.tokens` on TTS.

## Troubleshooting

| Symptom | Check |
|--------|--------|
| 401 from ElevenLabs | API key in vault / env; clock skew. |
| Voice id rejected | Id copied from **clone** not from a legacy voice that needs different API. |
| Silent audio in browser | Output device, autoplay policy, `useVoicePlayback` errors in console. |

When ElevenLabs changes API shapes, update the adapter in
`backend/core/voice/` (Cursor lane) — this doc stays procedural only.
