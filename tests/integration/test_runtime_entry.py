"""`python -m core.runtime`, the engine unit's ExecStart: the documented commands run (master §10)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from config.account_doctrine import guardrail_hash, rulebook_hash
from core.runtime.__main__ import cli

CONFIG = Path(__file__).resolve().parents[2] / "config"


def deployment(tmp_path: Path) -> Path:
    shutil.copytree(CONFIG, tmp_path / "config")
    return tmp_path


def test_print_hashes_shows_exactly_what_practice_attests_to(tmp_path, acis_config, capsys) -> None:
    assert cli(["--root", str(deployment(tmp_path)), "--print-hashes", "--account", "pepperstone_demo"]) == 0
    out = capsys.readouterr().out
    assert guardrail_hash(acis_config.guardrails) in out
    assert rulebook_hash(acis_config.platform_rules.accounts["pepperstone_demo"]) in out


def test_a_paper_smoke_run_boots_in_paper_runs_and_beats(tmp_path) -> None:
    root = deployment(tmp_path)
    assert cli(["--root", str(root), "--mock-ticks", "50"]) == 0
    beat = json.loads((root / "logs" / "heartbeat.json").read_text(encoding="utf-8"))
    assert beat["mode"] == "paper" and beat["fast_loop_seq"] == 50 * 2      # two instruments
    stopped = [json.loads(line) for line in (root / "logs" / "system_log.jsonl").read_text(
        encoding="utf-8").splitlines() if '"ENGINE_STOPPED"' in line]
    assert stopped[-1]["data"]["outcome"] == "feed_ended"
    assert (root / "data" / "runtime" / "risk.db").exists()


def test_practice_is_refused_without_an_attached_venue(tmp_path) -> None:
    with pytest.raises(SystemExit) as refused:
        cli(["--root", str(deployment(tmp_path)), "--practice"])
    assert refused.value.code == 2
