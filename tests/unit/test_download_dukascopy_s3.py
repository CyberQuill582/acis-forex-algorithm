"""Offline tests of the Dukascopy S3 downloader's pipeline (scripts/download_dukascopy_s3.py):
verification runs while the next year syncs, and a killed run can always resume."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import download_dukascopy_s3 as m  # noqa: E402


class FakeOps:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, msg: str) -> None:
        self.lines.append(msg)

    def acquire_lock(self) -> bool:
        return True

    def wait_for_network(self) -> None:
        pass

    def wait_for_disk(self) -> None:
        pass

    def free_gb(self) -> float:
        return 100.0

    write_json = staticmethod(lambda path, obj: Path(path).write_text(json.dumps(obj)))


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    out = tmp_path / "dukascopy"
    out.mkdir()
    monkeypatch.setattr(m, "OUT", out)
    monkeypatch.setattr(m, "MANIFEST", out / "manifest.jsonl")
    monkeypatch.setattr(m, "STATUS", out / "status.json")
    monkeypatch.setattr(m, "COMPLETE", out / "COMPLETE")
    monkeypatch.setattr(m, "YEARS", [2025, 2024])
    monkeypatch.setattr(m, "SYMBOLS", {"EUR_USD": ("EURUSD", None)})
    ops = FakeOps()
    monkeypatch.setattr(m, "OPS", ops)
    return out, ops


def test_verification_runs_while_the_next_year_syncs(repo, monkeypatch) -> None:
    out, _ = repo
    synced = {2025: threading.Event(), 2024: threading.Event()}
    order: list[str] = []

    def fake_sync(src, dest):
        year = int(dest.name)
        dest.mkdir(parents=True, exist_ok=True)
        order.append(f"sync {year}")
        synced[year].set()

    def fake_verify(inst, year, dest, known):
        if year == 2025:                    # blocks until 2024 syncs — only possible if concurrent
            assert synced[2024].wait(timeout=5), "2024 did not sync while 2025 was verifying"
        order.append(f"verified {year}")
        return 1, 0

    monkeypatch.setattr(m, "sync", fake_sync)
    monkeypatch.setattr(m, "verify_dir", fake_verify)
    assert m.cmd_run() == 0
    assert order.index("sync 2024") < order.index("verified 2025")
    assert (out / "EUR_USD" / "2025" / "SYNCED").exists()
    assert (out / "EUR_USD" / "2024" / "SYNCED").exists()
    assert m.COMPLETE.exists()


def test_a_year_that_fails_verification_is_not_marked_synced(repo, monkeypatch) -> None:
    out, ops = repo
    monkeypatch.setattr(m, "sync", lambda src, dest: dest.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(m, "verify_dir",
                        lambda inst, year, dest, known: (0, 1) if year == 2024 else (1, 0))
    assert m.cmd_run() == 1                                   # the supervisor reruns the pass
    assert (out / "EUR_USD" / "2025" / "SYNCED").exists()
    assert not (out / "EUR_USD" / "2024" / "SYNCED").exists()
    assert not m.COMPLETE.exists()
    assert any(line.startswith("RETRY EUR_USD 2024") for line in ops.lines)


def test_a_verifier_crash_is_not_swallowed(repo, monkeypatch) -> None:
    monkeypatch.setattr(m, "sync", lambda src, dest: dest.mkdir(parents=True, exist_ok=True))

    def boom(inst, year, dest, known):
        raise OSError("disk went away")

    monkeypatch.setattr(m, "verify_dir", boom)
    with pytest.raises(OSError):
        m.cmd_run()
    assert not m.COMPLETE.exists()


def test_a_cut_off_manifest_line_is_skipped_and_healed(repo) -> None:
    good = json.dumps({"file": "data/dukascopy/EUR_USD/2025/00/02_ticks.bi5"})
    m.MANIFEST.write_text(good + "\n" + '{"instrument": "EUR_USD", "fi', encoding="utf-8")
    assert m.load_known() == {"data/dukascopy/EUR_USD/2025/00/02_ticks.bi5"}
    m.heal_manifest()
    assert m.MANIFEST.read_bytes().endswith(b"\n")
    with m.MANIFEST.open("a", encoding="utf-8") as f:         # the next record lands on its own line
        f.write(json.dumps({"file": "x"}) + "\n")
    assert m.load_known() == {"data/dukascopy/EUR_USD/2025/00/02_ticks.bi5", "x"}


def test_sync_clears_partial_transfers_of_a_killed_run(repo, monkeypatch) -> None:
    out, _ = repo
    month = out / "EUR_USD" / "2025" / "02"
    month.mkdir(parents=True)
    (month / "28_ticks.bi5.fb5608ce").write_bytes(b"")        # aws CLI temp name
    (month / "27_ticks.bi5").write_bytes(b"keep")
    monkeypatch.setattr(m, "aws", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    m.sync("s3://bucket/EURUSD/2025/", out / "EUR_USD" / "2025")
    assert not (month / "28_ticks.bi5.fb5608ce").exists()
    assert (month / "27_ticks.bi5").read_bytes() == b"keep"
