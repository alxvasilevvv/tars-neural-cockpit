# Video transcripts — design references

Transcripts of the design/instruction videos shared by the user. Source
videos remain in `~/Downloads/`; they are not committed to the repo.

Transcribed locally with `faster-whisper small` (offline, int8 on CPU)
via `imageio-ffmpeg` for audio extraction. Language detected
automatically.

---

## 433d7195d4f34e84b8a52cfe28924a62.MP4

- Duration: 38.9s
- Language: ru (probability 1.00)
- Source: `/Users/alien/Downloads/433d7195d4f34e84b8a52cfe28924a62.MP4`

```
[00:00.00 → 00:02.60] Я только что создал сайт за 10 тысяч долларов с помощью
[00:02.60 → 00:03.60] одной строки кода.
[00:03.60 → 00:05.52] Вот как это сделать?
[00:05.52 → 00:06.52] Всего четыре шага.
[00:06.52 → 00:07.88] Первое — установить Claude Code.
[00:07.88 → 00:11.28] Перейдите по ссылке, скопируйте команду и вставьте её в терминал.
[00:11.28 → 00:13.64] Второе — установить Framer Motion для анимации.
[00:13.64 → 00:16.60] Перейдите по ссылке, скопируйте команду и вставьте в терминал.
[00:16.60 → 00:21.44] Третье — скачайте UI/UX Pro Max Skill, попросите Claude установить его.
[00:21.44 → 00:25.92] Четвёртое — зайдите на сайт 21st.dev, скопируйте строку и вставьте её в код.
[00:25.92 → 00:29.20] После этого вы сможете создавать профессиональные сайты вот такого уровня.
[00:29.20 → 00:34.08] И самое главное — я сделал это ещё проще, создав пошаговую инструкцию,
                       где собраны все шаги.
[00:34.08 → 00:36.56] Напиши слово «инструкция» в комментарии, я пришлю вам ссылку.
```

### How TARS implements this instruction

| Step | Status | Where |
|------|--------|-------|
| 1. Install Claude Code | ✅ done | `npm i -g @anthropic-ai/claude-code` (v2.1.121). |
| 2. Install Framer Motion | ✅ done | `experiments/neural-showcase-v3/package.json`. |
| 3. Install ui-ux-pro-max-skill | ✅ done | `~/.claude/skills/ui-ux-pro-max/` (Claude Code) and `.cursor/skills/ui-ux-pro-max/` in TARS + meeet-browser-agent (Cursor). |
| 4. Drop a 21st.dev component | ⏳ ready | `experiments/neural-showcase-v3/components.json` is configured for `npx shadcn add "https://21st.dev/r/<author>/<id>"`. User picks the specific block. |

---

## aac4ddb9854f470f8dbbae61291984fb.MP4 / b68f53a86d67450c936cb88b7ed20627.MP4

These earlier videos are visual references (no spoken instructions
relevant for setup). They remain in `~/Downloads/` for inspection.
Transcribe on demand with the same tooling:

```bash
FFMPEG=$(/Users/alien/Documents/Claude/Projects/Jarvis/jarvis/.venv/bin/python -c "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())")
"$FFMPEG" -y -hide_banner -loglevel error -i ~/Downloads/<id>.MP4 -ar 16000 -ac 1 -f wav /tmp/<id>.wav
/Users/alien/Documents/Claude/Projects/Jarvis/jarvis/.venv/bin/python /tmp/tars-transcribe/run.py /tmp/<id>.wav small
```
