# Distributed under the terms of the GNU General Public License v3 (GPLv3).
"""Unit tests for :func:`psychopy_eyetracker_eyetribe.clear_stale_servers`.

psutil is fully mocked so no real process is ever inspected or killed.
"""

from __future__ import annotations

import os

import psutil
import pytest

from psychopy_eyetracker_eyetribe import clear_stale_servers


class _FakeProc:
    def __init__(self, pid: int, cmdline: list[str]) -> None:
        self.pid = pid  # real psutil.Process exposes .pid
        self.info = {"pid": pid, "cmdline": cmdline}
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def _patch_psutil(monkeypatch: pytest.MonkeyPatch, procs: list[_FakeProc]) -> list[_FakeProc]:
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: list(procs))
    waited: list[_FakeProc] = []
    monkeypatch.setattr(psutil, "wait_procs", lambda victims, timeout=None: waited.extend(victims))
    return waited


def test_kills_other_iohub_servers_and_returns_pids(monkeypatch: pytest.MonkeyPatch) -> None:
    me = os.getpid()
    orphan_a = _FakeProc(1111, ["python.exe", "start_iohub_process.py", "0.0"])
    orphan_b = _FakeProc(2222, ["python.exe", r"C:\x\start_iohub_process.py"])
    unrelated = _FakeProc(3333, ["python.exe", "some_experiment.py"])
    myself = _FakeProc(me, ["python.exe", "start_iohub_process.py"])  # never kill self
    _patch_psutil(monkeypatch, [orphan_a, orphan_b, unrelated, myself])

    killed = clear_stale_servers()

    assert sorted(killed) == [1111, 2222]
    assert orphan_a.killed and orphan_b.killed
    assert not unrelated.killed
    assert not myself.killed  # current process is excluded even if it matches


def test_no_orphans_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    unrelated = _FakeProc(4444, ["python.exe", "pytest"])
    _patch_psutil(monkeypatch, [unrelated])

    assert clear_stale_servers() == []
    assert not unrelated.killed


def test_skips_dead_processes_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Vanishing(_FakeProc):
        def kill(self) -> None:
            raise psutil.NoSuchProcess(self.info["pid"])

    gone = _Vanishing(5555, ["python", "start_iohub_process.py"])
    _patch_psutil(monkeypatch, [gone])

    # The PID is still reported (we attempted it); the raise is swallowed.
    assert clear_stale_servers() == [5555]
