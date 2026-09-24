"""C5 — an agent-reachable staged tunable that RAISES size on a losing book (BASE 7695ed04, read-only import).

Run:  PYTHONDONTWRITEBYTECODE=1 python repro_stage_config_relax.py /tmp/review-acis
`monitoring/tools.py` claims its allowlist admits "no risk-raising value on any path". The human-committed
allowlist (`config/system_config.yaml` monitoring.tunable_paths) admits governor.marginal_alpha_window in [10, 500],
while governor.marginal_alpha_min_trades is 20. A window below min_trades can never fill, so the estimator pins to
NEUTRAL 1.0 forever — switching off the 0.25 anti-greed floor a losing book earns.
"""
import sys
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/review-acis")
sys.path.insert(0, str(ROOT))
from config.schemas import load_config  # noqa: E402
from core.governor.marginal_alpha import MarginalAlphaEstimator  # noqa: E402
from monitoring.auth import HumanTokenVerifier  # noqa: E402
from monitoring.tools import ControlTools  # noqa: E402

cfg = load_config(ROOT / "config")
gcfg = cfg.system.governor
bounds = {t.path: (t.min, t.max) for t in cfg.system.monitoring.tunable_paths}


class Stager:
    def stage_config(self, patch, rationale):
        return "staged-1"


class Audit:
    def find(self, rid): return None
    def record_once(self, rec): return True


class Log:
    def event(self, *a, **k): pass


class Ctl:
    def apply_halt(self, *a): pass
    def flatten(self, *a): pass
    def resume(self, *a): pass


tools = ControlTools(control=Ctl(), auth=HumanTokenVerifier.from_secret("owner"), mode_controller=None,
                     stager=Stager(), tunable_bounds=bounds, audit=Audit(), logger=Log(), session_id="s")
resp = tools.call_tool("acis_stage_config", {"request_id": "r1", "args": {
    "patch": {"governor.marginal_alpha_window": 10}, "rationale": "agent"}}, caller="agent")


def factor(window):
    est = MarginalAlphaEstimator(window, gcfg.marginal_alpha_min_trades, gcfg.marginal_alpha_min_bucket)
    for i in range(60):                                    # a steadily LOSING book, varied sizes
        size = Decimal(1000 + 100 * (i % 10))
        est.record_trade(size, Decimal(-2 - (i % 3)))
    return est.factor()


a, b = factor(gcfg.marginal_alpha_window), factor(10)
print(f"agent (no human token) stage_config governor.marginal_alpha_window=10 -> {resp}")
print(f"min_trades={gcfg.marginal_alpha_min_trades}; losing book: window {gcfg.marginal_alpha_window} -> "
      f"factor {a.factor} ({a.detail}); window 10 -> factor {b.factor} ({b.detail})")
print("DEFECT REPRODUCED" if resp["status"] == "ok" and b.factor > a.factor else "not reproduced")
