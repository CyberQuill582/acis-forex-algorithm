# KNOWN_GAPS_EXTERNAL_PENDING.md — external-referent audit findings (v2.11 pass, audit #2 of 2)

> **MERGED + TRIAGED into KNOWN_GAPS.md, 2026-07-17** (after the independent
> verification pass below certified completeness): GAP-0071/0072/0073/0090/0091
> CLOSED with fixes; **GAP-0070 (Hurst) OPEN — raised to the owner** with the
> confirmed recommendation (narrow to the mean-rev gate + repair estimator +
> re-derive thresholds + correct master §4 prose; GAP-0076 fixture re-tune
> bound to it). This file stays as the immutable audit + verification record.

External-referent adversarial audit, 2026-07-16 (Opus 4.8, finder-only). Rule: compare
the implementation AND the spec against their EXTERNAL referents (cited literature +
standard definitions), not against the repo's own documents. All findings reproduced with
scripts before logging (scratchpad repro_atr_rsi_ema_corr.py / repro_hurst.py /
repro_tsmom.py / repro_tsmom_fire.py). Full suite green: **286 passed**.

Same entry format as KNOWN_GAPS.md. IDs GAP-0070 onward. Status
"open (raised, external-referent audit — finder-only)". These are RAISED, not applied — no
code/test/guardrail/§14 change was made. Triage (fix+regression / mitigate / accept) belongs
to the author before phase-7 ✅.

---

## Guardrail-/§14-adjacent summary (merge into SPEC_AUDIT.md at triage)

- **GAP-0070 (Hurst, §14/regime-behaviour-adjacent, high).** The Hurst estimator is
  drift-invariant and high-variance; it cannot see a price trend, and a random walk trips
  each config threshold 20–42% of the time. It is the sole gate into the MEAN_REVERTING
  regime (which enables the Mean-Reversion and Pair-Divergence modules) and it perturbs
  trend confidence toward the 0.55 `confidence_veto`. Not a guardrail, but it materially
  drives which regimes — hence which strategy modules — are reachable, so it is §14-adjacent.
  Completes the owner-deferred GAP-0066. **No guardrail or threshold value changed by this
  audit — raised only.**
- **GAP-0071 (evolved-stop ATR unit, §8.6-adjacent, medium).** The evolved
  `atr_multiplier_sl/tp` genes are calibrated by the fitness harness on a bar series whose
  duration and ATR period are NOT tied to AGON's `signal_bar_seconds` / `signals.atr_period`.
  Since these multipliers set the broker-side stop distance (§8.6 safety law), a silent
  ATR-scale mismatch would mis-place every intraday stop/target. Sizing/stop-adjacent, not a
  guardrail edit.

---

## GAP-0070: `hurst_exponent` is drift-invariant and high-variance — it cannot distinguish a random walk from a strong price trend, and the config semantics "H>0.55 trending / H<0.45 mean-reverting" carry no external meaning (completes GAP-0066)
- Severity: high
- Likelihood: high
- Status: open (raised, external-referent audit — finder-only; this is the completed GAP-0066 characterisation + recommendation the owner deferred to this pass)
- Area: [DIR:core/regime] nvma.py `hurst_exponent`; config regime.hurst_trend (0.55) / hurst_meanrev (0.45) / hurst_window (200); its consumers in `NVMA.classify` (`trending_h`, `meanrev_h`); ACIS_SPEC.md §4; ACIS-02 v1.2
- Description: Reproduced (repro_hurst.py, 60 seeds/scenario, window=200). TWO distinct external-referent defects:
  1. **Drift-invariance (category error).** R/S Hurst is computed on the first differences (increments) with per-chunk mean removal, so a constant drift is subtracted out exactly. A pure random walk, a moderate trend (drift 0.3, same noise), and a near-deterministic strong trend (drift 0.5, noise 0.05) produce the **identical** H distribution (mean 0.530). A single near-deterministic strong uptrend reads **H = 0.504** (shipped) / **0.495** (standard) — i.e. ≈0.5, BELOW the 0.55 "trending" gate, confirming the author's GAP-0066 verification. Hurst R/S measures increment autocorrelation (persistence/anti-persistence), NOT price direction/drift; "H>0.55 ⇒ trending" is a category error about what the statistic means. Even a perfectly-implemented Hurst would not detect a deterministic price trend.
  2. **Estimation variance swamps the decision band.** On a random walk the shipped estimator gives mean 0.530 with **sd 0.103, range [0.283, 0.804]** — the sampling noise is wider than the entire 0.45–0.55 decision band (width 0.10). Consequence: a random walk is classified trending (H>0.55) **25/60 = 42%** and mean-reverting (H<0.45) **13/60 = 22%** of windows. A standard multi-window R/S estimator (≥8 geometric window sizes vs the shipped 4 R/S points; largest shipped size = the full series → a single un-averaged chunk) has less than half the variance (sd 0.062) on the same inputs.
- Reachability impact (what the classifier actually keys on today): `hurst` enters `classify` in exactly two places. (a) `meanrev_h = hurst < 0.45` is the SOLE gate into `RegimeType.MEAN_REVERTING` (an `elif` reached only when ADX is sub-strong) — and MEAN_REVERTING is one of the `_RANGING_REGIMES` that ENABLE the Mean-Reversion and Pair-Divergence modules; so a Hurst false-positive on noise (22% of random-walk windows) can turn on mean-reversion/pair trading in a market that is actually a random walk. Genuine mean reversion IS detected (OU price reads H<0.45 in 58/60 = 97%), so the gate has real signal — its problem is the false-positive rate, not blindness. (b) `trending_h = hurst > 0.55` only flips a 0.5↔1.0 term in the STRONG/WEAK trend confidence average; since random walks read H>0.55 42% of the time this term is ≈a coin flip and can spuriously push trend confidence under the 0.55 `confidence_veto` (spurious LOW_CONFIDENCE veto) or spuriously inflate it. It never GATES a trend regime (ADX+direction do that), so the trend-side damage is confidence noise, not regime misassignment.
- Justification (finder-only RECOMMENDATION): a pure rename-to-proxy is insufficient — it leaves both the "trending" category error and the noise-driven MEAN_REVERTING false-positives in place. Recommend instead: (1) NARROW the estimator's role to the anti-persistence job it can actually do — the MEAN_REVERTING gate — and DROP or heavily discount the `trending_h` confidence term (ADX already carries trend strength; Hurst adds only noise there); (2) REPAIR the estimator's variance for that gate to be trustworthy: proper multi-window R/S (≥8 geometric sizes, subseries averaging at every size, Anis–Lloyd small-sample bias correction) AND/OR add hysteresis (require H<0.45 to persist across consecutive NVMA cycles) so one noisy reading cannot flip the regime; (3) RE-DERIVE `hurst_meanrev` (and drop/retune `hurst_trend`) empirically against the repaired estimator — the phase-3 fixtures were tuned to the broken estimator and WILL need re-tuning, which is exactly why GAP-0066 flagged this as not-a-drive-by-fix. Either way, §4's "H>0.55 trending" prose is wrong about the outside world and should be corrected to describe anti-persistence, not trend.
- Linked: repro_hurst.py (2026-07-16), core/regime/nvma.py:97-132 + :285-313, ACIS_SPEC.md §4 line 162, GAP-0066, GAP-0055

## GAP-0071: the evolved ATR-multiplier stops are calibrated on a bar series with no declared duration and a hardcoded ATR period, not tied to AGON's `signal_bar_seconds` / `signals.atr_period` — a silent ATR-scale mismatch mis-places every intraday stop/target
- Severity: medium
- Likelihood: medium
- Status: open (raised, external-referent audit — finder-only)
- Area: [DIR:core/optimizer] fitness.py (`ATR_PERIOD = 14` hardcoded, `atr_series` default period, `simulate_trades` warmup), param_types.py `LabelledBar` / `RegimeLabelledHistory`; consumed by [DIR:core/signals] agon.py stop/target construction and config `signals.atr_period`
- Description: A4 asks for the GUARANTEE that the harness which EVOLVES `atr_multiplier_sl/tp` uses the same bar unit AGON later applies them on. There is none — neither a declared owner nor an assertion. (1) `LabelledBar` (param_types.py:91) has fields ts/open/high/low/close/spread/regime and **no `duration_s`**; `RegimeLabelledHistory` is just `tuple[LabelledBar, ...]` with no declared bar duration. Nothing constrains the phase-7/11 builder of that history to aggregate at `signal_bar_seconds`. (2) `fitness.ATR_PERIOD = 14` is HARDCODED and is what `simulate_trades` uses to size the SL/TP that produce the evolved multipliers; AGON's `wilder_atr(bars, self._cfg.atr_period)` reads the CONFIG period. GAP-0056 moved the signals ATR period to config but left the fitness harness on the literal 14 — they agree only by coincidence (both 14 today). If a future config sets `signals.atr_period ≠ 14`, or the phase-7 history is aggregated at a duration ≠ `signal_bar_seconds`, the evolved multipliers are calibrated to a different ATR magnitude than the one AGON multiplies them by, silently scaling every intraday stop and target (and the §8.6 broker-side stop distance) up or down. No test would catch it — the units are unenforced.
- Justification: latent because both periods are 14 and phase-7 history construction is not yet built, but the coupling is load-bearing (the evolved genes ARE the intraday risk geometry) and is currently guaranteed by nothing. Fix direction: give `LabelledBar` a `duration_s` and assert it equals `signal_bar_seconds` at history construction (single declared aggregator/owner), and drive `fitness.atr_series` off the same config `atr_period` AGON uses rather than the module literal.
- Linked: repro (read-through) core/optimizer/fitness.py:21,57,89 + core/optimizer/param_types.py:91-121 + core/signals/agon.py:353,356,366,402,423,450-451,480, GAP-0056, GAP-0059

## GAP-0072: the TREND module's conviction "ADX/50" (ACIS-04 §6.1) is computed by the close-only `adx_proxy` consumed OUTSIDE the regime layer under the canonical name "ADX" — the proxy substitution is undeclared in TREND's `declared_deviations` and in ACIS-04 §6.1
- Severity: low
- Likelihood: medium
- Status: open (raised, external-referent audit — finder-only)
- Area: [DIR:core/signals] agon.py `_trend` (`adx_proxy(seq, self._cfg.atr_period)`), indicators.py (re-exports `adx_proxy` from nvma), canonical.py TREND `declared_deviations`, ACIS-04 §6.1
- Description: The v2.11 naming law (GAP-0057/0062) renamed the regime-layer functions honestly and added ACIS-02's honesty note that "nothing outside the regime layer may treat them as ATR/ADX". But `adx_proxy` IS consumed outside the regime layer: `core/signals/indicators.py` re-exports it and `AGON._trend` calls it on bar closes to produce the conviction ACIS-04 §6.1 names plainly "clamp01(ADX/50)". `adx_proxy` is a close-only directional index (|Δmid| as the true-range stand-in, no high/low) — directionally faithful to Wilder's construction but NOT Wilder's ADX, which requires the true range from high/low. So the TREND conviction wears the canonical name "ADX" in both the spec text (§6.1) and the provenance citation (canonical.py TREND cites "Wilder … ADX"), while the value is the close-only proxy — and this substitution is absent from TREND's `declared_deviations` tuple (which lists evolved params, regime-gating, and 1-minute bars, but not "ADX-proxy-not-Wilder-ADX"). Time base is correct (it runs on bars now), and the magnitude only scales a [0,1] conviction, so the trading impact is bounded — but per the external-referent rule this is an undeclared deviation from the cited source's actual method. (The regime layer's own use is covered by the ACIS-02 honesty note; this finding is specifically the OUTSIDE-the-regime-layer consumer.)
- Justification: honesty/provenance defect, not a correctness breach (bounded conviction scale, correct bar time base). Fix direction: either add "TREND conviction uses the close-only `adx_proxy`, not Wilder true-range ADX" to TREND's `declared_deviations` and note it in ACIS-04 §6.1, or compute a true-range ADX on bars for the conviction.
- Linked: core/signals/agon.py:353, core/signals/indicators.py:17, core/signals/canonical.py TREND entry, specs/ACIS-04 §6.1 line 83, GAP-0057, GAP-0062

## GAP-0073: TSMOM signs RAW price returns, not excess-over-risk-free returns as in Moskowitz–Ooi–Pedersen (JFE 2012) — an undeclared (if low-materiality) departure from the cited method
- Severity: low
- Likelihood: low
- Status: open (raised, external-referent audit — finder-only)
- Area: [DIR:core/signals] agon.py `_tsmom` (`r = seq[-1]/seq[-1-lb] - 1.0`), canonical.py TSMOM `declared_deviations`
- Description: MOP 2012 define the time-series-momentum signal as the sign of the past-k-month EXCESS return (return in excess of the risk-free rate); the shipped `_tsmom` signs the raw price return `closes[-1]/closes[-1-lb]-1`. TSMOM's `declared_deviations` exhaustively lists the other five departures (3-horizon 63/126/252d agreement vs single 12-month lookback; no take-profit [faithful]; far disaster stop; continuous eval + vote-flip exit vs monthly rebalance; C16 vol-norm vs 40%/σ scaling) but does NOT list raw-vs-excess return. Materiality is low — at 3–12-month horizons in low-rate FX the risk-free adjustment almost never flips the sign — but it is a real, undeclared deviation from the source's actual method, which the external-referent rule counts as a finding.
- Justification: honesty completeness, not a signal-quality concern. Fix direction: either add "signs raw, not excess-over-risk-free, returns (immaterial at 3–12m FX horizons)" to TSMOM's `declared_deviations`, or subtract a risk-free accrual before signing.
- Linked: core/signals/agon.py:466-468, core/signals/canonical.py TSMOM entry, GAP-0055

---

## Honest negatives (verified-faithful — first-class deliverables)

- **A1 — Wilder ATR (fitness.atr_series / indicators.wilder_atr): FAITHFUL.** TR = max(h−l, |h−prevC|, |l−prevC|); first ATR = simple mean of the first `period` TRs; then Wilder smoothing `(ATR·(n−1)+TR)/n`. Matches an independent hand-computed reference vector to **0.0** max abs difference (repro_atr_rsi_ema_corr.py); seed equals the simple mean exactly. `wilder_atr` returns the last value, NaN when unwarmed.
- **A2 — blast radius: CLEAN.** All six AGON modules derive stops/targets from `wilder_atr` over bars (`_trend`, `_breakout`, `_mean_reversion`, `_momentum_scalp` on signal bars; `_pair_divergence` on each leg's bars; `_tsmom` on daily bars = daily true-range ATR). The Governor's C16 `_vol_factor` also now uses `wilder_atr` over `observe_bar` bars (GAP-0059 confirmed fixed in code). No residual tick-window ATR/stop path remains anywhere.
- **A3 — NVMA tick-window proxies + honesty note: as designed.** The ACIS-02 v1.2 honesty note (line 15) exists and is honest; `mean_abs_delta` and `adx_proxy` are named as proxies. The regime layer's internal use of them is legitimate. (The one out-of-layer consumer, `_trend`'s ADX conviction, is raised separately as GAP-0072.)
- **A4 — time base within a layer: consistent.** AGON signal bars and daily bars share one `BarAggregator`; the daily series is strictly ascending (GAP-0065). (The cross-layer fitness↔AGON unit GUARANTEE is the gap — GAP-0071.)
- **A5 — Pearson correlation (indicators.rolling_correlation): FAITHFUL.** Pearson on log-returns over the declared window; hand-vector match to **0.0** difference; identical series → 1.0; population covariance/variance (consistent numerator/denominator). `pair_spread_z` is a population-stdev z of `log(A) − expected_sign·log(B)`. The per-bucket joint sample (GAP-0060) means the window is a real time window (window × signal_bar_seconds).
- **A6 — §16 stdlib-deviation note: exists and is honest.** §16 records the deliberate zero-dependency-determinism choice for the fast loop, keeps ta-lib as the phase-11 cross-validation referent, and makes the naming law binding. Consistent with GAP-0057's closure.
- **RSI (Wilder, fitness.rsi_series): FAITHFUL.** Simple-average seed over the first `period`, then Wilder smoothing; on the canonical Wilder textbook closes RSI[14] = **70.46** and RSI[15] = **66.25** (textbook ≈70.53 / 66.32; the ≈0.07 gap is the known textbook intermediate-rounding artifact). Neutral-50 warm-up.
- **Bollinger (indicators.bollinger_z / nvma.bollinger_width_percentile): FAITHFUL.** 20-period, POPULATION standard deviation (÷n) per Bollinger's own convention; band width = 4σ (±2σ). NaN on flat/unwarmed.
- **QIEA (Han–Kim, qiea.py): FAITHFUL, simplification declared.** Genuine qubit-angle encoding P(observe 1)=sin²θ, rotation gate turning θ toward the generation-best bit by a fixed step, angles clamped off saturation. This is the post-GAP-0037 fix; the reduction of the full Δθ lookup table to a fixed signed step (comparison always against the generation best) is declared in-code.
- **B — TSMOM disaster stop, trend capture: HONEST (GAP-0055 carve-out stands).** Modelling the 10× daily-ATR disaster stop against realistic multi-month trends (repro_tsmom.py, 40 seeds, 520 daily bars, 0.6–1.2%/day vol) through the real `_tsmom` sign logic: **fraction of trend captured vs unstopped TSMOM = 100.00%** in every scenario (clean trend, higher vol, and a sharp 3× reversal at day 400), with **0 disaster-stop hits** — the vote-flip / 3-horizon re-evaluation always closes the position before price travels 10 ATR against it. The disaster stop is a genuine catastrophe-only backstop; it does NOT truncate the right tail the cited century evidence lives in, so the faithful-TSMOM claim and the GAP-0055 §14 carve-out are honest.
- **B — TSMOM declared_deviations: exhaustive (bar one).** The five shipped departures from MOP 2012 are all declared. TSMOM fires end-to-end from BOTH seeded history (repro_tsmom_fire.py: conviction 1.0, take_profit=None, disaster-stop distance 0.88% = 10× daily ATR) and live-tick daily aggregation; the GAP-0065 ordering guard drops out-of-order daily bars with a log. The only undeclared departure is raw-vs-excess return (GAP-0073).
- **C — conviction normalisers: DECLARED exact contracts, not silent.** ADX/50 (TREND), (magnitude/ATR)/2 (BREAKOUT), |z|/2 + Bollinger-20 + RSI-≥5-points-off-20-window-trough (MEAN_REVERSION), surge/3 (MOMENTUM_SCALP), |z|/3 × |corr| (PAIR_DIVERGENCE), agreement/3 (TSMOM) — every constant is written as an exact contract in ACIS-04 §6.1–§6.6. None is a hidden knob. (The ADX-proxy substitution behind "ADX/50" is the only wrinkle — GAP-0072.)
- **C16 vol-norm (factors.vol_norm): faithful to its declared one-sided form; note the partial analogy.** `min(1, v_target/v)` is a downward-only volatility damper — it reduces size when realized vol exceeds the declared target and NEVER levers up when vol is below target. This is deliberately NOT the symmetric published vol-targeting (MOP's `target/σ`, which increases low-vol positions); the asymmetry is consistent with the "hard limits clamp only downward" law and is declared as "C16 vol-norm, not 40%/σ" in TSMOM's deviations. Faithful to what it claims to be; the "vol-targeting" lineage is intentionally partial (no low-vol leverage). Recorded as a note, not a finding.
- **EMA seeding (fitness.ema_series): a convention difference to flag for phase-11.** The EMA is seeded with the FIRST data point (recursive convention), not an SMA of the first `period` values (ta-lib's convention). Both are legitimate and the series is used self-consistently, but the two conventions diverge during warm-up — so the phase-11 ta-lib cross-validation (§16) must expect a warm-up-region mismatch on EMA (and, by extension, on any EMA-cross timing near the series start). Recorded as a note so the cross-validation gate does not misread it as a bug.

---

## Verification pass (2026-07-17)

Independent VERIFIER (Opus 4.8, finder/verifier — NO sign-off, NO fixes). The
external-referent audit above died at a session limit before its final report and
its repro scripts died with its scratchpad; the owner authorised a verification
pass (confirm/refute item-by-item + certify completeness against
`_EXTERNAL_AUDIT_BRIEF.md`), NOT a redo. All load-bearing numbers were
RE-DERIVED with fresh scripts written from scratch (scratchpad
`v_atr_rsi_ema_corr.py`, `v_hurst.py`, `v_tsmom.py`, `v_tsmom_sens.py`). Full
suite re-run: **337 passed** (286 when the audit ran → +11 phase-7 e8582f4 →
+40 phase-8 f5ae029; both deltas EXPECTED and out of scope). Modified ONLY this
file. New findings carry ids **GAP-0090 onward**.

### Re-derived load-bearing numbers (file's claim vs my fresh script)

| Quantity | File's claim | My re-derivation | Verdict |
|---|---|---|---|
| Wilder ATR vs hand-vector (max abs diff) | 0.0 | **0.000e+00**; seed == simple mean of first 14 TRs | verified |
| Pearson-on-log-returns vs hand-vector | 0.0 | **0.000e+00** (both 0.9702608493); identical series → 1.0 | verified |
| RSI Wilder textbook RSI[14]/RSI[15] | 70.46 / 66.25 | **70.46 / 66.25** | verified |
| EMA seeding | first-value seed (not SMA) | ema[0] == closes[0] exactly | verified |
| Hurst RW distribution (W=200, 60 seeds) | mean .530, sd .103, range [.283,.804] | mean **.520**, sd **.091**, range **[.323,.737]** | verified (magnitude; exact % is RNG-dependent) |
| Hurst RW gate false-trips | >0.55: 42%, <0.45: 22% | >0.55: **33%**, <0.45: **27%** | verified (both gates tripped 20–33% by pure noise) |
| Hurst drift-invariance (RW vs RW+drift, same noise) | "identical" | max \|ΔH\| = **1.3e-15** (machine epsilon) | verified — EXACT drift-invariance |
| Hurst near-deterministic strong trend, single | 0.504 (< 0.55) | **0.463** (< 0.55) | verified (≈0.5, below the trending gate) |
| Hurst OU mean-reversion detection (<0.45) | 97% | **93%** (θ=0.15) | verified (both high — genuine MR IS seen) |
| Multi-window R/S variance vs shipped 4-point | sd .062 vs .103 | sd **.061** vs shipped **.091** | verified (proper estimator ≈⅓ less variance) |
| TSMOM disaster-stop trend capture | **100.00%**, **0 hits**, all scenarios | capture **≥100% always (101–105%)**; **17/160 replays HIT the stop** at low trend/noise; 0 hits only when drift/vol SNR is high | **corrected → GAP-0090** |

### Per-brief-item verdict table

| Brief item | File treatment | Verdict |
|---|---|---|
| A1 Wilder ATR faithful | HN A1 | verified (re-derived, 0.0) |
| A2 blast radius clean | HN A2 | verified (code-read: all 6 AGON modules + Governor C16 `_vol_factor` use `wilder_atr` on bars) |
| A3 NVMA proxies + honesty note | HN A3 | verified (nvma docstrings + ACIS-02 v1.2 line-15 note read; honest) |
| A4 unit match within a layer | HN A4 (+GAP-0071 cross-layer) | verified |
| A5 Pearson faithful | HN A5 | verified (re-derived, 0.0) |
| A6 §16 stdlib/ta-lib note | HN A6 | verified (ACIS_SPEC §16 read: zero-dep-determinism + ta-lib phase-11 cross-val referent + naming law all present/honest) |
| B TSMOM declared_deviations exhaustive | HN B + GAP-0073 | verified (5 departures declared; raw-vs-excess undeclared = GAP-0073) |
| B TSMOM disaster-stop trend-capture MODEL | HN B "100%/0 hits" | **corrected-numbers (GAP-0090)** — conclusion holds, the "0 hits" number does not |
| C undeclared constants | HN C + GAP-0072 | verified (constants are exact contracts in ACIS-04 §6; adx-proxy-as-"ADX" = GAP-0072) |
| D GAP-0066 Hurst completion | GAP-0070 | verified (drift-invariance EXACT; variance + reachability confirmed) |
| Free: RSI (Wilder) | HN RSI | verified (re-derived) |
| Free: EMA seeding | HN EMA | verified (re-derived) |
| Free: Bollinger | HN Bollinger | verified (code-read: population stdev ÷n, 4σ width, NaN-safe) |
| Free: Han–Kim QIEA | HN QIEA | verified (code-read: P(1)=sin²θ, rotation toward gen-best, θ clamped; fixed-step simplification declared in-code) |
| Free: Pearson | HN A5 | verified (re-derived) |
| Free: C16 vol-targeting | HN note | verified (code-read: `vol_norm`=min(1,target/v), one-sided; note honest) |
| **Free: Sharpe / profit-factor** | **(absent)** | **coverage-hole → GAP-0091** |

### Premise check vs phase-7 (e8582f4) and phase-8 (f5ae029)

Phase-7 changed nvma.py (+4 lines = NVMAEngine `veto_counters`), agon.py (`observe`
now returns the completed `Bar`), and added integration tests. Phase-8 touched
only `config/schemas.py`+`system_config.yaml` (a new `execution:` block),
`core/execution/*`, specs, and execution tests. **Neither touched fitness.py,
agon.py's signal maths, nvma.py's Hurst/gates, or canonical.py.** Result:

| Finding | Premise as logged | Status now |
|---|---|---|
| GAP-0070 (Hurst) | `meanrev_h`=`hurst<0.45` sole gate into MEAN_REVERTING; `trending_h`=`hurst>0.55` only a confidence term | **intact** (nvma.py:285-313 unchanged; re-confirmed by code-read + re-derivation) |
| GAP-0071 (evolved-stop ATR unit) | `fitness.ATR_PERIOD=14` hardcoded; `LabelledBar` has no `duration_s` | **intact** (fitness.py:21 + param_types.py:91-121 untouched by phase-7/8) |
| GAP-0072 (adx_proxy as "ADX") | `_trend` conviction = `clamp01(adx_proxy(...)/50)`; not in TREND `declared_deviations` | **intact** (agon.py:372-375, canonical.py TREND entry unchanged). §16's own naming law now reinforces it. |
| GAP-0073 (raw vs excess return) | `_tsmom` signs `seq[-1]/seq[-1-lb]-1`; not in TSMOM `declared_deviations` | **intact** (agon.py:486 unchanged) |

None of the four findings' premises were altered or invalidated by phase-7/8.

---

## GAP-0090: the audit's TSMOM disaster-stop honest-negative overstates robustness — "0 stop hits / 100.00% capture in every scenario" is NOT reproducible; at the stated 0.6–1.2%/day vol with realistic (low trend-to-noise) drift the 10×daily-ATR disaster stop DOES fire, though only ever on LOSING positions (so the GAP-0055 carve-out conclusion survives, and is arguably strengthened)
- Severity: low
- Likelihood: medium (the exact number is parameter-sensitive; the conclusion it defends is robust)
- Status: open (raised, external-referent verification — finder-only)
- Area: HN "B — TSMOM disaster stop, trend capture" in this file; [DIR:core/signals] agon.py `_tsmom` / `_pipeline`; GAP-0055 §14 duration carve-out; ACIS-04 §6.6
- Description: The file's honest negative B claims "fraction of trend captured vs unstopped TSMOM = 100.00% in every scenario ... with 0 disaster-stop hits ... the vote-flip / 3-horizon re-evaluation always closes the position before price travels 10 ATR against it." Re-derived by replaying synthetic daily series day-by-day through the REAL `AGON._tsmom` sign logic + real `wilder_atr` on live-seeded daily bars, 40 seeds × 4 scenarios (520 daily bars, 0.6–1.2%/day vol, incl. a 3× reversal @day400), managing one position with the actual `tsmom_disaster_stop_atr=10.0` stop and vote-flip exit (scripts `v_tsmom.py`, `v_tsmom_sens.py`):
  - **Disaster-stop hits = 17 across 160 replays, NOT 0.** Hits concentrate where the trend-to-noise ratio is LOW: weak drift 0.06%/day at 0.8% vol → 5/40; drift 0.08%/day at 1.2% vol → 7/40; the 3× reversal → 3/40. A slow 63/126/252-day majority vote can leave a position ~8% (=10×daily ATR) underwater before the vote flips.
  - **The "0 hits" number reproduces ONLY at high SNR:** a sensitivity sweep shows 0/40 hits once drift ≥ ~0.15%/day at ≤0.8% vol (drift .20%/.30% → 0 hits). The audit's scenario almost certainly used a stronger/cleaner trend than its "0.6–1.2%/day vol" caption implies, or a different stop-hit semantics.
  - **BUT the conclusion the number defends still holds — and is strengthened.** In EVERY parameterisation, captured/unstopped ≥ 100% (101–105%): when the disaster stop fired it truncated a LOSING position, never a winning trend. So the load-bearing GAP-0055/§14 claim ("the disaster stop is a catastrophe-only backstop that does NOT truncate the profitable right tail the cited century evidence lives in") is CONFIRMED — the stop only ever helps, it never clips the right tail.
- Justification: honesty/robustness of a stated audit number, not a code defect. The carve-out honesty verdict stands. Fix direction (finder-only): reword HN B from "100.00% capture / 0 hits" to the reproducible+conservative form — "captured/unstopped ≥ 100% across all tested trend-to-noise ratios; the 10×ATR stop fires only on losing positions at low SNR and never truncates a winning trend" — and, if the exact zero-hit claim is retained anywhere §14-facing, pin the drift/vol regime it holds in.
- Linked: v_tsmom.py + v_tsmom_sens.py (2026-07-17), core/signals/agon.py:477-501, GAP-0055, HN "B — TSMOM disaster stop"

## GAP-0091: coverage hole — the brief's free-sweep item "Sharpe / profit-factor definitions in fitness.py" received NO verdict in the audit file; on verification, profit factor is textbook-faithful but `sharpe_component` is an un-annualised, zero-risk-free per-trade mean/σ transform wearing the name "Sharpe"
- Severity: low
- Likelihood: low
- Status: open (raised, external-referent verification — finder-only)
- Area: [DIR:core/optimizer] fitness.py `sharpe_component` (:195-203), `profit_factor_component` (:206-211); ACIS-03 §6.1; ACIS_SPEC §16 naming law
- Description: `_EXTERNAL_AUDIT_BRIEF.md` line 30 lists "Sharpe/profit-factor definitions in fitness.py" in the mandatory free-sweep. The audit file addresses RSI, EMA, Bollinger, QIEA, Pearson and the C16 ratio as honest negatives/notes but records NO verdict on Sharpe or profit-factor — a coverage hole. Filled on verification (code-read):
  - `profit_factor_component` = `gross_win / gross_loss` (then `/3`, clamped [0,1]) — the standard profit-factor definition (gross profit ÷ gross loss). **Faithful.**
  - `sharpe_component` = `mean(pnls) / sqrt(pop_var(pnls))` mapped via `(s+3)/6` clamped to [0,1]. This is a per-trade mean/σ ratio with NO risk-free term and NO annualisation — i.e. an information-ratio-style bounded fitness scalar, not the textbook (annualised, excess-of-rf) Sharpe ratio. As an internal ranking transform (ACIS-03 §6.1) with no external provenance citation, its external-referent obligation is weaker than the six cited AGON modules — but §16's own naming law ("no function may wear a canonical name it does not implement") arguably reaches the name "Sharpe".
- Justification: honesty/naming completeness, not a correctness breach (both scalars are monotone, bounded, and used self-consistently for ranking). Fix direction (finder-only): note in ACIS-03 §6.1 that `sharpe_component` is a per-trade mean/σ proxy (no risk-free, not annualised) — or rename to e.g. `mean_over_vol_component` — so the phase-11 evaluation and any reader do not read it as a textbook Sharpe.
- Linked: core/optimizer/fitness.py:195-211, ACIS-03 §6.1, ACIS_SPEC §16, _EXTERNAL_AUDIT_BRIEF.md:30

---

## Completeness verdict (verification pass)

**Does `KNOWN_GAPS_EXTERNAL_PENDING.md` satisfy `_EXTERNAL_AUDIT_BRIEF.md`? YES — substantially — with two low-severity caveats. (This is a finder/verifier certification of coverage, NOT a sign-off; ✅ still requires a peer/superior model or the human.)**

1. **Coverage:** every brief item — A1–A6, B (incl. the TSMOM trend-capture model), C, D/GAP-0066 completion, and the free-sweep (RSI, EMA seeding, Bollinger, Han–Kim QIEA, Pearson, C16) — is addressed, **except Sharpe/profit-factor**, which was unaddressed and is now filled (GAP-0091, low).
2. **Correctness of the four logged findings (GAP-0070..0073):** all four reproduce, and their premises are untouched by phase-7/phase-8. GAP-0070's headline claims (EXACT drift-invariance to machine epsilon; estimation variance wider than the 0.10 decision band; both gates false-tripped 20–33% by pure noise; strong trend reads ≈0.5 below the gate; OU detected >90%; `meanrev_h` sole MEAN_REVERTING gate, `trending_h` confidence-only) are all confirmed. The exact random-walk percentages differ from the file's (RNG-dependent) but are the same magnitude and support the same conclusion.
3. **Correctness of the honest negatives:** all verified EXCEPT one load-bearing number — the TSMOM disaster-stop "0 hits / 100.00% capture in every scenario" is **not robust** (GAP-0090, low): the stop DOES fire at realistic low trend-to-noise ratios, but only ever on losing positions, so the GAP-0055 §14 carve-out conclusion the number defends survives and is arguably strengthened.
4. **Suite:** 337 green, consistent with the expected phase-7 (+11) and phase-8 (+40) deltas.

**Caveats to carry into triage:** (a) reword HN B per GAP-0090 before any §14-facing use of the "0 hits" figure; (b) close the Sharpe/profit-factor coverage gap per GAP-0091. Neither disturbs a guardrail, threshold, or the four original findings; both are raised, not applied.
