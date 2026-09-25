"""A declared `initial_capital` is validated at load: finite and > 0; a typo is fatal
(audit F6: a dropped zero, 600 for 6,000, silently disabled the static max-loss rule, and
`.inf` was accepted). The shipped config is never edited: every case loads a TEMPORARY
copy of the config directory with one rulebook line changed."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from config.schemas import ConfigError, load_config

CONFIG = Path(__file__).resolve().parents[2] / "config"
LINE = "  ftmo:                             # reputability anchor — 12-yr payout track record\n"


def _load_with(tmp_path: Path, extra: str):
    cfg_dir = tmp_path / "config"
    shutil.copytree(CONFIG, cfg_dir)
    rules = cfg_dir / "platform_rules.yaml"
    text = rules.read_text(encoding="utf-8")
    assert text.count(LINE) == 1
    rules.write_text(text.replace(LINE, LINE + extra), encoding="utf-8")
    return load_config(cfg_dir)


def test_a_valid_initial_capital_loads(tmp_path) -> None:
    cfg = _load_with(tmp_path, "    initial_capital: 10000.0\n")
    assert cfg.platform_rules.accounts["ftmo"].initial_capital == 10000.0


@pytest.mark.parametrize("extra", [
    "    initial_capital: .inf\n",              # not finite
    "    initial_capital: .nan\n",
    "    initial_capital: 0\n",                 # not > 0
    "    initial_capital: -6000\n",
    "    initial_capital: 10O00\n",             # a letter O for a zero: not a number
    "    initial_capitol: 10000\n",             # a misspelt key
])
def test_a_typo_in_initial_capital_is_fatal_at_load(tmp_path, extra) -> None:
    with pytest.raises(ConfigError):
        _load_with(tmp_path, extra)
