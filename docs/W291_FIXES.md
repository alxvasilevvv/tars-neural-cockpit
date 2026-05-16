# W291 — TARS не отвечает / голоса не работают — fix bundle

## Что было сломано

1. **Голос приветствия — НЕ ElevenLabs.**
   `ttfvSpeak` обращался напрямую к `window.speechSynthesis` (системный голос macOS), минуя backend и ElevenLabs Adam.
   *Симптом:* "голоса по API не работают" — звучал системный голос, а не Adam.

2. **Приветствие срабатывало только один раз — навсегда.**
   `ttfvMaybeStart` читает `localStorage.tars_first_launch_done`. Один раз поставил `'1'` — и приветствие больше никогда не запускается, пока не сбросить флаг руками.
   *Симптом:* "приветственного сообщения нет" — флаг уже был установлен с прошлых сессий.

3. **Backend на :8765 мог быть offline.**
   `_dispatchTranscript` молча возвращал "Dispatch failed: ..." в transcript area. Пользователь видел "TARS не отвечает".

4. **WKWebView localStorage переживает переустановку .app.**
   Контейнер `~/Library/Containers/world.meeet.tars/` сохраняется между билдами. Сброс `~/.tars/state.json` (мой W289 фикс) не помогал — это другое хранилище.

## Что починено в W291

### Frontend (`desktop/src-tauri/web/index.html`)

- `ttfvSpeak` → теперь идёт через `_speak()` → `/api/a11y/speak` → ElevenLabs Adam. С graceful fallback на browser TTS если backend недоступен или ElevenLabs вернул `use_browser_tts:true`.
- `ttfvMaybeStart` → respect `?demo=1` query param и `localStorage.tars_demo_mode='1'`. В demo-режиме приветствие играется на каждом запуске.
- `window.tarsReplayGreeting()` → публичный helper, очищает флаги и перезапускает welcome tour.
- `_w291ProbeBackend()` → запускается на каждом `showCockpit()`, выводит в transcript area конкретные жалобы: backend down / ElevenLabs off / `/api/voice/command` 404.
- **Cmd+Shift+R** → перепроиграть приветствие.
- **Cmd+Shift+B** → перепроверить backend и показать что сломано.

### Build script (`scripts/FORCE-REBUILD-TARS.command`)

- Автоматически проверяет `/api/a11y/health`. Если backend не отвечает — стартует его с правильными env vars из `.env` (включая ELEVENLABS_API_KEY).
- Также запускает meeet mock на :8766 если он не работает (нужен для OAuth flow).
- Очищает `~/Library/Containers/world.meeet.tars/Data/Library/WebKit/WebsiteData/LocalStorage/` перед запуском → приветствие точно сыграет при первом запуске после rebuild.
- Печатает явно: "ElevenLabs active: yes/no" — видно из терминала.

## Acceptance test после rebuild

1. Двойной клик по `scripts/FORCE-REBUILD-TARS.command`.
2. В терминале должно появиться: `ElevenLabs active: yes`.
3. После запуска приложения и "Continue local-only →":
   - Должно зазвучать приветствие **голосом Adam** (не системный).
   - В transcript area не должно быть жёлтых предупреждений `⚠`.
4. Печатаем "hello" в текстовое поле → Enter → ответ TARS + голос Adam.
5. Клик по микрофону → "Listening..." → говорим → транскрипция → ответ.

## Если что-то всё ещё не работает

- Открой DevTools (правый клик в окне → Inspect) → Console → смотри ошибки.
- Cmd+Shift+B → переоценка backend.
- В терминале `tail -f .TARS-BACKEND.txt` → видеть запросы в реальном времени.
