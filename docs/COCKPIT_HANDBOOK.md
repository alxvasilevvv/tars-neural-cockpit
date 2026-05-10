# TARS cockpit handbook — workshop lab edition

> Operator-facing runbook for the **algotrade workshop lab**
> (W4-PR2). Pairs with `docs/ALGOTRADE.md` (architecture) and
> `docs/B2B_WORKSHOP.md` (audience deck).

This handbook documents the end-to-end flow a facilitator runs
during a Cresco-style workshop, from "open the lab" to "publish
the leaderboard". Every step is a single algotrade-pack action
(no special "lab API" — the lab reuses the existing
`sandbox_id` field on every session) so the same flow works
from the cockpit, the CLI, a playbook, or an external MCP
client.

## 1. Before the workshop

1. **Update the algotrade pack** to v0.7.0+ (W4-PR2). Verify in
   the cockpit: Settings → Domains → Algotrade should show
   `phase: W4-PR2` and `workshop_lab_roster` +
   `workshop_leaderboard` in the capabilities list.
2. **Pick a TARS_HOME**. The lab persists workshops + rosters
   at `$TARS_HOME/algotrade/lab/<workshop_id>/roster.json`.
   For a multi-day workshop, pin `TARS_HOME` so the same
   roster + leaderboard survives a worker restart.
3. **Decide the data tier**. The leaderboard ranks attendees
   by net edge against whatever paper / testnet / live
   sessions they own. For first-day workshops, **paper-only**
   is the right default; flip to testnet for day-2.

## 2. Open the lab

```jsonc
// algotrade.lab_create_workshop
{
  "name": "Cresco — May 12 — Cohort A",
  "facilitator": "alex@meeet.world",
  "notes": "Half-day intro, focus on bb_reversion + trailing_runner.",
  "metadata": { "venue": "remote", "session": 1 }
}
```

Returns:

```jsonc
{
  "ok": true,
  "workshop": {
    "workshop_id": "ws_cresco-may-12-cohort_1715000000_a1b2c3",
    "name": "Cresco — May 12 — Cohort A",
    "status": "open",
    "started_at": 1715000000.123,
    "attendee_ids": []
  }
}
```

The `workshop_id` is the only thing the facilitator needs to
remember for the rest of the day. Stash it in the cockpit lab
panel header.

## 3. Enroll attendees

For every person in the room, call:

```jsonc
// algotrade.lab_enroll_attendee
{
  "workshop_id": "ws_cresco-may-12-cohort_…",
  "display_name": "Alice Karpov",
  "metadata": { "team": "options-desk", "experience": "intermediate" }
}
```

Returns:

```jsonc
{
  "ok": true,
  "attendee": {
    "attendee_id": "att_alice-karpov_a1b2c3d4",
    "sandbox_id": "lab:ws_cresco-may-12-cohort_…:att_alice-karpov_…",
    "joined_at": 1715000010.456
  },
  "usage_hint": "Pass `sandbox_id`='lab:…' to start_paper_session …"
}
```

Hand the attendee:
1. The `sandbox_id` value from the response.
2. The `_workshop.quant.recipe_to_paper` playbook (set
   `WORKSHOP_SANDBOX_ID` env var to the value above).

That's all the attendee needs. Every session they spawn carries
their sandbox_id, so the leaderboard's fanout is automatic.

### Bulk enrollment via playbook

For large rosters, use the bundled
`_workshop.quant.lab_kickoff` playbook with a wrapper script:

```bash
for name in "Alice Karpov" "Bob Sun" "Carol Lee"; do
  WORKSHOP_NAME="Cresco May 12" \
  WORKSHOP_FACILITATOR="alex@meeet.world" \
  ATTENDEE_NAME="$name" \
  tars playbooks run _workshop.quant.lab_kickoff
done
```

Each invocation reads the same workshop_id (idempotent on
the playbook's first step — `lab_create_workshop` rejects
duplicate names by default; pass `workshop_id` explicitly to
share one across enrollments).

## 4. Run the workshop

Attendees execute their normal algotrade flow:

1. `algotrade.load_recipe` — pick a starter strategy
2. `algotrade.register_strategy` — get a fingerprint
3. `algotrade.start_paper_session` with **their** `sandbox_id`
4. `algotrade.feed_bar` / `algotrade.submit_intent` loop
5. (post) `algotrade.session_report` for the markdown handout
6. (optional) `algotrade.council_review` for the trading
   council voices

Nothing in this loop changes for lab mode — the only difference
is that every attendee passes the lab-minted `sandbox_id`.

## 5. Publish the leaderboard

```jsonc
// algotrade.lab_leaderboard
{ "workshop_id": "ws_cresco-may-12-cohort_…" }
```

Returns:

```jsonc
{
  "ok": true,
  "leaderboard": {
    "workshop_id": "ws_cresco-may-12-cohort_…",
    "workshop_name": "Cresco — May 12 — Cohort A",
    "workshop_status": "open",
    "computed_at": 1715050000.0,
    "attendees_total": 12,
    "attendees_with_sessions": 11,
    "entries": [
      {
        "rank": 1,
        "attendee_id": "att_alice-karpov_…",
        "display_name": "Alice Karpov",
        "sandbox_id": "lab:…",
        "sessions_total": 3,
        "sessions_running": 1,
        "realized_pnl": 287.42,
        "unrealized_pnl": 14.10,
        "fees_total": 12.30,
        "slippage_cost": 1.05,
        "intents_total": 18,
        "intents_accepted": 17,
        "fills_total": 14,
        "score": 274.07,
        "acceptance_rate": 0.944
      },
      …
    ]
  }
}
```

### Scoring formula

```
score = realized_pnl - fees_total - slippage_cost
```

Tie-breakers (in order):
1. Higher acceptance_rate (well-formed intents > spam-rejected).
2. More fills (more activity = more learning).
3. Earlier `joined_at` (stable, deterministic).

The leaderboard is **always recomputed from disk** — no
caching. Restart the worker mid-workshop and the next call
returns the same ranking that matches every attendee's audit
log byte-for-byte.

## 6. Per-attendee debrief

```jsonc
// algotrade.lab_attendee_snapshot
{ "attendee_id": "att_alice-karpov_…" }
```

Returns the attendee row + the workshop row + every session
the attendee owns + the attendee's current rank entry. Pair
with `algotrade.session_report` per session for a full
markdown handout the attendee can take home.

## 7. Close the workshop

```jsonc
// algotrade.lab_set_workshop_status
{
  "workshop_id": "ws_cresco-may-12-cohort_…",
  "status": "closed"
}
```

Closing sets `closed_at`, freezes new enrollments, and marks
the workshop as archived in the cockpit lab list. The
leaderboard is still recomputable — closing does NOT touch
session data — so post-workshop debriefs and council reviews
keep working.

## 8. Troubleshooting

| Symptom                                                  | Fix                                                                                 |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Attendee's sessions don't appear on the leaderboard      | Check `start_paper_session` call carried the lab-minted `sandbox_id` (not blank).   |
| Leaderboard score = 0 for an attendee with sessions      | Sessions exist but no fills. Confirm `feed_bar` is being called; paper adapter only fills on the next bar's open. |
| Worker restart left the lab empty                        | `TARS_HOME` changed between starts. Pin it to a stable path.                        |
| `lab_enroll_attendee` returns `workshop_closed`          | Re-open with `lab_set_workshop_status({status: "open"})` before enrolling.          |
| Leaderboard rank flips between identical-PnL attendees   | Tie-breakers are deterministic (acceptance_rate → fills → joined_at). Check those.  |

## 9. Pre-workshop checklist

- [ ] `algotrade` pack version ≥ 0.7.0 in cockpit.
- [ ] `TARS_HOME` pinned for the duration of the workshop.
- [ ] `_workshop.quant.recipe_to_paper` playbook visible in
      the cockpit playbook drawer.
- [ ] Optional: `_workshop.quant.lab_kickoff` playbook ready
      for bulk enrollment.
- [ ] Test run with a single dummy attendee: create →
      enroll → recipe_to_paper → leaderboard returns rank 1.
- [ ] Optional: pre-mint testnet API keys for day-2 attendees
      (https://testnet.binance.vision/).
