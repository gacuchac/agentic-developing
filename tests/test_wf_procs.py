from __future__ import annotations

import os
import subprocess

import procs


def test_us12_current_process_is_alive():
    assert procs.pid_alive(os.getpid()) is True


def test_us12_current_process_start_is_stable_nonempty():
    first = procs.pid_start(os.getpid())
    assert first
    assert first == first.strip()
    assert procs.pid_start(os.getpid()) == first


def test_us12_exited_child_is_not_alive_and_has_no_start():
    child = subprocess.Popen(["true"])
    child.wait()
    assert procs.pid_alive(child.pid) is False
    assert procs.pid_start(child.pid) is None
