from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import claims  # noqa: E402
from effects import claimfiles  # noqa: E402

NAME = "proj--task-1.json"


def _claim(session: str, pid: int, run: str = "run-a", checkout: str = "/co/a", branch: str = "feature/a") -> dict:
    return claims.make_claim(session, pid, f"start-{pid}", run, checkout, branch, "2026-01-01T00:00:00")


def _alive(pids: set[int]):
    return lambda pid: pid in pids


def _start(pid: int) -> str | None:
    return f"start-{pid}"


def _acquire(active: Path, claim: dict, alive_pids: set[int], logs: list[str]):
    return claims.acquire(active, NAME, claim, _alive(alive_pids), _start, logs.append)


def test_us12_acquire_creates_when_no_claim(tmp_path: Path) -> None:
    logs: list[str] = []
    mine = _claim("s1", 1)
    outcome, holder = _acquire(tmp_path, mine, {1}, logs)
    assert outcome == "created"
    assert claimfiles.read(tmp_path, NAME) == mine


def test_us12_acquire_own_claim_refreshes_run_checkout_branch(tmp_path: Path) -> None:
    logs: list[str] = []
    claimfiles.create(tmp_path, NAME, _claim("s1", 1))
    newer = _claim("s1", 1, run="run-b", checkout="/co/b", branch="feature/b")
    outcome, _ = _acquire(tmp_path, newer, {1}, logs)
    assert outcome == "own"
    stored = claimfiles.read(tmp_path, NAME)
    assert stored["session"] == "s1"
    assert (stored["run"], stored["checkout"], stored["branch"]) == ("run-b", "/co/b", "feature/b")


def test_us12_acquire_takes_over_stale_claim(tmp_path: Path) -> None:
    logs: list[str] = []
    claimfiles.create(tmp_path, NAME, _claim("old", 1))
    mine = _claim("s2", 2)
    outcome, _ = _acquire(tmp_path, mine, {2}, logs)
    assert outcome == "taken_over"
    assert claimfiles.read(tmp_path, NAME) == mine


def test_us12_acquire_takes_over_when_pid_reused(tmp_path: Path) -> None:
    logs: list[str] = []
    stale = claims.make_claim("old", 1, "different-start", "r", "/c", "b", "t")
    claimfiles.create(tmp_path, NAME, stale)
    outcome, _ = _acquire(tmp_path, _claim("s2", 2), {1, 2}, logs)
    assert outcome == "taken_over"
    assert claimfiles.read(tmp_path, NAME)["session"] == "s2"


def test_us12_acquire_refuses_live_claim_and_returns_holder(tmp_path: Path) -> None:
    logs: list[str] = []
    theirs = _claim("s1", 1)
    claimfiles.create(tmp_path, NAME, theirs)
    outcome, holder = _acquire(tmp_path, _claim("s2", 2), {1, 2}, logs)
    assert outcome == "refused"
    assert holder == theirs


def test_us13_refused_leaves_other_sessions_claim_in_file(tmp_path: Path) -> None:
    logs: list[str] = []
    theirs = _claim("s1", 1)
    claimfiles.create(tmp_path, NAME, theirs)
    _acquire(tmp_path, _claim("s2", 2, run="run-z"), {1, 2}, logs)
    assert claimfiles.read(tmp_path, NAME) == theirs


def test_us13_second_session_in_a_row_is_refused(tmp_path: Path) -> None:
    logs: list[str] = []
    first, _ = _acquire(tmp_path, _claim("s1", 1), {1, 2}, logs)
    second, holder = _acquire(tmp_path, _claim("s2", 2), {1, 2}, logs)
    assert first == "created"
    assert second == "refused"
    assert holder["session"] == "s1"
    assert claimfiles.read(tmp_path, NAME)["session"] == "s1"


def test_us12_takeover_logs_once_naming_task_and_old_session(tmp_path: Path) -> None:
    logs: list[str] = []
    claimfiles.create(tmp_path, NAME, _claim("old", 1))
    _acquire(tmp_path, _claim("s2", 2), {2}, logs)
    assert logs == [f"takeover {NAME} from old"]


def test_us12_created_and_own_do_not_log(tmp_path: Path) -> None:
    logs: list[str] = []
    _acquire(tmp_path, _claim("s1", 1), {1}, logs)
    _acquire(tmp_path, _claim("s1", 1, run="run-b"), {1}, logs)
    assert logs == []


def test_us13_refused_does_not_log(tmp_path: Path) -> None:
    logs: list[str] = []
    claimfiles.create(tmp_path, NAME, _claim("s1", 1))
    _acquire(tmp_path, _claim("s2", 2), {1, 2}, logs)
    assert logs == []
