"""Run the §14 out-of-sample walk-forward validation for one account (ACIS-09 §7, GAP-P12D-23).

    python scripts/run_oos_validation.py --family trend-v1 --origin llm --model-id <model> \\
        --model-cutoff <YYYY-MM-DD> --proposed <YYYY-MM-DD> --exposure repository --recon-commit <sha>
    (add --changed "..." after a family's first look; --final-holdout grades 2024–2025, ONCE)

LLM agents designed and refined the engine, so its origin is `llm` (master §5.6). A human label on an
LLM-originated variant is refused, and real-data looks stay CLOSED until R1.4 (GAP-P12D-127).

Every run is a LOOK (GAP-P12D-64), registered BEFORE anything is graded. Needs the Dukascopy
mirror, the labelled-bar cache (scripts/build_labelled_bars.py) and data/macro; writes
data/validation/oos/<run id>/report.json. A development run is never the final grade, and the
pipeline is falsified on synthetic data first (GAP-P12D-28).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.account_doctrine import guardrail_hash  # noqa: E402
from config.schemas import load_config  # noqa: E402
from core.data.jsonl_logging import JsonlEventLogger  # noqa: E402
from tests.backtest.data_loader import BacktestDataLoader  # noqa: E402
from tests.backtest.financing import load_rate_table, make_financing  # noqa: E402
from tests.backtest.look_claims import ORIGINS, Claim, Origin  # noqa: E402
from tests.backtest.look_register import LookRefused, LookRegister, config_hash, git_state  # noqa: E402
from tests.backtest.oos_plan import DATA_START, HOLDOUT_END, HOLDOUT_START, HoldoutGuard, plan_folds  # noqa: E402
from tests.backtest.oos_runner import (RunInputs, load_spx_closes, missing_labels,  # noqa: E402
                                       report_json, run_walk_forward)
from tests.backtest.regime_labels import LabelledBarCache, LabelSpec  # noqa: E402
from tests.backtest.replay_logging import ReplayEventLogger  # noqa: E402
from tests.backtest.sources import DukascopyTickSource  # noqa: E402

SOURCE = "dukascopy"


def main() -> int:
    cfg = load_config(ROOT / "config")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account", default=cfg.system.active_account)
    ap.add_argument("--first-test-year", type=int, default=2014)
    ap.add_argument("--last-test-year", type=int, default=2023)
    ap.add_argument("--final-holdout", action="store_true")
    ap.add_argument("--family", required=True, help="the hypothesis family this look belongs to (GAP-P12D-64)")
    ap.add_argument("--changed", default="", help="what changed since the family's previous look (required after its first)")
    ap.add_argument("--operator", default=None, help="who ran it (default: the OS user)")
    ap.add_argument("--origin", required=True, choices=ORIGINS, help="who originated the hypothesis (master §5.6)")
    ap.add_argument("--model-id", default="", help="the model that proposed (or selected) the hypothesis")
    ap.add_argument("--model-cutoff", default="", help="that model's training-data cutoff, YYYY-MM-DD")
    ap.add_argument("--proposed", default="", help="when the model proposed or selected it, YYYY-MM-DD")
    ap.add_argument("--exposure", default="", help="none | web | repository: what the proposer could read")
    ap.add_argument("--reference", default="", help="a literature origin's citation")
    ap.add_argument("--published", default="", help="its publication date, YYYY-MM-DD")
    ap.add_argument("--recon-commit", required=True, help="the commit at which B0 held (ACIS-09 C-BT-11 v2)")
    a = ap.parse_args()
    instruments = sorted(cfg.instruments.enabled)
    try:   # the engine's searched space is its config: the QIEA gene ranges and module switches
        claim = Claim(family=a.family, variant="engine", universe_id="enabled:" + ",".join(instruments),
                      declared_space={"grid": {"config_hash": config_hash(cfg), "code": git_state()[0]},
                                      "instruments": instruments,
                                      "formula": "ACIS engine: AGON modules routed by NVMA, QIEA per instrument x regime per fold"},
                      origin=Origin(a.origin, model_id=a.model_id, model_cutoff=a.model_cutoff,
                                    proposed=a.proposed, exposure=a.exposure, reference=a.reference,
                                    published=a.published),
                      simulator="engine", recon_commit=a.recon_commit)
    except ValueError as exc:
        print("refused:", exc)
        return 2

    folds = (plan_folds(HOLDOUT_START.year, HOLDOUT_END.year - 1) if a.final_holdout
             else plan_folds(a.first_test_year, a.last_test_year))
    guard = HoldoutGuard(ROOT / "data" / "validation" / "holdout_graded.json")
    cache = LabelledBarCache(ROOT / "data" / "labelled_bars", LabelSpec.for_config(cfg, SOURCE, DATA_START))
    missing = missing_labels(cache, sorted(cfg.instruments.enabled), folds)
    if missing:
        print("refused: labelled bars missing for", ", ".join(f"{i} {y}" for i, y in missing),
              "— run scripts/build_labelled_bars.py first")
        return 2
    source = DukascopyTickSource(ROOT / "data" / "dukascopy")
    try:   # GAP-P12D-64: the line is written BEFORE any grade, and before the holdout's marker
        look = LookRegister(ROOT / "data" / "validation" / "looks").register(
            cfg=cfg, source=source, instruments=instruments, folds=folds,
            family=a.family, account=a.account, changed=a.changed, operator=a.operator, claim=claim)
    except LookRefused as exc:
        print("refused:", exc)
        return 2
    print(f"look {look.look_id} registered: family {look.family}, tier {look.tier_name}, commit {look.git_commit}"
          + (" (dirty tree)" if look.git_dirty else ""))
    if a.final_holdout:
        guard.begin_final(folds, config_hash=guardrail_hash(cfg.guardrails))   # graded ONCE
    else:
        guard.check_development(folds)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ("-FINAL" if a.final_holdout else "")
    out = ROOT / "data" / "validation" / "oos" / run_id
    out.mkdir(parents=True, exist_ok=True)
    log = ReplayEventLogger(JsonlEventLogger(out / "run_log.jsonl", layer="backtest", session_id=run_id),
                            keep_per_type=200)
    macro = ROOT / "data" / "macro"
    report = run_walk_forward(RunInputs(
        cfg=cfg, account=a.account, source=SOURCE,
        loader=BacktestDataLoader({SOURCE: source}, log),
        cache=cache, folds=folds, spx_closes=load_spx_closes(macro / "spx_yahoo.csv"),
        financing=make_financing(load_rate_table(macro)), work_dir=out / "engine", logger=log, look=look))
    log.close()
    (out / "report.json").write_text(report_json(report), encoding="utf-8")
    print(f"{'FINAL HOLDOUT' if a.final_holdout else 'development'} run {run_id}: "
          f"passed={report.passed}  trades={report.out_of_sample.n_trades}  "
          f"deflated_sharpe={report.deflated_sharpe}  trials={report.trial_count}")
    for family, tiers in report.look["family_looks"].items():
        print(f"  looks by family: {family}: " + ", ".join(f"{n} {t}" for t, n in tiers.items()))
    for caveat in report.fidelity_caveats:
        print("  caveat:", caveat)
    print("report:", out / "report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
