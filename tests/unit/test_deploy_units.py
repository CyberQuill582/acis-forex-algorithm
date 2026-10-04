"""GAP-P12D-134: the deploy units run the venv's interpreter (Debian 12 refuses pip into the system
Python, PEP 668), and the demo host's shell helpers parse."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "deploy" / "demo"


@pytest.mark.parametrize("unit", ["acis-engine.service", "acis-watchdog.service"])
def test_each_unit_runs_the_venv_interpreter(unit: str) -> None:
    lines = (ROOT / "deploy" / "systemd" / unit).read_text(encoding="utf-8").splitlines()
    execs = [line for line in lines if line.startswith("ExecStart=")]
    assert execs and all(line.startswith("ExecStart=/opt/acis/venv/bin/python ") for line in execs)


@pytest.mark.parametrize("drop_in", ["acis-watchdog.override.conf", "acis-watchdog.aws.conf"])
def test_the_demo_drop_in_resets_then_points_at_the_venv(drop_in: str) -> None:
    lines = (DEMO / drop_in).read_text(encoding="utf-8").splitlines()
    starts = [line for line in lines if line.startswith("ExecStart=")]
    assert starts == ["ExecStart=", "ExecStart=/opt/acis/venv/bin/python scripts/acis_watchdog.py"]


def test_the_aws_drop_in_runs_the_watchdog_as_acis() -> None:
    """Owner ruling 2026-10-01 ("Hybrid, on AWS"): the watchdog runs as the sudo-less `acis` user."""
    lines = (DEMO / "acis-watchdog.aws.conf").read_text(encoding="utf-8").splitlines()
    assert "User=acis" in lines and "Group=acis" in lines


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("script", [
    "demo/acis_setup.sh", "demo/set_human_token.sh", "aws/acis-demo-userdata.sh", "aws/acis-demo-prepare.sh",
])
def test_each_demo_helper_parses(script: str) -> None:
    bash = shutil.which("bash")                     # the found one: a bare "bash" can resolve to WSL on Windows
    done = subprocess.run([bash, "-n", (ROOT / "deploy" / script).as_posix()], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_aws_host_rotates_only_the_two_high_volume_logs_and_keeps_them_compressed() -> None:
    """GAP-P12D-138 (owner ruling 2026-10-04): data_log and signal_log rotate daily with copytruncate (the
    engine appends), compressed, kept 60 days; the evidence logs are never rotated away by this file."""
    conf = (ROOT / "deploy" / "aws" / "acis-logrotate.conf").read_text(encoding="utf-8")
    body = [ln.strip() for ln in conf.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert body[0] == "/opt/acis/repo/logs/data_log.jsonl /opt/acis/repo/logs/signal_log.jsonl {"
    assert {"daily", "rotate 60", "compress", "copytruncate", "su acis acis"} <= set(body)
    assert not any(e in body[0] for e in ("trade_log", "risk_log", "target_log", "governor_log", "venue_events"))
    prepare = (ROOT / "deploy" / "aws" / "acis-demo-prepare.sh").read_text(encoding="utf-8")
    assert "deploy/aws/acis-logrotate.conf /etc/logrotate.d/acis" in prepare
