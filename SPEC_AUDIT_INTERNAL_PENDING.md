# SPEC_AUDIT_INTERNAL_PENDING.md — Lens 1 (Internal-Consistency) findings, phase-12 SPEC audit

**Auditor:** Opus 4.8, Lens 1 (internal-consistency), launched cold per `SPEC_AUDIT_BRIEF.md` v1.0.
**Date:** 2026-07-21 · **Target:** `ACIS_SPEC.md` (master v2.12) + LOCKED `specs/` (ACIS-01..12) + `config/`.
**Governing constitution:** `../specs_constitution/SPEC_CONSTITUTION.md` v0.3, Tier 1.

## Attestation (A4)
- **Context was fresh/cold.** I did not participate in authoring the spec or any build session. I formed my
  attack from the code/config/spec text and reproduced every finding with a script before recording it (A6).
- **No web research** — that is Lens 2's job by design (A3, must fail differently).
- **Method:** grep + small Python scripts parsing the real YAML/spec/tests. Repro script saved at
  `scratchpad/repro_sp12i.py`. The existing drift gate `tests/unit/test_spec_constants.py` was run: **9 passed**.
- I am a **finder, not a clearer** (A5). A clean line below is a checked negative, never a sign-off. Nothing here
  edits `KNOWN_GAPS.md`, `SPEC_AUDIT.md`, the spec, config, or tests — the author merges + triages per A6.
- **Severity of the whole batch is LOW.** I could not break a guardrail, a HALT/veto semantic, a staging rule,
  or the layer law by internal contradiction. Every finding is documentation/traceability drift or a latent
  fencepost. That is itself a first-class result and is stated honestly.

---

## FINDINGS

### GAP-SP12I-01 — Master spec still names "Sharpe" for a quantity the ratified build declares is NOT Sharpe
- **Severity:** Low · **Likelihood:** High (present in the master right now)
- **Area:** `ACIS_SPEC.md` §5 (fitness), §8 (RiskSnapshot + alpha-decay) vs `specs/ACIS-03` §6.1, `specs/ACIS-07` §4/§10
- **Description:** GAP-0105 (a.k.a. P9E-05) is **CLOSED** in `KNOWN_GAPS_CLOSED.md`: the shipped fields were renamed
  from `rolling_sharpe_50t`/`sharpe_nan_safe` to `rolling_mean_sigma_50t`/`mean_sigma_50t` because they compute a
  per-trade mean/σ, **not** an annualised Sharpe. The fix landed in the deep specs but was **never propagated up to
  the master (the build authority).** The master still reads:
    - §5: `Fitness = Sharpe×0.40 + WinRate×0.20 + ProfitFactor×0.20 + MaxDrawdownPenalty×(−0.20)`
    - §8 RiskSnapshot list: `rolling 50-trade Sharpe and win-rate`
    - §8 alpha-decay: `rolling Sharpe(last 50 trades) < threshold × baseline Sharpe(trades −200..−50)`
  while the LOCKED deep specs explicitly disclaim that term:
    - ACIS-03 §6.1: `fitness = 0.40·mean_sigma_c + 0.20·win_rate + 0.20·pf_c − 0.20·mdd_pen`
    - ACIS-07 §4: `rolling_mean_sigma_50t: float  # per-trade mean/σ — NOT an annualised Sharpe (GAP-P9E-05)`
  Per `specs/ACIS-00-INDEX.md` precedence, *a locked spec may add detail but never contradict the master* — here the
  locked spec must contradict the master to be honest, because the master was left stale.
  **Reproduction:**
  ```
  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py   # section SP12I-01
  # master fitness : Fitness = Sharpe×0.40 + WinRate×0.20 + ProfitFactor×0.20
  # master §8 snap : True   (contains "rolling 50-trade Sharpe")
  # ACIS-07 field  : True   (contains "NOT an annualised Sharpe")
  # GAP-0105 closed but master still says 'Sharpe' (no 'mean_sigma' in master): True
  ```
- **Justification:** Functionally harmless (the alpha-decay test is a *ratio* `s_recent < 0.5·s_baseline`, so any
  annualisation constant cancels; fitness is a relative rank). But the master is the constitution a fresh session
  trusts, and it now teaches a term the ratified code was corrected *away from*. The correction should close the loop
  by adding a one-line master note ("the §5/§8 'Sharpe' component is the per-trade mean/σ of GAP-0105, not an
  annualised Sharpe; the annualised Sharpe is only the §14 graded metric") — or the master values re-worded. No drift
  test guards this term.

### GAP-SP12I-02 — Load-bearing anti-greed constants (0.25 floor, 1.5 cap, 25% throttle) have NO drift gate
- **Severity:** Low · **Likelihood:** Medium (drift only on a future careless edit)
- **Area:** `ACIS_SPEC.md` §6 (marginal-alpha floor/cap), §8 (alpha-decay throttle) vs `specs/ACIS-05` §6.1 / step 4;
  gap in `tests/unit/test_spec_constants.py`
- **Description:** The brief asks to "hunt a prose constant with no drift gate." Three risk-restrictive constants are
  stated in master prose — §6 "factor floors at **0.25**", §6 "**Cap 1.5** — never more", §8 "cut all allocations to
  **25%**" — and are realised in code (ACIS-05 §6.1 `g()` and step-4 `× 0.25`). Unlike the eight guardrail values,
  **none of the three is pinned by `test_spec_constants.py`** to what the code runs on.
  **Reproduction:**
  ```
  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py   # section SP12I-02
  # master floor/cap/throttle present: True True True
  # drift test references 0.25 / 1.5 / 25%: False False False
  ```
- **Justification:** ACIS-05's C-GOV-1 unit tests *do* assert `g()`'s 0.25 floor and 1.5 cap as function properties,
  so the code side is tested — but nothing cross-checks the **master prose value against the code** the way the drift
  test does for the guardrails. If someone edited §6 to "floors at 0.30", no red test would fire. These are anti-greed
  / risk-restrictive levers (never guardrails), so severity is Low; the fix is to extend the drift test with three
  anchors (or accept-risk with the C-GOV-1 property-test as the record). Weaker than the guardrail case because these
  live in `ACIS-05` structural code, not YAML.

### GAP-SP12I-03 — MOMENTUM_SCALP sits exactly on the fast-decay exclusion fencepost; the most time-sensitive strategy never takes the IOC path
- **Severity:** Low · **Likelihood:** High (true of every scalp signal as configured)
- **Area:** `config/system_config.yaml` (`signals.valid_for_seconds.MOMENTUM_SCALP`, `execution.fast_decay_seconds`)
  vs `ACIS_SPEC.md` §7 / §5.5 and `specs/ACIS-06` §7
- **Description:** Master §7 defines the aggressive-IOC fast path as `valid_for_seconds < 30`; ACIS-06 §7 implements
  it with a **strict `<`**: "`SizedOrder` whose originating signal had `valid_for_seconds < fast_decay_seconds` (30)".
  The config sets `MOMENTUM_SCALP.valid_for_seconds = 30` and `fast_decay_seconds = 30`. So the shortest-lived signal
  type in the whole system (30 s, vs TREND/MEAN_REVERSION 300 s) is **excluded** from the IOC fast path by one second
  at the boundary and is instead routed to the fragment/VWAP/single path — the opposite of §5.5's intent (a
  tick-velocity-surge scalp on a 5–15-bar horizon, "speed over stealth").
  **Reproduction:**
  ```
  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py   # section SP12I-03
  # scalp valid_for=30  fast_decay_seconds=30  strict '<' rule -> qualifies=False
  # ACIS-06 rule: valid_for_seconds < fast_decay_seconds
  ```
- **Justification:** Not a guardrail and not a hard master contradiction (the master's own definition is `< 30`, and
  30 is not `< 30`, so the master is *self*-consistent). But it is a reproducible spec-intent-vs-config mismatch and a
  latent execution-path bug: as shipped, MOMENTUM_SCALP never gets IOC. No §13 glitch test covers the fast-decay
  boundary. Fix is a one-value decision (set scalp `valid_for_seconds` to 29 or below, or make ACIS-06 use `<=` for
  the scalp class, or raise `fast_decay_seconds`) — owner-directed, since it touches execution routing behaviour.

### GAP-SP12I-04 — ACIS-02 §6 names ADX config keys that do not exist (`adx_strong_threshold`/`adx_weak_threshold`)
- **Severity:** Low · **Likelihood:** High (present now)
- **Area:** `specs/ACIS-02-NVMA_REGIME.md` §6 vs `config/system_config.yaml` + `config/schemas.py`
- **Description:** ACIS-02 §6 config listing names the regime ADX thresholds `adx_strong_threshold` and
  `adx_weak_threshold`. The **actual shipped keys/schema fields are `adx_strong` / `adx_weak`** (schemas.py:64-65;
  system_config.yaml:12-13). ACIS-02 is even internally inconsistent — its own §7 (line 74) uses the correct bare
  `adx_strong`/`adx_weak`.
  **Reproduction:**
  ```
  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py   # section SP12I-04
  # actual config regime keys: ['adx_period', 'adx_strong', 'adx_weak']
  # ACIS-02 §6 says 'adx_strong_threshold': True
  ```
- **Justification:** Pure documentation drift — the code loads `adx_strong`/`adx_weak`, so nothing breaks — but a
  fresh session reading the LOCKED deep spec would look for a config key that is not there, and it violates the
  "config listing names the real key" discipline the rest of the specs follow. One-word fix in ACIS-02 §6.

### GAP-SP12I-05 — Stale config narrative: scenario_book says the GAP-0108 outage refinement is "deferred to phase 11"; ACIS-09 (phase-11 ✅, LOCKED) says it was delivered
- **Severity:** Low · **Likelihood:** High (present now)
- **Area:** `config/scenario_book.yaml` (comments, 3 places) vs `specs/ACIS-09-BACKTEST_VALIDATION.md` §6 + project
  status (CLAUDE.md / STATUS.md: phase 11 ✅)
- **Description:** `scenario_book.yaml` states three times that "the outage-allowance-source refinement … is deferred
  to phase 11". Phase 11 is complete (ACIS-09 LOCKED v1.1, 515 green), and ACIS-09 §6 states the refinement as a
  delivered methodology item: "the scenario-replay outage allowance is refined to source the worst gap from the worst
  ENABLED-instrument gap for this account's universe". Both cannot be current.
  **Reproduction:**
  ```
  PYTHONIOENCODING=utf-8 python scratchpad/repro_sp12i.py   # section SP12I-05
  # scenario_book 'deferred to phase 11': True
  # ACIS-09 says refinement delivered: True
  ```
- **Justification:** Comment-only staleness with no safety impact (the static `max_loss_pct_nav: 7.5` in the book is a
  conservative superset of any all-majors account's enabled-only gap, so the book errs safe). But it is exactly the
  read-path/traceability drift A13 forbids: a fresh session reading the config would believe a completed refinement is
  still pending. Update the three comments to point at where the refinement now lives (ACIS-09 §6 / the per-account
  release gate), or confirm and record that the static book value is intentionally retained as the conservative
  fallback.

---

## HONEST NEGATIVES (checked and found consistent — first-class results, A6/A10)

1. **All eight guardrail values agree across every copy and are drift-pinned.** daily-drawdown 2.0%, per-instrument
   1.0%, alpha-decay Sharpe-mult 0.5×, VaR cap 3.0% NAV, cluster cap 20%, single-currency delta cap 30%, slippage
   alert 8.0 bps, taper 0.60 / entry-halt 0.80 — identical in master §6/§8, `guardrail_limits.yaml`, `ACIS-05`,
   `ACIS-07`, `ACIS-09`. `tests/unit/test_spec_constants.py` pins each to the real YAML through the real loader and to
   the schema stricter-only ceilings: **9 passed**. A full-doc regex sweep for disagreeing copies found **zero** (the
   only two hits were false positives matching the literal `0.0` inside the ACIS-07 taper formula).
2. **Every `§`-cross-reference in the master resolves.** All 29 distinct `§N`/`§N.N` references (0–18 plus the ten
   subsections 3.5/3.6/3.7/5.5/5.6/5.7/7.5/8.5/8.6/9.5) point to an existing section header. No dangling or
   mis-numbered pointer found.
3. **QIEA fitness formula matches** master §5 (`Sharpe×0.40 + WinRate×0.20 + ProfitFactor×0.20 − MDD×0.20`) ↔
   ACIS-03 §6.1 (`0.40·… + 0.20·… + 0.20·… − 0.20·…`), modulo the naming issue in SP12I-01. **ParamSet ranges** match
   master §5 ↔ ACIS-03 (ema_fast 5–50, ema_slow 20–200, rsi 7–21, atr_sl 1.0–3.5, atr_tp 1.5–5.0, momentum 5–50,
   breakout 0.5–2.0, zscore 1.5–2.5, holding 1–48) with the tp>sl / slow>fast invariants present.
4. **Governor sizing formula factors match** master §6 ↔ ACIS-05 §6 (conviction · liquidity · correlation ·
   regime_stability×confidence · marginal_alpha · vol_norm · taper), with the upward edge declared risk-restrictive
   only (rejects any factor > 1.0).
5. **12 regime types match** master §4 ↔ ACIS-02 §5 (three †always-`tradeable=False`: MACRO_EVENT/ILLIQUID/
   UNCLASSIFIED). **Regime veto thresholds match** (confidence < 0.55, spread > 3×, tick-velocity < 0.5×) across
   master §4, config, ACIS-02, and are drift-pinned. **hurst_meanrev = 0.35** consistent across master §4, config,
   ACIS-02 §6, changelog v2.12, and drift-pinned; `hurst_trend` is deleted everywhere (config, schema, ACIS-02).
6. **§14 targets match** master §14 ↔ ACIS-09 §4 (Sharpe > 1.5, DD < 15%, WR > 48%, PF > 1.4, +months > 70%, SPX corr
   < 0.25, duration 30min–48h) with the TSMOM/scalp duration carve-outs recorded in both.
7. **Heartbeat/watchdog SLAs consistent.** master §12 (10 s fast / 60 s others, 3 missed beats → flatten) ↔ ACIS-08
   §6 ↔ config (`heartbeat_fast_s:10`, `heartbeat_other_s:60`, `missed_beats_flatten:3`); `watchdog.yaml`
   `watchdog_timeout_s:30` = 3 × the ≤10 s beat, so the 30 s silence window is exactly the 3-missed-beat rule.
8. **CHF de-peg arithmetic is internally consistent.** scenario_book: `min(cluster_cap 20, delta_cap 30)%` = 20% NAV
   worst book × 35% gap = 7.0% NAV, ceiling 7.5% — the referenced cluster/delta caps match config, and the ceiling
   sits just above the computed worst cost. (Whether −35% is the right *real-world* magnitude is Lens 2's call.)
9. **VaR 1-day horizon is consistent** across master §8 ("1% VaR"), config (`var_horizon_seconds:86400`,
   `var_method:delta_normal_undiversified`), ACIS-07 §5 (σ scaled √(horizon/eval_cadence)), and ACIS-09 §4
   (`var_breach_frequency` vs the 3% cap). (Whether the 50-sample window and √-scaling are sound is Lens 2's call.)
10. **fast_loop_decision_budget_ms = 250** consistent master §10 (deep-spec-owned) ↔ ACIS-04 §6 ↔ config, drift-pinned.

## Residual risk / scope honesty
- I hunted internal contradiction, master↔deep-spec drift, unpinned prose constants, changelog-vs-body drift, and
  cross-reference errors. I did **not** verify that any named statistic computes what its *real-world* definition
  says, nor the realism of the §14 target levels or the CHF magnitude — those are Lens 2 by construction, and a clean
  Lens-1 pass says nothing about them.
- The batch is uniformly Low severity. That is a genuine result, not reassurance: the guardrail values, HALT/veto
  semantics, staging rules, and layer law survived every internal-contradiction attack I could construct and pinned
  themselves under the drift test. The remaining defects are the spec telling a fresh session a slightly out-of-date
  story (SP12I-01/04/05), one unpinned lever class (SP12I-02), and one latent execution fencepost (SP12I-03).
- **Finder, not clearer.** These five bind only after the author reproduces them (all repro commands above are
  deterministic); the honest negatives are recorded so the next auditor need not re-walk them from scratch.
