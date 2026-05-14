# TARS v10.0.0-rc.1 — Demo Cheat Sheet

**One page. Print it. Tape it next to the laptop.**

---

## 1. Pre-demo checklist (T-15 minutes)

- [ ] `TARS.app` open · monolith breathing · sidecar dot **green**
- [ ] `TARS_DEMO_SEED=1` in `.env` · fixtures loaded (USAGE shows 30 receipts)
- [ ] `./scripts/LAUNCH-NOW.command` ran clean · port 8765 alive
- [ ] `./scripts/REBUILD-TARS-APP.command` last build < 24h old
- [ ] `LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY` set
- [ ] Wi-Fi confirmed · Gmail OAuth still valid
- [ ] `Cmd+Shift+Space` global shortcut tested twice
- [ ] Audio: mic input level green · speakers at 60%
- [ ] Browser tab open: Gmail Drafts (proves slide 6 step 4)
- [ ] Phone on silent · airplane mode optional but recommended

---

## 2. The 5-step demo flow

| # | Time | What you do | What you SAY | Wow moment |
|---|------|-------------|---------------|-----------|
| 1 | ~3s  | `Cmd+Shift+Space` | "Watch the monolith come alive." | Cyan strip charges bottom→top |
| 2 | ~8s  | Speak the prompt | **"Compose a thank-you to last week's investors."** | STT waveform pulses, router picks Composer |
| 3 | ~15s | Wait for diff | "Notice — Composer knows the **Entrepreneur** pack vocabulary." | Multi-file diff, domain-pack aware |
| 4 | ~10s | Click **Accept hunks** | "Real OAuth. Real Gmail draft. No mocks." | Switch to Gmail tab — draft visible |
| 5 | ~5s  | Open **Audit Explorer** | "Hash-chained. Solana-anchors tonight." | Receipt #1284 live with green checkmark |

**Total: ~45 seconds. Land it at 60 max.**

---

## 3. Backup plans

| If this fails | Do this |
|---------------|---------|
| Sidecar dot red | `./scripts/LAUNCH-NOW.command` from Terminal — recovers in ~8s |
| `Cmd+Shift+Space` does nothing | Click TARS.app in dock to focus, retry the shortcut |
| STT mis-hears the phrase | Type into the composer text fallback below the mic. Same outcome. |
| Composer panel won't open | Run command manually: `tars compose "thank-you to investors"` — same diff |
| Gmail OAuth expired | Skip step 4. Show the diff preview. Say "the draft would land in Gmail." |
| Audit Explorer empty | Force-seed: `TARS_DEMO_SEED=1 ./scripts/SEED-DEMO.command` then refresh |
| **Hard fail** (TARS won't start) | Skip to slide 12 screenshots. Treat them as the demo. Don't apologize. |

---

## 4. Q&A — 5 anticipated questions

| Q | One-line answer |
|---|-----------------|
| **"What if Cursor enters this market?"** | Cursor is a VS Code fork — extending to non-devs is a 12-month product redirect, not a 12-week project. |
| **"Why local-first if inference is cloud anyway?"** | Data plane separation: receipts, memory, index all on disk. Inference is the only network egress, and BYO key. |
| **"Is $MEEET a security?"** | Utility token for compute on the relayer. Opt-in day one. On-prem buyers never touch it. |
| **"What's the moat if inference gets free?"** | Cockpit + receipts + marketplace + per-user style. Cheap inference helps us asymmetrically. |
| **"Why hasn't an incumbent built this?"** | Anthropic/OpenAI ship chat. Microsoft Copilot is wired into Office. None ship voice + local + receipts + 7 packs together. |

---

## 5. Closing line (don't improvise)

> "Cursor did this for code. We're doing this for everything else. v10 ships tomorrow."

**Then stop talking.** First audience question tells you what landed.

---

## 6. After the demo

- [ ] Screenshot the audit ledger (proof receipt for the room)
- [ ] Note questions asked → input to v10.1 roadmap
- [ ] Hand out one-pager + leave-behind PDF (`TARS_v10.0_PRESENTATION.pdf`)
- [ ] Follow up within 24h with the recording link

---

**Contact during the demo:** alienram@icloud.com  ·  meeet.world  ·  github.com/alienram/jarvis
