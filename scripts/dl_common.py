"""Shared plumbing for the unattended downloaders (scripts/download_*.py) — one copy of
the log / status / lock / network-wait / disk-guard behaviour they all need.

A network failure never counts against a file: `wait_for_network` blocks until the
host is reachable again. The lock is an OS file lock, so it dies with the process and
can never go stale. Works on Windows (msvcrt) and POSIX (fcntl — CI runs Linux).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import time
from datetime import datetime, timezone
from pathlib import Path


class Ops:
    """Log, atomic status files, single-instance lock, network and disk guards for one
    download job rooted at `out`, talking to `host`."""

    def __init__(self, out: Path, host: str, disk_min_gb: float = 3.0) -> None:
        self.out, self.host, self.disk_min_gb = Path(out), host, disk_min_gb
        self.out.mkdir(parents=True, exist_ok=True)
        self.log_path = self.out / "download.log"
        self._lock_fh = None

    def log(self, msg: str) -> None:
        line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  {msg}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    @staticmethod
    def write_json(path: Path, obj) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
        os.replace(tmp, path)

    def acquire_lock(self) -> bool:
        fh = open(self.out / "download.lock", "a+")
        fh.seek(0)
        try:
            try:
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except ImportError:
                import fcntl
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._lock_fh = fh
        return True

    def online(self) -> bool:
        try:
            socket.create_connection((self.host, 443), timeout=10).close()
            return True
        except OSError:
            return False

    def wait_for_network(self) -> None:
        if self.online():
            return
        self.log("NETWORK DOWN - waiting for connectivity (checking every 30 s)...")
        t0 = time.time()
        while not self.online():
            time.sleep(30)
        self.log(f"NETWORK BACK after {round((time.time() - t0) / 60)} min - resuming")

    def free_gb(self) -> float:
        return shutil.disk_usage(self.out).free / 1e9

    def wait_for_disk(self) -> None:
        if self.free_gb() >= self.disk_min_gb:
            return
        self.log(f"DISK LOW ({self.free_gb():.1f} GB < {self.disk_min_gb}) - paused; free space")
        while self.free_gb() < self.disk_min_gb:
            time.sleep(600)
        self.log("DISK OK - resuming")
