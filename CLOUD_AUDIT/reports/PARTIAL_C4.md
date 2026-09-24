# PARTIAL — C4 PROVEN PARTS & THE KILL LIST (in progress)

- Lane: C4 · Model observed: `claude-opus-5-5` (Opus 5.5); effort not observable from inside (launcher configured xhigh) · Fresh context, no subagents · BASE `7695ed04abfeaa7535e237afcac25fb983025ff0` · 2026-09-24 · web searches used so far: 0 (PyPI JSON API via curl used for package metadata).

## Landed so far

1. **Component inventory** (receipt: `evidence/C4/probe_inventory.py`, output `probe_inventory.out.md`): 11,727 lines across the named components; the product core (`core/` + `monitoring/`) is ~7,500 lines; the backtest harness alone is 3,125.
2. **Process is outgrowing product.** Over the 50 commits at BASE (2026-09-13 → 09-24): production Python (`core/`+`monitoring/`) grew 326,141 → 335,797 bytes (+3.0%); live Markdown (non-archive) grew 975,260 → 1,172,747 bytes (+20%); `archive/` grew 58 KB → 1,017 KB. Live Markdown is now **3.5× the bytes of all production Python**. Command: `git ls-tree -r -l <commit>` summed by path class (see final report).
3. **Demo SDK facts (PyPI JSON, primary):** `ctrader-open-api` 0.9.2 MIT, last release 2024-06-26, pure-Python wheel, but exact-pins `Twisted==24.3.0`, `protobuf==3.20.1`; `MetaTrader5` 5.0.6180 ships only `win_amd64` wheels; `nautilus_trader` 1.231.0 is LGPL-3.0 and requires Python ≥3.12 (ACIS pins 3.11); `v20` (OANDA official) last release 2018; `oandapyV20` last release 2021.

## Next
Degrees-of-freedom bound; per-component verdicts with line deltas; kill list; smallest demo runtime.
