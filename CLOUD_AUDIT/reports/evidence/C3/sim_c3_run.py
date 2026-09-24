"""C3 forensic driver: one real-engine walk-forward on a synthetic market, with per-trade records.

Run from a THROWAWAY copy of the repo at BASE (never the review tree):
    cd /tmp/acis-forensics && python <this> --kind planted --seed 7 --folds 4 --out /tmp/c3/runs/x

What it changes relative to scripts/cost_stress_ladder.py (all in-process, no source edits
except the env-gated AGON patch described in the C3 report):
  * the fold plan starts `--offset-days` after the market start, and TSMOM's daily history is
    seeded straight from the synthetic mid path (17:00 New York closes), so TSMOM is LIVE from
    the first graded tick (in GAP-P12D-49's run it went live only in fold ~8);
  * labels are built only over the union of the folds' train windows (plus the labeller's own
    3-day warm-up), not whole calendar years; NVMA and the labeller are the real ones;
  * the market seed (`--seed`) and an evolution-seed salt (`--evo-salt`) are parameters;
  * `--off` disables modules through a copied config (modules_enabled), `--no-veto` sets
    C3_TSMOM_NO_VETO for the AGON patch;
  * `--episode-hours`/`--drift-sigma` reshape the planted market (the horizon test);
  * every closed trade is recorded (strategy, direction, reason, gross, friction, net, planted
    sign at entry, episode boundaries crossed) by wrapping PositionModel.close_at.
Cost map, account, Governor, Backtest book, report and gates are the production ones.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import random
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

UTC = timezone.utc
NY = ZoneInfo("America/New_York")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="planted")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--evo-salt", default="")
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--train-days", type=int, default=60)
    ap.add_argument("--test-days", type=int, default=30)
    ap.add_argument("--offset-days", type=int, default=385)
    ap.add_argument("--off", nargs="*", default=[])
    ap.add_argument("--no-veto", action="store_true")
    ap.add_argument("--instruments", nargs="*", default=None)
    ap.add_argument("--episode-hours", nargs=2, type=float, default=None)
    ap.add_argument("--drift-sigma", type=float, default=None)
    ap.add_argument("--daily-vol", type=float, default=None)
    ap.add_argument("--cost-stress", type=float, default=1.0)
    ap.add_argument("--max-hold-h", type=float, default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.no_veto:
        os.environ["C3_TSMOM_NO_VETO"] = "1"
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "logs").mkdir(parents=True)

    # -- config variant --------------------------------------------------------------------
    cfg_dir = out / "config"
    shutil.copytree(ROOT / "config", cfg_dir)
    sysyaml = cfg_dir / "system_config.yaml"
    text = sysyaml.read_text()
    for m in a.off:
        old = f"    {m}: true\n"
        assert text.count(old) == 1, m
        text = text.replace(old, f"    {m}: false\n")
    sysyaml.write_text(text)
    if a.instruments is not None:
        iy = cfg_dir / "instruments.yaml"
        t = iy.read_text()
        for inst in ("EUR_USD", "USD_JPY"):
            if inst not in a.instruments:
                old = f"  {inst}:\n    enabled: true\n"
                assert t.count(old) == 1
                t = t.replace(old, f"  {inst}:\n    enabled: false\n")
        iy.write_text(t)

    from config.schemas import load_config
    import tests.backtest.evolve_step as evolve_step
    import tests.backtest.oos_runner as oos_runner
    import tests.backtest.harness as harness
    from tests.backtest.book import PositionModel
    from tests.backtest.money import quote_to_account
    from core.data.jsonl_logging import JsonlEventLogger
    from tests.backtest.replay_logging import ReplayEventLogger
    from tests.backtest.data_loader import BacktestDataLoader
    from tests.backtest.regime_labels import (LABEL_WARMUP, LabelledBarCache, LabelSpec,
                                              build_nvma, label_bars)
    from tests.backtest.tick_stream import build_factory, market_states
    from tests.backtest.synthetic_grade import FIRST_MID, START, plan
    from tests.backtest.synthetic_market import MarketSpec, SyntheticMarket, synthetic_spx

    cfg = load_config(cfg_dir)
    instruments = sorted(cfg.instruments.enabled)
    t_start = START + timedelta(days=a.offset_days)
    t_start = t_start - timedelta(days=t_start.weekday())          # keep a Monday
    folds = plan(a.train_days, a.test_days, a.folds, start=t_start)
    days = (folds[-1].test_end - START).days
    kw = {"seed": a.seed}
    if a.episode_hours:
        kw["episode_hours"] = tuple(a.episode_hours)
    if a.drift_sigma is not None:
        kw["drift_sigma"] = a.drift_sigma
    if a.daily_vol is not None:
        kw["daily_vol"] = a.daily_vol
    spec = MarketSpec(a.kind, START, days, tuple((i, FIRST_MID[i]) for i in instruments), **kw)
    market = SyntheticMarket(spec)

    def logger(name, layer, keep):
        return ReplayEventLogger(JsonlEventLogger(out / "logs" / f"{name}.jsonl", layer=layer,
                                                  session_id=f"c3-{name}"), keep_per_type=keep)

    # -- tick-index <-> time, planted episode schedule ----------------------------------
    tps = spec.ticks_per_day

    def index_of(ts: datetime) -> int:
        d = (ts - spec.start).days
        wk, wd = divmod(d, 7)
        if wd >= 5:
            return (wk * 5 + 5) * tps
        sec = (ts - (spec.start + timedelta(days=d))).total_seconds()
        return (wk * 5 + wd) * tps + int(sec // spec.tick_seconds)

    ep_starts, ep_signs = [], []
    if a.kind == "planted":
        idx = instruments.index(instruments[0])
        # rebuild the schedule exactly as synthetic_market._returns draws it (instrument 0 and 1
        # have different schedules; keep one per instrument)
    schedules = {}
    for k, inst in enumerate(instruments):
        rng = random.Random(spec.seed * 1000 + k)
        n = spec.weekdays() * tps
        sigma = spec.daily_vol / math.sqrt(tps)
        for _ in range(n):
            rng.gauss(0.0, sigma)
        starts, signs = [], []
        if a.kind != "null":
            lo, hi = (max(1, round(h * 3600 / spec.tick_seconds)) for h in spec.episode_hours)
            j = 0
            while j < n:
                length = rng.randint(lo, hi)
                sgn = rng.choice((-1.0, 1.0))
                starts.append(j)
                signs.append(sgn)
                j += length
        schedules[inst] = (starts, signs)

    def planted_sign(inst, ts):
        starts, signs = schedules[inst]
        if not starts or a.kind != "planted":
            return 0
        return int(signs[bisect.bisect_right(starts, index_of(ts)) - 1])

    def boundaries(inst, t0, t1):
        starts, _ = schedules[inst]
        if not starts or a.kind != "planted":
            return 0
        return bisect.bisect_right(starts, index_of(t1)) - bisect.bisect_right(starts, index_of(t0))

    # -- TSMOM seed straight from the mid path -------------------------------------------
    def closes_until(inst, end):
        path = market._path(inst)
        outc = []
        d = spec.start.date()
        while True:
            ny = datetime(d.year, d.month, d.day, 17, 0, tzinfo=NY).astimezone(UTC)
            if ny > end:
                break
            if d.weekday() < 5:
                i = index_of(ny) - 1
                if 0 <= i < len(path):
                    outc.append((d, math.exp(path[i])))
            d += timedelta(days=1)
        return outc

    seeded = {}

    def seed_tsmom(agon, instrument, _closes):
        closes = closes_until(instrument, folds[0].train_end)
        for _, c in closes:
            agon.observe_daily_close(instrument, c)
        seeded[instrument] = len(closes)
        return len(closes)

    oos_runner.seed_tsmom = seed_tsmom

    if a.evo_salt:
        orig_seed_for = evolve_step.seed_for

        def salted(fold_index, regime, instrument):
            return orig_seed_for(fold_index, regime, instrument + "|" + a.evo_salt)
        evolve_step.seed_for = salted

    if a.max_hold_h is not None:
        orig_init = harness.Backtest.__init__

        def init(self, **k):
            k["max_hold_s"] = a.max_hold_h * 3600
            orig_init(self, **k)
        harness.Backtest.__init__ = init

    # -- per-trade recorder ------------------------------------------------------------
    trades = []
    orig_close = PositionModel.close_at

    def close_at(self, pos, exit_price, ts, reason, book, exit_spread=0.0):
        ct = orig_close(self, pos, exit_price, ts, reason, book, exit_spread)
        to_acct = quote_to_account(pos.instrument, exit_price, book.last_price)
        gross = (Decimal(str(exit_price)) - Decimal(str(pos.entry_price))) * pos.direction \
            * pos.size_units * to_acct
        trades.append({
            "strategy": pos.strategy_type, "instrument": pos.instrument, "dir": pos.direction,
            "entry_ts": pos.entry_ts.isoformat(), "exit_ts": ts.isoformat(),
            "dur_h": round((ts - pos.entry_ts).total_seconds() / 3600, 4), "reason": reason,
            "regime": pos.regime, "units": str(pos.size_units),
            "gross": float(gross), "net": float(ct.pnl), "friction": float(gross - ct.pnl),
            "sign_at_entry": planted_sign(pos.instrument, pos.entry_ts),
            "boundaries": boundaries(pos.instrument, pos.entry_ts, ts)})
        return ct
    PositionModel.close_at = close_at

    # -- labels over the train windows only --------------------------------------------
    t0 = time.perf_counter()
    cache = LabelledBarCache(out / "labels", LabelSpec.for_config(cfg, market.name, START))
    lab_log = logger("labels", "labels", 20)
    loader = BacktestDataLoader({market.name: market}, lab_log)
    lab_start = folds[0].train_start - LABEL_WARMUP
    lab_end = folds[-1].train_end
    nbars = 0
    for inst in instruments:
        factory = build_factory(cfg, [inst])
        engine = build_nvma(cfg, factory, lab_log)
        states = market_states(cfg=cfg, loader=loader, factory=factory, source=market.name,
                               instruments=[inst], start=lab_start, end=lab_end)
        by_year = {}
        for _, b in label_bars(states, engine, cycle_s=cfg.system.regime.cycle_seconds,
                               bar_seconds=cfg.system.signals.signal_bar_seconds):
            if b.ts >= folds[0].train_start:
                by_year.setdefault(b.ts.year, []).append(b)
        for y in range(lab_start.year, lab_end.year + 1):
            nbars += cache.write(inst, y, by_year.get(y, []))
    lab_log.close()
    t_label = time.perf_counter() - t0

    # -- grade -------------------------------------------------------------------------
    t1 = time.perf_counter()
    log = logger("run", "backtest", 200)
    report = oos_runner.run_walk_forward(oos_runner.RunInputs(
        cfg=cfg, account=cfg.system.active_account, source=market.name,
        loader=BacktestDataLoader({market.name: market}, log), cache=cache, folds=folds,
        spx_closes=synthetic_spx(START, spec.days), financing=None, work_dir=out / "engine",
        logger=log, cost_stress=a.cost_stress))
    log.close()
    t_grade = time.perf_counter() - t1
    (out / "report.json").write_text(oos_runner.report_json(report))

    with open(out / "trades.csv", "w", newline="") as f:
        if trades:
            w = csv.DictWriter(f, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    per = {}
    for t in trades:
        p = per.setdefault(t["strategy"], {"n": 0, "net": 0.0, "gross": 0.0, "friction": 0.0,
                                           "dur_h": 0.0, "with_sign": 0, "signed_n": 0,
                                           "reasons": {}})
        p["n"] += 1
        p["net"] += t["net"]
        p["gross"] += t["gross"]
        p["friction"] += t["friction"]
        p["dur_h"] += t["dur_h"]
        if t["sign_at_entry"]:
            p["signed_n"] += 1
            p["with_sign"] += int(t["sign_at_entry"] == t["dir"])
        p["reasons"][t["reason"]] = p["reasons"].get(t["reason"], 0) + 1
    for p in per.values():
        p["dur_h"] /= max(1, p["n"])
    oos = report.out_of_sample
    summary = {
        "args": vars(a), "instruments": instruments, "tsmom_seeded_closes": seeded,
        "folds": [[f.train_start.isoformat(), f.train_end.isoformat(), f.test_start.isoformat(),
                   f.test_end.isoformat()] for f in folds],
        "label_bars": nbars, "seconds_label": t_label, "seconds_grade": t_grade,
        "passed": report.passed, "n_trades": oos.n_trades, "sharpe": oos.annual_sharpe,
        "net": sum(t["net"] for t in trades), "gross": sum(t["gross"] for t in trades),
        "champions": [r["champions"] for r in report.in_sample_evolution],
        "per_strategy": per,
        "report_per_strategy": {k: str(v.net_pnl) for k, v in report.per_strategy.items()},
        "open_at_end": len(getattr(report, "open_positions", []) or []),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: summary[k] for k in ("passed", "n_trades", "sharpe", "net", "gross",
                                               "seconds_label", "seconds_grade", "champions")},
                     default=str))
    for k, p in sorted(per.items()):
        print(f"  {k:16s} n={p['n']:4d} net={p['net']:9.2f} gross={p['gross']:9.2f} "
              f"fric={p['friction']:7.2f} dur_h={p['dur_h']:6.2f} "
              f"hit={p['with_sign']}/{p['signed_n']} {p['reasons']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
