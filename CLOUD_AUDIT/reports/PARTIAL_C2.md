# PARTIAL — C2 FALSE-ENCOURAGEMENT HUNTER (in progress)

- Lane: C2, harness red team. Model: Opus 5.5 (`claude-opus-5-5`), effort not observable. Fresh context. BASE 7695ed04. 2026-09-24.
- Status: code read done; reproductions being written to `reports/evidence/C2/`. The final will be `reports/C2_HARNESS_REDTEAM.md`.

## Candidate holes found so far (code-read; reproductions pending)

1. **Stops fill at the stop price even when the market gaps through them, in BOTH the fitness sim and the graded book.** Code: `core/optimizer/fitness.py:117-125` and `tests/backtest/book.py:115-121`. GAP-P12D-42 already notes that the harness "books stops AT the stop price", but only as a reason a test can't be written. Nobody has priced it.
2. **The graded book triggers stops on the MID, and the loader DROPS every tick whose spread is above `max_plausible_spread`** (`tests/backtest/data_loader.py:82-83`, with 5 pips set for EUR_USD and USD_JPY). So the moments when spreads blow out (the 17:00 New York rollover, news) never trigger a stop, never cost a spread, and never show in the marks. A live broker's server-side sell stop triggers on the BID. Not in the ledger.
3. **The fitness sim runs on a STITCHED series.** `LabelledBarCache.history` and `qiea.fitness_window` return only the bars of one regime, concatenated. EMA crosses, ATR, stop checks and max-hold counts all span jumps of hours or days between regime episodes, and a stop that one of those jumps gaps through is filled at the stop price. Not in the ledger.
4. **`passed` ignores `var_breach_frequency` and every fidelity caveat**, including "NO overnight financing modelled". The synthetic grader passes `financing=None` (`tests/backtest/synthetic_grade.py:96`). See `report.py:265-274`.
5. **Equity, drawdown and the Governor's NAV mark open positions at the mid with no exit cost** (`book.py:158-167`). A position still open at the end of the run never pays its exit friction.
6. **Configuration look-ahead:** the `costs`, `vol_target_atr_frac` and `max_plausible_spread` values are calibrated once, over the whole tick archive, which overlaps the 2024–2025 holdout (`config/instruments.yaml:50-53, 98-101`; `data_loader.calibrate_cost_model` takes a whole-period median).
7. **The synthetic tape is not a faithful positive control.** It has a constant 0.4 bp spread, no weekend gap (Friday's close runs straight into Monday), no volatility clustering, uniform 20 s ticks and 1–4 h episodes only. So findings 1 and 2 are invisible to `falsify_engine.py` and `cost_stress_ladder.py` by construction.
8. **The cost-stress ladder multiplies only the per-side C8 cost.** It does not touch financing, gap slippage, spread spikes (which the loader drops), or the mid-triggered stops.
