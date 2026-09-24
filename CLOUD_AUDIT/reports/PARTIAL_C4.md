# PARTIAL — C4 PROVEN PARTS & THE KILL LIST (run 2, in progress)

- Lane: C4 · Model observed: `claude-opus-5-5` (Opus 5.5); effort not observable (launcher configured xhigh) · Fresh context (run 2), no subagents · BASE `7695ed04abfeaa7535e237afcac25fb983025ff0` · 2026-09-24 · web searches used: 2 (+ WebFetch of primaries, PyPI JSON via curl).

## Landed so far (run 2 re-verified run 1)

1. **Inventory re-verified.** `evidence/C4/probe_inventory.py` re-run at BASE reproduces `probe_inventory.out.md` byte-for-byte (11,727 lines across named components).
2. **Process is outgrowing product (re-verified).** `git ls-tree -r -l` at 85e1cf0 (2026-09-13) vs 7695ed0 (BASE): core+monitoring .py 326,141 → 335,797 B (+3.0%); live .md 975,260 → 1,172,747 B (+20%); archive/ 58 KB → 1,017 KB; tests/ .py 469 KB → 711 KB (+51%).
3. **Degrees of freedom** (`evidence/C4/probe_dof.py`, output `.out.md`): QIEA runs 600 evaluations per (regime, instrument) = **43,200 per fold**; the graded DSR counts only surviving champions (≤72/fold, `tests/backtest/harness.py:217-218`). Even at an effective N of 100, MinBTL at SR 0.5 is ~26 years, vs a 2-year fitness window per fold and ~25 effective instrument-years in total.
4. **Contract/venue impedance:** cTrader Open API rejects an absolute stopLoss on MARKET orders (only `relativeStopLoss`), while the §7.5 contract demands an absolute stop "atomically with the fill" and the conformance gate asserts exact equality (`tests/integration/test_adapter_conformance.py:143`). OANDA v20 `stopLossOnFill.price` fits the contract as written.
5. **S3 verified at primary** (Carver's speed limit: "DO NOT SPEND MORE THAN ONE THIRD OF YOUR EXPECTED PRE-COST RETURNS ON COSTS"); the "3 weeks to 3 months" clause was NOT found verbatim. **S4 verified at primary** (Darwinex risk engine: 6.5% monthly VaR target, 3.25–6.5% band, last 45 exposed days; 95% confidence per help.darwinex.com/var).
6. **Demo SDK facts (PyPI JSON):** `ctrader-open-api` 0.9.2 MIT, last release 2024-06-26, Twisted-based, exact-pins Twisted 24.3.0 / protobuf 3.20.1 / requests 2.32.3; `MetaTrader5` win_amd64 only; `nautilus_trader` LGPL-3.0, Python ≥3.12; `v20` last release 2018, `oandapyV20` 2021.

## Next
Per-component verdicts with line deltas; kill list; smallest demo runtime; final report.
