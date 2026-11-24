from __future__ import annotations

import claims

KEYS = {"session", "pid", "pid_start", "run", "checkout", "branch", "since"}


def _claim() -> dict:
    return claims.make_claim("s1", 123, "Mon Nov 23 10:00:00 2026", "/r", "/c", "feature/x", "2026-11-23T10:00:00")


def test_us12_claim_name_joins_project_and_task():
    assert claims.claim_name("Developing", "x") == "Developing--x.json"


def test_us12_make_claim_has_exactly_the_seven_keys():
    assert set(_claim()) == KEYS


def test_us12_make_claim_keeps_given_values():
    c = _claim()
    assert (c["session"], c["pid"], c["pid_start"], c["branch"]) == ("s1", 123, "Mon Nov 23 10:00:00 2026", "feature/x")


def test_us12_dead_pid_is_stale():
    c = _claim()
    assert claims.is_stale(c, False, None) is True
    assert claims.is_stale(c, False, c["pid_start"]) is True


def test_us12_live_pid_with_same_start_is_not_stale():
    c = _claim()
    assert claims.is_stale(c, True, c["pid_start"]) is False


def test_us12_reused_pid_with_other_start_is_stale():
    assert claims.is_stale(_claim(), True, "Tue Nov 24 09:00:00 2026") is True
