"""Module-size budget — SPEC_CONSTITUTION v0.4 A12 ("a source file over 300 lines is
presumptively a finding") made machine-checked for ACIS. An external review
(2026-09-11) found long modules (capital_governor.py ~470, monitor.py ~380) that stay
coherent but are hard for a new reader. So:

  * a production module may not exceed BUDGET lines;
  * the modules already over budget are grandfathered at their 2026-09-11 size, each
    owned by GAP-P12M-01 — they may SHRINK, never GROW (a ratchet);
  * once a grandfathered module is back under budget its allowlist line must go
    (a stale exemption is itself a failure), so the list only ever gets shorter.

Decomposition itself is audit work (GAP-P12M-01), not done here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGET = 300                                  # SPEC_CONSTITUTION v0.4 A12
PRODUCTION = ["core", "monitoring", "config", "scripts", "tests/backtest"]

# path -> line count on 2026-09-11 (the ceiling), all owned by GAP-P12M-01
GRANDFATHERED = {
    "config/schemas.py": 533,                   # 702 → 622: calendars → config/calendars.py (P12D-10); → 581: rulebook → config/rulebook.py (P12D-54); → 535: monitoring → config/monitoring_schema.py (ACIS-13 venue block); → 533: runtime block → config/runtime_schema.py
    "core/signals/agon.py": 506,
    "core/governor/capital_governor.py": 401,   # 464 → 448: calendar gates → calendar_gates.py (P12D-22); 447 (P12D-58); 437: exposure caps → exposure.py; 436; 434: `_rewrite` via replace (v1.6 min size); 401: entry guards → guards.py (R1.6)
    "scripts/download_histdata.py": 400,        # 456 → 400 after scripts/dl_common.py extraction
    "core/regime/nvma.py": 395,
    "core/signals/provenance.py": 391,
    "core/risk/monitor.py": 343,                # 378 → 368: usd factor → usd_conversion.py (P12D-55); 343: VaR/cluster → exposure_metrics.py
}


def _production_modules() -> dict[str, int]:
    out = {}
    for top in PRODUCTION:
        for p in (ROOT / top).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if p.name.startswith("test_") or "__pycache__" in rel:
                continue
            out[rel] = len(p.read_text(encoding="utf-8").splitlines())
    return out


def test_no_new_module_exceeds_the_budget() -> None:
    over = {m: n for m, n in _production_modules().items()
            if n > BUDGET and m not in GRANDFATHERED}
    assert not over, (f"modules over the {BUDGET}-line legibility budget: {over} — decompose "
                      "them (lean-build law); do not add them to the grandfather list")


def test_grandfathered_modules_only_shrink() -> None:
    sizes = _production_modules()
    grown = {m: (sizes[m], cap) for m, cap in GRANDFATHERED.items() if sizes.get(m, 0) > cap}
    assert not grown, f"grandfathered modules GREW past their ratchet (now, cap): {grown}"


def test_grandfather_list_has_no_stale_entries() -> None:
    sizes = _production_modules()
    stale = [m for m in GRANDFATHERED if m not in sizes or sizes[m] <= BUDGET]
    assert not stale, (f"{stale} are gone or back under {BUDGET} lines — remove them from "
                       "GRANDFATHERED (and update GAP-P12M-01)")
