"""LEAD v2 of the internal auditor's HIGH-1 / L5 / race repros, re-aimed at the fixed register API.
No real data is read: a stand-in source NAMED 'dukascopy' (real provenance) yields the synthetic walk."""
import sys, tempfile, threading, itertools
from pathlib import Path
TREE = Path(sys.argv[1]); sys.path.insert(0, str(TREE))
import tests.backtest.look_register as lr
from config.schemas import load_config
from tests.backtest.data_loader import BacktestDataLoader
from tests.backtest.look_register import LookRegister, LookRefused, CANONICAL
from tests.backtest.oos_runner import RunInputs, run_walk_forward
from tests.backtest.sources import DukascopyTickSource
from tests.backtest.test_oos_runner import _Synthetic, _folds
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec
from tests.optimizer_fixtures import CapturingLogger, bars_from_closes, zigzag_closes
from core.regime.regime_types import RegimeType
from datetime import datetime, timezone
cfg = load_config(TREE / "config"); inst = sorted(cfg.instruments.enabled); folds = _folds()
HEAD = lr.git_state()[0]; lr.git_state = lambda repo=None: (HEAD, False)       # a clean tree at HEAD
class StandInDukascopy(DukascopyTickSource):
    def __init__(self): pass
    def load(self, instrument, start, end): yield from _Synthetic().load(instrument, start, end)
src = StandInDukascopy(); print("stand-in provenance:", getattr(src, "provenance", None), "name:", src.name)
tmp = Path(tempfile.mkdtemp(prefix="lr2_")); _n = itertools.count()
def cache():
    c = LabelledBarCache(tmp / f"labels{next(_n)}", LabelSpec.for_config(cfg, "dukascopy", datetime(2014, 1, 1, tzinfo=timezone.utc)))
    bars = bars_from_closes(zigzag_closes(600), RegimeType.STRONG_TREND_UP)
    sh = tuple(b.__class__(ts=b.ts.replace(year=2014, month=2, day=3), open=b.open, high=b.high, low=b.low,
                           close=b.close, spread=b.spread, regime=b.regime) for b in bars)
    for i in inst: c.write(i, 2014, sh)
    return c
def grade(look, key="dukascopy", obj=src, **kw):
    return run_walk_forward(RunInputs(cfg=cfg, account="dev_paper", source=key,
        loader=BacktestDataLoader({key: obj}, CapturingLogger()), cache=cache(), folds=folds, spx_closes={},
        financing=None, work_dir=tmp / f"eng{next(_n)}", logger=CapturingLogger(), look=look, **kw))
def attempt(label, fn):
    try: out = fn(); print(f"  {label}: ALLOWED -> {out!r}"[:220])
    except LookRefused as e: print(f"  {label}: REFUSED -> {str(e)[:150]}")
    except Exception as e: print(f"  {label}: {type(e).__name__} (NOT LookRefused) -> {str(e)[:120]}")
reg = lambda root, fam, **k: LookRegister(root).register(cfg=cfg, source=src, instruments=inst, folds=folds,
                                                         family=fam, account="dev_paper", **k)
print("L1 a real-data look registered in a throwaway dir")
attempt("register in tmp/anywhere", lambda: reg(tmp / "anywhere", "trend-v1"))
print("L2 a source named 'dukascopy' loaded under the key 'synthetic'")
l2 = reg(CANONICAL, "l2-fam")
attempt("grade keyed 'synthetic'", lambda: grade(l2, key="synthetic"))
print("L3 one line, two grades (declared world, then 3x cost)")
l3 = reg(CANONICAL, "l3-fam")
attempt("first grade", lambda: grade(l3).look["look_id"])
attempt("second grade, 3x stress", lambda: grade(l3, cost_stress=3.0).look["look_id"])
print("L4 a hand-forged line on disk")
from dataclasses import asdict, replace; import json
forged = replace(l3, look_id="777777", path=str(CANONICAL / "777777.json"), git_commit="deadbeef")
(CANONICAL / "777777.json").write_text(json.dumps(asdict(forged), sort_keys=True), encoding="utf-8")
attempt("grade with the forged line", lambda: grade(forged))
(CANONICAL / "777777.json").unlink()
print("L5 an empty numbered file (power cut between create and write)")
r5 = tmp / "reg5"; LookRegister(r5).register(cfg=cfg, source=_Synthetic(), instruments=inst, folds=folds,
                                             family="f5", account="dev_paper") if hasattr(_Synthetic(), "provenance") else None
r5.mkdir(exist_ok=True); (r5 / "000009.json").write_bytes(b"")
attempt("scan", lambda: (lambda s: (len(s.lines), s.torn, s.broken))(LookRegister(r5).scan()))
print("RACE two concurrent first looks by one family")
out, errs = [], []
def go():
    try: out.append(reg(CANONICAL, "race-fam"))
    except Exception as e: errs.append(type(e).__name__ + ": " + str(e)[:90])
ts = [threading.Thread(target=go) for _ in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]
print("  registered:", [(l.look_id, repr(l.changed)) for l in out], "| refused:", errs)
