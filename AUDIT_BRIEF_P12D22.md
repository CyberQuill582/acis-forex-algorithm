# Pinned dual-audit brief — Governor base-unit sizing + evolve-driver steps 1–4 (A4)

Pinned 2026-09-15. Launch both lenses in fresh context, in parallel, on Opus 5 (owner directive 2026-09-15; Fable only when the owner asks; floor Opus 4.8) — never Sonnet or Haiku. (This commit's first audit pair was already running on Fable when the directive landed and was left to finish.) Auditors change no repo file except their report, cite existing IDs only (label findings F-I1… / F-E1…), and write to `scratchpad/audit_p12d22_internal.md` and `scratchpad/audit_p12d22_external.md`. The author triages every finding into `KNOWN_GAPS.md`, then `git mv` this brief and the reports to `archive/`.

**Scope:** the 2026-09-15 commit "Governor base-unit sizing (GAP-P12D-22) + evolve-driver steps 1–4". Read GAP-P12D-22, GAP-P12D-18, GAP-P12D-19, GAP-P12D-20 and GAP-P12D-21 in KNOWN_GAPS.md first.
- Core: core/governor/units.py, core/governor/calendar_gates.py, core/governor/capital_governor.py (sizing, exposure notional, pair-leg notional; calendar gates moved), specs/ACIS-05 v1.3.
- Backtest: tests/backtest/book.py, harness.py, boundary_clock.py, deflated_sharpe.py (`n_trials`), report.py (`in_sample_evolution`), data_loader.py (`stream`), tick_stream.py, regime_labels.py, oos_plan.py, evolve_step.py, scripts/build_labelled_bars.py, tests/integration/paper_loop.py (`position_gate`, `provenance`).

## Lens 1 — internal consistency
1. Sizing: `size_units` is base-currency units for XXX_USD, USD_XXX, crosses and gold, per ACIS-05 §4/§7. Is the notional used by the cluster and currency caps now USD for every case, including pair groups? Does anything else in core (Risk Monitor, execution, venue adapters, MCP surfaces) assume the old units? Is the calendar-gate move behaviour-identical?
2. Harness: the embargo check on declared `train_end` versus the first test tick; promotion only through `on_boundary` when the backtest book is flat; `n_trials` rules (fold Sharpes for variance, champions + `min_trials` for N, fewer than 2 fold Sharpes means no N).
3. Labeller: no look-ahead (label = the classification before the completing tick); year warm-up and year cut; cache key covers everything that changes a label; `history()` never returns a bar at or after `end`.
4. Fold plan and holdout guard: can any development path read, label or grade 2024–2025? Is "graded once" enforced (exclusive create), and can a failed start consume the single grade?
5. Evolve step: only bars before `train_end`; seeds reproducible; best-holdout selection and staging only.

## Lens 2 — external referent
1. FX unit conventions: base/quote units, USD notional for USD-base pairs and crosses, and how brokers (OANDA units, MT5 lots) define position size, compared with ACIS-05.
2. Walk-forward practice: calendar folds with an embargo (López de Prado purge/embargo), dropping the in-sample replay, and counting trials for the Deflated Sharpe (Bailey & López de Prado 2014: variance across trials, independent-trial N).
3. Offline regime labelling: labels built from information available at bar close, the replay cadence, and warm-up length relative to NVMA's windows.
4. Known bug classes: survivorship or leakage through cached features; DST in session boundaries; per-instrument cost models in price units.

## Both lenses also cover
Module legibility (GAP-P12M-01, `tests/unit/test_module_budget.py`), invariant density (GAP-P12M-02), and ledger closure (`python scripts/ledger_check.py` green; are the new Residual lines honest?).
