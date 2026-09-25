# R1 audit triage: the dual audit of master v2.21 (commit 271d8e0), triaged by the lead

**Status: RATIFIED by the owner 2026-09-25 ("Ratify all") and APPLIED as master v2.22.**

- **The reports:** `archive/AUDIT_R1_AMENDMENTS_INTERNAL_2026-09-25.md` (19 findings, I1–I19) and
  `archive/AUDIT_R1_AMENDMENTS_EXTERNAL_2026-09-25.md` (18 findings, E1–E18). Both ran on Opus in fresh context,
  under the pinned brief `AUDIT_BRIEF_R1_AMENDMENTS_2026-09-25.md`. Both were interrupted once by a session limit
  and resumed with `SendMessage`, not relaunched.
- **Both lenses agree on the headline:**
  - no guard VALUE changed;
  - no trade passes that v2.20 refused for safety reasons;
  - the NVMA veto is whole.

  But the applied text is wrong in places, mostly where it transcribed the plan loosely.
- **What the lead verified (A6):**
  - I1, I4, I5, I6 and I18 on the tree (`passed` and the live gate, the staging code and its import, `regime_f`
    in sizing, E2's units, the draw's spelling);
  - E2, E4 and I13 by arithmetic (two parallel α = 0.05 families give FWER ≈ 0.0975; a zero residual alpha gives
    P(t < −0.5) = 0.309).

  The rest rest on each auditor's quoted source or seeded script, as their reports cite.
- **Ledger:** [[GAP-P12D-103]] is the umbrella; GAP-P12D-104..123 are minted below. Gate-rule findings stay
  separate, as the auditors asked.

## A. The correction pass: the text restored to what was ratified, or made faithful to its source (all tightening or clarifying)

| # | Finding(s) | Correction | ID |
|---|---|---|---|
| C1 | I1 | `passed` = the C-BT-11 v2 verdict AND the §14 gates (Max DD < 15%, SPX < 0.25) AND C-BT-2 (≥ 2 yr, > 1 fold, ≥ 30 trades) AND C-BT-4 (guardrail hash) AND C-BT-7 (the account's rules). The live gate (ACIS-09, ACIS-08, `mode.py`) reads rung 2, which contains `passed`. A2 replaced only the DSR clause. | 104 |
| C2 | I2 | Restore B0 into rung 1 and C-BT-11 v2 as a precondition: no real-data verdict unless the lab calibration passes at the same `recon_commit`. That covers planted-at-power, null false-detect ≤ 5% + 2 se, the leaky oracle refused, RSIM ≡ engine, and variance-matched controls. | 105 |
| C3 | I4 | The staging MECHANISM is not retired: `PromotionForbiddenError`, the `PositionGate` and stage/promote/on_boundary are re-homed as the rule registry's staging. §7–§8 and C1/C2 are carved out of "legacy". The `provenance.py` import is ledgered. | 107 |
| C4 | I5 | §4 is narrowed to "regimes no longer gate rule families or key their parameters; the NVMA veto is unchanged; §6's regime factor and C4 stand until separately amended". One trigger was REPLACED (no params for the regime → no registered, validated rule set), not kept. ACIS-02 step 8 and C-REG-6 are amended to the A4 row. Whether `regime_f` leaves sizing is decision D-b. | 109 |
| C5 | I6, E1, E13 | The stage-D bettors are restated: σ* is the declared DAILY vol (σ_ann/√252); μ_claim = (SR̂_dev/2)·σ*; the per-day factor floor at −1 is a property of the bet and is stated as such; a −6σ* day or a 5× fill sets that family-version's W := 0, permanently (void, not a reset). What "E2 silent ≥ 3 months" certifies is stated as weak. PLAN_R1's "25% killed by 1 year" is recorded as the FREEZE figure. | 110 |
| C6 | I13, E2 | Stage A becomes serial gatekeeping. The Holm set is tested only after the whole fixed-sequence chain passes (FDA 2022 §7). Each family declares a look budget k (1–3) at registration and is tested at α/k. The order is a register row written before any stage-A look. The lifetime α rule is decision D-d. | 111 |
| C7 | I7 | Rung 1 also requires a per-account re-grade on the account's live-eligible universe with its §9.5 rules active (Max DD, SPX, C-BT-7), so the §14 per-account law holds. | 112 |
| C8 | I8 | "R1.7" is replaced in the spec by an explicit retirement list (A4's ratified list minus the staging mechanism). Marginal-alpha, the fragmenter, C4 and MR/SCALP/PAIR retire only by their own master amendment. | 113 |
| C9 | E6 | The MOP baseline member is made faithful: the sign of the 12-month EXCESS return (spot plus carry from the rates on disk), one horizon, MOP's vol scaling. ACIS-04 §6.6's 3-horizon spot vote stays a separate member. GAP-0073's "immaterial" is re-opened (3–12% of days disagree). | 116 |
| C10 | E3, E7 | C-BT-12: the variance match is taken at the graded rule's decision horizon (daily for TREND), by construction (common random numbers plus an exact rescale), not by a sampled tolerance. The permuted null flips ARITHMETIC price increments, or adds antithetic paths, so a long bias earns nothing in price units. A price-unit null test is added. | 117 |
| C11 | I10, E8 | The no-trade buffer is Carver's: a band of 10% of the forecast-10 position around the CURRENT position, trading to the band's edge, owned by the Governor (AGON has no portfolio state). §2, CLAUDE.md rule 5 and C-ALP-4 are reworded: "ambiguity = no trade" means a target inside the band places no order. | 118 |
| C12 | E9 | PBO ≤ 0.20 is recorded as a declared deviation from the paper's customary 0.05 (max-t carries the α, and PBO is a secondary kill), with S = 16 pinned. | 119 |
| C13 | E10 | Max-t's null: a stationary bootstrap of the members' daily series jointly, recentred (White 2000; Romano–Wolf step-down), with the block length pre-registered. | 120 |
| C14 | E11 | Stage A's standard error is HAC (Newey–West) or Lo-corrected on the daily portfolio series. | 121 |
| C15 | I9, I11, I14–I19, E14–E18 | One batch, listed in [[GAP-P12D-123]]:<br>• rung 2 requires the practice mode ([[GAP-P12D-69]]);<br>• a pair family is refused while either leg is capped;<br>• "stricter meanwhile" is replaced by "the as-built v2.20 path", with the axes listed, and no R1.x phase may land before the rules it assumes;<br>• one lot rule: round the TARGET toward zero, then order = target − current;<br>• no per-fold embargo for fixed families, and the config keys are amended;<br>• the C9-per-member and plateau conventions are defined;<br>• the draw's spelling is pinned;<br>• the read-path residue is cleared;<br>• the news prong points to [[GAP-P12D-58]]/[[GAP-P12D-03]];<br>• IDM = √N_eff, with the 2.5 caps;<br>• rung 3's expected horizon is recorded;<br>• C8 carries a swap charge calendar;<br>• the minimum lot and step are read from the platform, dated. | 123 |

## B. The owner's decisions (each with the lead's recommendation)

| # | Decision | Lead recommendation | Why | ID |
|---|---|---|---|---|
| **D-a** | What "validated" means (I3), i.e. the new `tradeable=False` trigger | **Live mode: rung 1. Paper/practice mode: a REGISTERED family whose machinery passed B0 may trade at minimum size.** That is the only way an LLM-originated family earns the forward record stage D needs. Record honestly that today's demo trades QIEA sets nobody validated. | Read strictly, "validated" makes every LLM-originated family untradeable forever. Read loosely, it is vacuous. | 106 |
| **D-b** | Does the §6 regime factor leave sizing (I5)? | **Not now.** Keep `regime_f`: it is dampen-only, and removing it is a size-UP of up to 1/regime_f (3.3× at stability 0.5, confidence 0.6). Revisit it with the position policy and NAV-relative sizing ([[GAP-P12D-61]]). | A size increase must be decided on purpose, never implied by a sentence. | 109 |
| **D-c** | Staging under continuous positions (I12): the law "never with open positions" means a new family is never promoted | **Keep the law.** Promote by a staged flatten-then-promote at a valid session boundary: risk-reducing, agent-executable, logged. Parameters are fixed under A4, so promotions are rare events. | No loosening of CLAUDE.md rule 5 is needed. | 108 |
| **D-d** | Stage A's lifetime α (E2): each quarterly cycle restarting at α = 0.05 lets lifetime FWER grow without bound | **α-spending across cycles:** cycle 1 spends 0.03, and each later cycle spends half of what remains, so the lifetime total is ≤ 0.05. With k = 1, cycle 1's bar is 0.57 at Y = 11 (D1's power ≈ 48% at the swap-free midpoint). | This is ratified direction 4 made literal: the verdict answers to the whole register. It is the price of iterating honestly. | 111 |
| **D-e** | Stage C (E4): the residualised held-out kill fires on ~31% of real factor-borne edges, the same as on noise | **Grade the held-out set RAW, still kill-only.** Stage C can only kill, so the factor leak that residualising removes can only weaken a kill, never credit. Keep the frozen draw; no re-draw. | Residualising only costs power here, and the plan's "credited only forward" was really "killed". | 114 |
| **D-f** | The forecast-scalar source (E12) | **Carver's published values** (3.75 / 2.65 / 1.87, with his daily price-volatility normaliser and EWMA span convention). Record them as literature-fixed. | The null-derived scalars run ~24% hot on real data, which means more risk than σ* declares. The published ones spend no project look. | 122 |
| **D-g** | The "⅓ of pre-cost Sharpe" cost filter (E5) | **Split it into two filters.** (1) Carver's speed limit: annual turnover cost ≤ 0.13 SR units, from his book, pinned. (2) A separate swap-MARKUP viability filter per instrument, against a FIXED expected Sharpe, not a realised one. Both are declared deviations. | This is faithful to Carver, and it removes a data-dependent per-instrument look. | 115 |

## C. What happens next
- **If the owner ratifies:** the lead applies A and B as master v2.22, ACIS-09 v1.8, ACIS-03 v2.1, ACIS-04 v1.4 and
  ACIS-02 v1.3, with ACIS-11 and ACIS-08 as needed. Each correction is checked against the finding's own
  reproduction (as with the branch fixes), and the full suite and gate are run.
- **On a re-audit:** the constitution does not require one for fixing findings. If the owner wants the corrected
  text re-audited, that is an explicit launch.
- **Meanwhile, no R1.x build starts,** and the as-built v2.20 behaviour stands.
