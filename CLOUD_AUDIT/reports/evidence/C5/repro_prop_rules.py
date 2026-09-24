"""C5 — confirm SCOUT's prop-fit findings and one new rule-mechanics hole, BASE 7695ed04 (read-only import).

Run:  PYTHONDONTWRITEBYTECODE=1 python repro_prop_rules.py /tmp/review-acis
Synthetic account paths only.
"""
from __future__ import annotations

import asyncio
import random
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

sys.dont_write_bytecode = True
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis")
sys.path.insert(0, str(ROOT))

from config.schemas import DrawdownRule  # noqa: E402
from core.risk.guardrails import build_drawdown_series  # noqa: E402
from tests.risk_fixtures import RecordingSink, acct, build_monitor, load_cfg  # noqa: E402

T0 = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)   # 14:00 CEST, 08:00 New York
cfg = load_cfg()
out: list[str] = []

# S-A  the $9,000 absolute floor halts a $6k account at the first evaluate
sink = RecordingSink()
mon, *_ = build_monitor(cfg, sink)
snap = mon.evaluate(acct(6000), T0)
out.append(f"S-A floor: equity 6000 -> equity_floor_breached={snap.equity_floor_breached} "
           f"flattens={sink.flattens} halts={sink.halts}")

# S-B  every platform rule is built with resets_daily=False; the schema has no reset instant/zone
ftmo = cfg.platform_rules.accounts["ftmo"]
series = build_drawdown_series(cfg.guardrails, ftmo.drawdown_rules, "ftmo")
out.append("S-B resets_daily per rule: " + ", ".join(f"{k}={rd}" for k, _o, _r, rd in series.rules)
           + f"; DrawdownRule fields={sorted(DrawdownRule.model_fields)}")

# S-C  sub-minimum-lot orders go straight to the venue (no min_lot / lot_step check)
from config.schemas import ExecutionConfig  # noqa: E402
from core.execution.orchestrator import ExecutionOrchestrator  # noqa: E402
from core.execution.venue import FillReportStore, MockExecutionFace, VenueQuality  # noqa: E402
from core.governor.portfolio_types import SizedOrder  # noqa: E402
from tests.optimizer_fixtures import CapturingLogger  # noqa: E402


async def sc() -> str:
    face = MockExecutionFace()          # declares min_lot=0.01 (1,000 units), lot_step=0.01
    with tempfile.TemporaryDirectory() as d:
        o = ExecutionOrchestrator(ExecutionConfig(**cfg.system.execution.model_dump()), {"mock": face},
                                  VenueQuality(), FillReportStore(Path(d) / "f.db"), 8.0,
                                  random.Random(1), CapturingLogger(), "s", now_fn=lambda: T0)
        r = await o.submit(SizedOrder(order_id="o", signal_id="s", instrument="EUR_USD", direction=1,
                                      size_units=Decimal("332.17"), entry_price=1.08, stop_loss=1.07,
                                      take_profit=None, reason="probe",
                                      factors_snapshot=MappingProxyType({}), sized_at=T0,
                                      param_set_id="p"), valid_for_seconds=300)
    return (f"S-C min lot: descriptor min_lot={face.descriptor.min_lot} lots; 332.17 units (0.0033 lot) -> "
            f"status={r[0].status.value} filled={r[0].filled_units} (dispatched, no min-lot/lot-step check)")


out.append(asyncio.run(sc()))

# S-D  a restart re-bases every drawdown measure to 0 (anchors live in memory only)
path = [10000, 10400, 9800, 9400]
s1 = build_drawdown_series(cfg.guardrails, ftmo.drawdown_rules, "ftmo")
for i, e in enumerate(path):
    st = s1.measure(equity=e, balance=e, now=T0 + timedelta(minutes=i), start=0.6, halt=0.8)
s2 = build_drawdown_series(cfg.guardrails, ftmo.drawdown_rules, "ftmo")
st2 = s2.measure(equity=9400, balance=9400, now=T0 + timedelta(minutes=5), start=0.6, halt=0.8)
out.append("S-D restart: before " + ", ".join(f"{s.rule_key}={s.measured_pct:.2f}%" for s in st)
           + " | after restart " + ", ".join(f"{s.rule_key}={s.measured_pct:.2f}%" for s in st2))

# N-1  NEW: the `ftmo` stand-in (trailing/intraday/equity 5%) is LOOSER than FTMO's real daily rule
#      when a realised gain lifts the balance while another position is open at a loss.
#      FTMO: limit = balance at 00:00 CE(S)T - 5% x initial capital, tested on equity.
s3 = build_drawdown_series(cfg.guardrails, ftmo.drawdown_rules, "ftmo")
day1 = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
steps = [  # (utc time, equity, balance, note)
    (day1, 10000, 10000, "start, flat"),
    (day1 + timedelta(hours=1), 10000, 10000, "A +400 open, B -400 open"),
    (day1 + timedelta(hours=2), 10000, 10400, "A closed: balance 10400; B still -400"),
    (datetime(2026, 9, 23, 22, 0, tzinfo=timezone.utc), 10000, 10400, "00:00 CEST: FTMO anchors balance 10400"),
    (datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc), 9850, 10400, "B slides to -550"),
]
ftmo_anchor = 10400
for t, e, b, note in steps:
    st = s3.measure(equity=e, balance=b, now=t, start=0.6, halt=0.8)
worst = {s.rule_key: (round(s.measured_pct, 2), round(s.distance_fraction, 2), round(s.taper_factor, 2)) for s in st}
ftmo_limit = ftmo_anchor - 0.05 * 10000
out.append(f"N-1 ftmo stand-in: equity 9850 vs FTMO daily floor {ftmo_limit:.0f} -> FTMO BREACHED="
           f"{9850 < ftmo_limit}; ACIS (measured %, distance, taper) = {worst}; any ACIS rule at distance>=1: "
           f"{any(v[1] >= 1.0 for v in worst.values())}")

print("\n".join(out))
