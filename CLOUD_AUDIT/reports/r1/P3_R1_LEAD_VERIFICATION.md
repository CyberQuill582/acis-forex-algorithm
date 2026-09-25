# P3 R1: the lead's verification of the lanes' top claims (A6: a finding binds only after it survives refutation)

- **Verifier:** the cloud lead. Its configuration reads `claude-opus-5-5` at effort `xhigh`.
- **Scope:** BASE `974dbda`, 2026-09-25. Receipts are in `evidence/LEAD/`.
- **Method:**
  - an **independent re-implementation** where one is affordable;
  - otherwise a **re-run** of the lane's own receipt, which checks reproducibility but not independence;
  - or a **primary-source fetch**.
- **Verdicts:** CONFIRMED, PLAUSIBLE or REFUTED.

| # | Lane | Claim | How checked | Verdict |
|---|---|---|---|---|
| 1 | R1-A | A betting e-process holds FPR ≤ 5% under daily looks; a daily-peeked t-test does not | **Independent re-implementation** from R1-A's stated definition (`repro_lead_eprocess.py`, 1,000 replications, 10 years). Null FPR at e ≥ 20: 2.8% (Gaussian) and 2.5% (t4). Daily-peeked t-test: 40.3% and 39.6%. R1-A reports 1.5–3.6% and 38–47% | **CONFIRMED** |
| 2 | R1-A | Sign of edge forward is slow: P(e ≥ 20 by 3 y) and the median years to e ≥ 20 | Same re-implementation, t4 innovations. The lead measured: SR 1.0: 0.258, 6.76 y; SR 1.5: 0.55, 2.65 y; SR 2.0: 0.805, 1.46 y. R1-A reports 22–26%, 5.8–6.8 y; 51–59%, 2.4–3.0 y; 80–83%, 1.4–1.7 y | **CONFIRMED** |
| 3 | R1-A | IDM = √(N/(1+(N−1)ρ)) on P&L correlation; values at N = 20/30/40 | Arithmetic re-computed by the lead. The lead **added** the comparison against the 8 declared instruments (+13% at ρ 0.2, +24% at ρ 0.1), which R1-A's draft did not state (PLAN_R1 A5) | **CONFIRMED** (arithmetic) |
| 4 | R1-B | FTMO's symbol JSON: EUR/USD swap −9.49/+0.36 points, $5 flat commission; 166 active symbols; the G10 positive-carry side keeps a median of 21% of fair carry; 6 of 28 pairs have no positive side | **Primary-source fetch** of `https://ftmo.com/wp-json/ftmo/symbols` (2026-09-25) and a lead re-computation (`repro_lead_ftmo_swaps.py`). Every number matches. **Caveat:** "21% of fair carry" rests on R1-B's symmetric-markup decomposition (L = d − m, S = −d − m), a modelling assumption; the raw swap points are (a) | **CONFIRMED** (data (a); decomposition an assumption) |
| 5 | R1-C | Whole-path demeaning biases a pooled 126-day momentum rule by about −1.2 annual SR at N = 20 on 2.8-year paths, and pays the mirror reversal rule +1.2; on 14-year paths it is about −0.06 | **Re-run** of `repro_bridge.py` (2 s): byte-identical to the committed output. Consistent with the prior lead's closed form (−0.038 log units per path; C3/P3) | **CONFIRMED** (reproduced, not independent) |
| 6 | R1-C | The lab's null centres at zero (−0.013, se 0.025; false-detect 4.0%), and a planted pooled trend is detected at 96% against a theory power of 0.915 | **Re-run** of `probe_calibration.py 100` (46 s): byte-identical | **CONFIRMED** (reproduced, not independent) |
| 7 | R1-C | The fix is "demean nothing", plus a random ±1 sign per shuffled return for the permuted kind | **Lead reasoning.** Given the shuffled multiset, an independent symmetric sign makes each return a martingale difference with respect to any non-anticipating rule's past, so its expected gross P&L is exactly zero. "Demean only the planted drift" subtracts a path-dependent constant, which re-creates a bridge on the drift component | **CONFIRMED** (argument) |
| 8 | R1-D | Kill-list line counts at BASE | **Independent `wc -l`:** qiea 291, evolve_step 117, fitness 256, param_library 268, param_types 143, plateau 74, nvma 395, stability 44, regime_labels 197, marginal_alpha 73, fragmenter 120. All match. `core/` + `monitoring/` = 7,645 lines at this BASE, not the 7,519 of C4's older BASE | **CONFIRMED** |

**Still to verify, as the finals land:**
- R1-A: the register-verdict FPR under adaptive iteration;
- R1-B: its universe draw and data plan;
- R1-D: the RSIM timing (a receipt re-run).
