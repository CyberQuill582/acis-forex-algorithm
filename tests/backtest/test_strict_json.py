"""No bare NaN in any JSON the backtest writes (audits F6/E7).

RFC 8259 §6: "Numeric values that cannot be represented in the grammar below (such as Infinity and
NaN) are not permitted." Python's `json.dumps` writes them by default. After the empty-mean fix
(GAP-P12D-38) a rung whose §14 duration band is empty carries avg_duration_s NaN, and ladder.json
wrote it as a bare `NaN`. Every writer now goes through `oos_runner.strict_json`, and these tests
parse the output with a parser that REFUSES the non-standard constants.
"""

from __future__ import annotations

import json
import math
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests.backtest.oos_runner import report_json, strict_json
from tests.backtest.test_metrics_and_grader import _block, _report

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cost_stress_ladder import ladder_document  # noqa: E402


def _strict(text: str):
    def refuse(token: str):
        raise ValueError(f"non-RFC-8259 constant {token}")
    return json.loads(text, parse_constant=refuse)


def test_strict_json_writes_every_non_finite_float_as_null() -> None:
    value = {"a": math.nan, "b": [math.inf, -math.inf, 1.5], "c": {"d": math.nan}, "e": Decimal("1.25")}
    assert _strict(strict_json(value)) == {"a": None, "b": [None, None, 1.5], "c": {"d": None}, "e": "1.25"}
    with pytest.raises(ValueError, match="non-RFC-8259"):
        _strict(json.dumps({"a": math.nan}))                       # what the default writer produced


def _row(stress: float, net: str) -> dict:
    return {"kind": "planted", "tag": f"rung_{stress:g}x", "cost_stress": stress, "spread_floor": 0.0,
            "passed": False, "trades": 40, "sharpe": math.nan, "profit_factor": math.inf, "win_rate": 1.0,
            "avg_duration_s": math.nan, "max_drawdown_pct": 0.0, "net_pnl": net, "dsr": math.nan,
            "trials": 0, "failed": ["avg_duration"], "seconds": 1.0}


def test_the_ladder_document_is_strict_json_even_when_the_duration_band_is_empty() -> None:
    text = ladder_document(kind="planted", account="dev_paper", folds=25, days=985, bar=2.0, quick=False,
                           rows=[_row(1.0, "-5.0"), _row(2.0, "-7.0")])
    doc = _strict(text)
    assert doc["rungs"][0]["avg_duration_s"] is None and doc["rungs"][0]["dsr"] is None
    assert doc["rungs"][0]["profit_factor"] is None and doc["verdict"].startswith("NO EDGE TO STRESS")


def test_a_validation_report_with_non_finite_metrics_is_strict_json() -> None:
    report = _report(out_of_sample=_block(avg_trade_duration_s=math.nan, profit_factor=math.inf),
                     deflated_sharpe=math.nan)
    doc = _strict(report_json(report))
    assert doc["out_of_sample"]["avg_trade_duration_s"] is None and doc["deflated_sharpe"] is None
