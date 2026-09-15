"""The mutation gate's own honesty (GAP-P12D-28): a mutant that breaks an import is a kill, and
mutmut's exit bits are read as what they mean."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mutation_gate", REPO / "scripts" / "mutation_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.mark.parametrize("pytest_exit, reported", [(0, 0), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1)])
def test_every_failing_test_run_counts_as_a_kill(pytest_exit: int, reported: int) -> None:
    """mutmut 2 kills only on exit 1; pytest's 2 is a collection error — an import-breaking mutant."""
    seen = {}

    def fake_run(cmd, cwd, env):
        seen["cmd"], seen["cwd"], seen["env"] = cmd, cwd, env
        return subprocess.CompletedProcess(cmd, pytest_exit)

    assert gate.run_tests(run=fake_run) == reported
    assert seen["cwd"] == gate.REPO and all(t in seen["cmd"] for t in gate.TESTS)
    assert seen["env"]["PYTHONDONTWRITEBYTECODE"] == "1"       # no stale .pyc can run a wrong mutant


@pytest.mark.parametrize("code, word", [(1, "FAILED TO RUN"), (3, "FAILED TO RUN"), (2, "SURVIVING"),
                                        (4, "timeouts"), (0, None)])
def test_the_verdict_reads_mutmuts_exit_bits(code: int, word: str | None, capsys) -> None:
    assert gate._verdict(code) == code
    err = capsys.readouterr().err
    assert (word in err) if word else err == ""


def test_the_gate_names_real_files_and_runs_through_the_shim() -> None:
    assert gate._config_ok()
    assert gate.RUNNER.endswith("--run-tests")
