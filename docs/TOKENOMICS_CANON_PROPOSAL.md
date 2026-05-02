# MEEET Tokenomics — Canonical Proposal

> **Status:** PROPOSAL (awaiting Operator approval)
> **Author:** Claude QA — 2026-05-02 00:30 UTC+7
> **Discovered via:** Deep tokenomics audit 2026-05-01 (subagent run identified 20 contradictions across 47 markdown files)
> **Resolves:** B-008 in `meeet-command-center/state/BLOCKERS.md`
> **Replaces (on merge):** scattered claims in `QA_BOT_DOMAIN_KNOWLEDGE.md`, `legal-security-ops.md`, `TOKENOMICS_AUDIT.md`, `DEEP_TOKENOMICS_AUDIT_v2.md`, `LOVABLE_ROUND_53_TOKENOMICS_FIX.md`, `MEEET_TREASURY_AND_ENHANCEMENTS.md`, `blog-04-{en,ru}-meeet-tokenomics.md`, on-page copy at `/token` and `/economy`, and the whitepaper draft.
>
> **How this document is meant to be used:**
> - On merge into main, this file is **the** authoritative source for any tokenomics number, mechanic, or governance rule. All other docs become deprecated and must either redirect to this file or be updated to mirror it verbatim.
> - The `/token` and `/economy` pages must render numbers from this canon (or from the underlying program/database state that this canon describes).
> - Any future change to tokenomics requires a PR amending this file with a new ADR-style entry in the changelog at the bottom.
> - Investor / legal / regulatory inquiries should be answered using this document only.
>
> **What Operator must decide before this can merge:** see «§9 Open decisions for Operator». Six items have multiple defensible options; recommendation is given for each, but Operator's call is final.

---

## §1. Token primitives (✅ verifiable on-chain)

These are facts, not decisions. They are pinned here for reference.

| Field | Canonical value | Source |
|---|---|---|
| Mint address | `EJgyptJK58M9AmJi1w8ivGBjeTm5JoTqFefoQ6JTpump` | Solana RPC `getAccountInfo` |
| Token program | Token-2022 (`TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`) | RPC |
| Decimals | 6 | RPC |
| Mint authority | `null` (REVOKED) | RPC `getMint` |
| Freeze authority | `null` | RPC |
| Metadata update authority | `null` (immutable) | Metadata extension |
| Initial supply at TGE | 1,000,000,000.000000 | Mint creation tx |
| Current supply (snapshot 2026-05-01 23:55 UTC+7) | 999,999,788.003648 | RPC `getTokenSupply` |
| Burn delta from TGE | 211.996352 (micro-burn from pump.fun graduation, NOT protocol burns) | derived |
| Trading venue | PumpSwap (graduated from pump.fun on 2026-04-26) | DexScreener |

These never change without a coordinated on-chain action. Anyone can verify them.

## §2. Supply distribution (canonical)

```
Community / Staking pool:      40%   (400,000,000 MEEET)
Development:                   20%   (200,000,000)
Liquidity (LP):                15%   (150,000,000)
Team:                          10%   (100,000,000)   — vesting per §3
Marketing:                     10%   (100,000,000)
Reserve:                        5%   ( 50,000,000)
                              ─────
                              100%   1,000,000,000
```

**Source:** `QA_BOT_DOMAIN_KNOWLEDGE.md`. No contradictions found in other docs.

**Locked vs circulating today:**
- Currently `100%` of supply has shipped to the mint — **before** authority revocation. This means the wallets controlling each tranche today are the source of truth for «what is liquid vs what is locked».
- Need to publish, on the public site, the **5 wallet addresses** for each tranche (`Treasury`, `LP`, `Team-vesting`, `Marketing`, `Reserve`) so anyone can audit. **Currently not done — see §9 (D6).**

## §3. Team vesting

> 3 different models found in 4 docs. **Resolution required.**

| Source | Claimed schedule |
|---|---|
| `QA_BOT_DOMAIN_KNOWLEDGE.md` | 1 year cliff + 3 years linear vesting |
| `LOVABLE_ROUND_53_TOKENOMICS_FIX.md` (referenced from `/economy` page translations) | 24 months cliff + 48 months vesting |
| `TOKENOMICS_AUDIT.md` | 12 months total |
| `Meeet_World_Whitepaper_v2.docx` | (need to extract; assumed 1y+3y per investor-FAQ alignment) |

### ✅ Recommended canonical: **1-year cliff + 3-year linear vesting** (4 years total)

**Reasoning:**
- Aligns with VC/launch-pad standard (most Tier-1 Solana projects use 1y+3y or 1y+2y)
- `QA_BOT_DOMAIN_KNOWLEDGE.md` is the agent-facing canon used for live QA; changing it would require the most updates downstream — keep this as canonical
- 24m+48m (6 years total) is unusually long; deters team commitment perception
- 12 months total is too short — investor-unfriendly, increases dump risk

### ❌ Deprecation
- Update `LOVABLE_ROUND_53_TOKENOMICS_FIX.md` to `1y+3y`; on-chain Token-2022 vesting extension or off-chain agreement needs to enforce.
- `/economy` page translations updated to read «1-year cliff, 3-year linear vest» / «1 год клифф, 3 года линейного вестинга».
- `TOKENOMICS_AUDIT.md` corrected.

## §4. Treasury multisig

> 2 different configurations found across 3 docs. **Resolution required.**

| Source | Claim |
|---|---|
| `legal-security-ops.md` line 143 | «Multisig (3-of-5) for treasury wallet, keys held by Alex + Foundation director + 2 advisors + cold storage» |
| `investor-FAQ.md` (referenced) | 2-of-3 |
| `QA_BOT_DOMAIN_KNOWLEDGE.md` | not specified explicitly; mentions Squads multisig service |

### ✅ Recommended canonical: **3-of-5 (Squads multisig)**

**Composition (from `legal-security-ops.md`):**
1. Alex Vasilev (operator/founder)
2. Foundation director (TBD if not yet appointed — operator decides §9 D2)
3. Advisor 1 (TBD)
4. Advisor 2 (TBD)
5. Cold storage / hardware wallet (offline, recovery)

**Reasoning:**
- 3-of-5 provides better resilience (loss of 2 keys recoverable; 2-of-3 only tolerates 1 key loss)
- More signers = harder for any single individual to control treasury, stronger «no single point of failure» narrative for regulators
- Squads on Solana fully supports 3-of-5 with timelock and proposal flow
- `legal-security-ops.md` is the most legally-rigorous doc and explicitly says 3-of-5

### ❌ Deprecation
- `investor-FAQ.md` updated to 3-of-5.
- All on-page copy referring to "team multisig" must say 3-of-5.
- 5 wallet addresses publicly published per §9 D6.

## §5. Insurance Fund timelock

> 3 different values found across 3 docs. **Resolution required.**

| Source | Timelock |
|---|---|
| `Round 54.1` audit (referenced in `LOVABLE_ROUND_53_TOKENOMICS_FIX.md` lineage) | 90 days |
| `investor-FAQ.md` | 72 hours |
| Treasury doc (referenced) | 48 hours |

### ✅ Recommended canonical: **72 hours timelock**

**Reasoning:**
- 90 days is too long — by the time funds can be deployed, an exploit response is futile (insurance fund's purpose is rapid deployment for protocol exploits, gas spikes, oracle failures)
- 48 hours is too short for community to organize a veto / object to a withdrawal proposal (governance review takes ~2-3 days)
- 72 hours is the industry middle ground (matches Aave, Compound, OlympusDAO timelock conventions)
- Standard on-chain pattern: Squads proposal → 72h timelock → execute

### Edge cases
- **Emergency override** (zero timelock): allowed only with 4-of-5 multisig signatures + public on-chain «emergency» tag → for verifiable critical exploits only. Should be used at most 2 times per year, never for non-emergency operational moves.
- **Timelock applies to:** withdrawals from the Insurance Fund wallet to ANY destination including buyback&burn, treasury rebalancing, exploit reimbursement.

### ❌ Deprecation
- 90d / 48h variants removed from all docs.

## §6. Burn mechanics — exactly 5

> Canonical doc says 5; `/economy` page lists 7+ including non-canonical entries. **Resolution required.**

### ✅ Recommended canonical: **exactly 5 burn mechanisms** (per `QA_BOT_DOMAIN_KNOWLEDGE.md` §Burn механики)

| # | Mechanism | Amount per event | Frequency basis |
|---|---|---|---|
| 1 | Mint agent | 100 MEEET (or progressive `100 × 1.5^(n-1)`, capped 85K) | per agent registration |
| 2 | Discovery accepted | ~17 MEEET (1/3 of 30-50 payout) | per discovery merge |
| 3 | Prediction resolution | 0.5% of pool | per oracle settlement |
| 4 | Arena loss | 10 MEEET (20 split with opponent) | per arena defeat |
| 5 | Rejected parliament proposal | 10 MEEET deposit forfeit | per rejected proposal |

### ❌ Wrongly listed extras (must be REMOVED from `/economy`)

- ❌ «Transfer tax 2%» — **NOT a burn mechanism**. There is no transfer tax on $MEEET. Mint authority is REVOKED so no tax extension can be added without remintng (which requires governance vote and a new mint).
- ❌ «Marketplace fee 30%» — this is a **fee split** (goes to Treasury / StakingPool / partial Burn) not a flat burn. Should be described in §7, not as standalone burn.
- ❌ Other entries — confirm with Operator and remove.

### Implementation status
- All 5 mechanisms require backend code (Edge Functions or on-chain programs) to actually execute the burn (`SPL Transfer to incinerator address` or equivalent).
- Until those Edge Functions ship, the «Total Burned» on `/token` should show **on-chain delta only** (211.996 MEEET as of 2026-05-01, almost entirely from pump.fun graduation, NOT protocol burns). See `LOVABLE_FIX_TOKEN_PAGE_TOTAL_BURNED.md`.

## §7. Treasury splits

### ✅ Recommended canonical (per `QA_BOT_DOMAIN_KNOWLEDGE.md`)

```
$MEEET payment splits (e.g. agent mint, marketplace, breeding):
  Treasury:     50%
  Burn:         30%
  StakingPool:  20%

SOL payment splits (e.g. subscriptions Scout/Warrior/Commander/Nation):
  LP:           40%
  Buyback&Burn: 30%
  Operations:   20%
  Insurance:    10%
```

Both totals = 100%. No contradiction found in other docs but worth pinning here so it doesn't drift.

## §8. Breeding cost

> 2 values found: 100 vs 500 MEEET. **Resolution required.**

### ✅ Recommended canonical: **500 MEEET per breeding event**

**Reasoning:**
- 100 MEEET is the **agent mint cost** — same as breeding would create same supply pressure as fresh mints
- Breeding adds value beyond just creating an agent (genetic combination of parent traits, rarity boost, narrative scarcity), so cost should reflect the premium
- 500 MEEET keeps the breeding economy interesting without becoming a free-replication exploit
- Subject to dynamic adjustment (governance can change to 250-1000 range based on observed demand)

### Splits per §7
- 250 to Treasury (50% of 500)
- 150 to Burn (30%)
- 100 to StakingPool (20%)

## §9. Open decisions for Operator (must answer before this merges)

### D1. President veto + 30% treasury power — IS this a documented mechanic or hallucinated by an LLM round?

This phrase appears **only in BLOCKERS.md B-008 quoting the audit**, NOT in any whitepaper. Two possibilities:
- **(a) Real mechanic**: governance role «President» can veto proposals + control 30% of treasury for a defined period. If real, this needs a full ADR — significantly increases regulatory complexity (centralized control after «decentralized» launch).
- **(b) Hallucination**: an audit subagent invented this from context. Should be removed from BLOCKERS.md entirely.

**Operator decides.** If (a), the whole governance section must be expanded; if (b), I'll remove the line and add a DECISIONS_LOG entry.

### D2. Foundation director — appointed?

§4 multisig assumes a Foundation Director key-holder exists. If the foundation is not yet incorporated (Wyoming LLC / Cayman Foundation / Lithuania / Estonia), the multisig is currently **3-of-5 with 1 vacant slot** — that's **3-of-4 effective**, which is materially less secure.

**Operator decides:** has the Foundation been incorporated? If not, what's the temporary 4-of-4 or 3-of-4 plan until it is?

### D3. Advisor key-holders — named?

§4 lists «2 advisors». Are they appointed? If yes, who? If no, what's the plan?

**Operator decides** and we update §4 with names (or pseudonymous handles) before publishing.

### D4. Insurance Fund — does it exist and what wallet?

§5 prescribes a 72h timelock on withdrawals. Pre-condition: the Insurance Fund wallet must EXIST and be FUNDED. Is there an existing wallet? What's its current balance?

**Operator decides** and we update §5 with the wallet address.

### D5. Cold storage key — who holds, where?

§4 multisig includes a «cold storage / hardware wallet» key. Operator decides: hardware (Ledger/Trezor) location and recovery seed custody.

This is a real-world security question — answer should not appear in this public doc but Operator must have a clear answer for legal/audit reviewers.

### D6. 5 wallet addresses for Community/Dev/LP/Team/Marketing/Reserve — public?

Per §2, these should be published on the site for verifiability. Operator decides: publish now (transparency win), or wait until §4 multisig is fully operational (avoids confusion if treasury wallet rotates).

**Recommend: publish now**, mark each wallet's role + balance, even if multisig signers are pending.

### D7. President role — exists?

If D1 confirms «yes», governance section needs full description: term, election mechanic, veto scope, 30% treasury allocation rules, removal procedure.

If «no», keep current parliament-based governance only.

## §10. Pricing model — secondary canon (informational)

The B-008 audit also flagged confusion in PRICING (subscription tiers). Quick canon for cross-reference:

### ✅ Subscription tiers (per `QA_BOT_DOMAIN_KNOWLEDGE.md`)

```
Scout:     0.19 SOL/mo  (~$28)   /  1 agent
Warrior:   0.49 SOL/mo  (~$73)   /  3 agents
Commander: 1.49 SOL/mo  (~$224)  / 10 agents
Nation:    4.99 SOL/mo  (~$749)  / 50 agents
```

### ❌ Variants to remove
- «Pro 25,000 MEEET/mo / Enterprise 80,000» — appears on `/token` page (R-43 regression). Replace with the SOL-denominated 4-tier list above.
- «Trial / Citizen / Senator / Governor (USD-first)» — appears in `PRICING_TIERS.md` effective May 2; deprecated by this canon.

### ✅ Staking tiers (per `QA_BOT_DOMAIN_KNOWLEDGE.md`) — exactly 4

```
Explorer:   100      MEEET / 5%  APY / 1d   lock
Builder:    5,000    MEEET / 12% APY / 7d   lock
Architect:  25,000   MEEET / 20% APY / 14d  lock
Visionary:  100,000  MEEET / 30% APY / 30d  lock
```

Any «Flex / Diamond» or «1K / 10K / 50K / 250K» reference is R-05 regression and must be removed.

## §11. Cross-references to update on merge

These docs/files must be updated to mirror this canon (or replaced with «See `TOKENOMICS_CANON.md`»):

| File | Action |
|---|---|
| `meeet-solana-state-941a6045/src/pages/Token.tsx` | Render Total Burned, fix tier list to SOL-denominated |
| `meeet-solana-state-941a6045/src/pages/Economy.tsx` (`/economy`) | Limit burn list to 5 mechanisms (§6); remove transfer-tax claim |
| `Claude/Projects/Meeet.world/QA_BOT_DOMAIN_KNOWLEDGE.md` | Add cross-reference to this file as «authoritative; this is a navigation summary only» |
| `Claude/Projects/Meeet.world/legal-security-ops.md` | Update line 143 reference; cross-link this canon |
| `Claude/Projects/Meeet.world/blog-04-en-meeet-tokenomics.md` and `blog-04-meeet-tokenomics.md` | Update vesting/multisig/burns numbers; add canon link |
| `Claude/Projects/Meeet.world/Meeet_World_Whitepaper_v2.docx` | Update before next investor share |
| `Claude/Projects/Meeet.world/PRICING_TIERS.md` (effective May 2) | Mark deprecated; redirect to canon §10 |
| `Claude/Projects/Meeet.world/PRICING_MODEL_v2.md` | Verify match with §10 |
| `Claude/Projects/Meeet.world/TOKENOMICS_AUDIT.md` and `DEEP_TOKENOMICS_AUDIT_v2.md` | Mark «historical» (not authoritative) |
| `Claude/Projects/Meeet.world/MEEET_TREASURY_AND_ENHANCEMENTS.md` | Update §4 references |
| `Claude/Projects/Meeet.world/LOVABLE_ROUND_53_TOKENOMICS_FIX.md` | Update vesting + multisig values |
| `tars-neural-cockpit/docs/SYNC.md` | Add this file to «authoritative docs» list in §0 if such section exists |
| `state/BLOCKERS.md` (command-center) | Mark B-008 with «mitigated by `TOKENOMICS_CANON.md` proposal — awaiting Operator approval» |

## §12. Changelog (ADR-style, append-only)

### 2026-05-02 00:30 UTC+7 — initial proposal (Claude QA, instaps lane)

- Drafted from QA_BOT_DOMAIN_KNOWLEDGE.md + legal-security-ops.md as primary sources
- Reconciled 6 contradictions (vesting / multisig / timelock / burns / breeding / pricing tiers)
- Identified 7 open decisions for Operator (§9)
- Status: PROPOSAL — awaiting Operator approval before becoming canonical
- Discovered via deep tokenomics audit subagent run on 2026-05-01

---

_If this PR is rejected, my next action: convert the proposal into a discussion thread in `tars-neural-cockpit#8` so Cursor + Operator can debate item-by-item. This file would then become an ADR-style decision log of WHY each canonical value was chosen, not an unilateral declaration._

_If this PR is merged, B-008 transitions from P0 to «mitigated» in BLOCKERS.md, and this file becomes the citation for any future tokenomics-related comm._
