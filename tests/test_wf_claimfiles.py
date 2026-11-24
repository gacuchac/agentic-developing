from __future__ import annotations

import json

from effects import claimfiles


def test_us12_second_create_returns_false_and_keeps_first(tmp_path):
    active = tmp_path / "active"
    assert claimfiles.create(active, "a.json", {"session": "s1"}) is True
    assert claimfiles.create(active, "a.json", {"session": "s2"}) is False
    assert claimfiles.read(active, "a.json") == {"session": "s1"}


def test_us12_create_makes_missing_active_dir(tmp_path):
    active = tmp_path / "x" / "active"
    assert claimfiles.create(active, "a.json", {"session": "s1"}) is True
    assert json.loads((active / "a.json").read_text()) == {"session": "s1"}


def test_us12_read_missing_is_none(tmp_path):
    assert claimfiles.read(tmp_path, "nope.json") is None


def test_us12_read_corrupt_is_none(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    assert claimfiles.read(tmp_path, "bad.json") is None


def test_us12_remove_deletes_and_missing_is_fine(tmp_path):
    claimfiles.create(tmp_path, "a.json", {"session": "s1"})
    claimfiles.remove(tmp_path, "a.json")
    assert claimfiles.read(tmp_path, "a.json") is None
    claimfiles.remove(tmp_path, "a.json")


def test_us12_owned_by_returns_only_that_sessions_names(tmp_path):
    claimfiles.create(tmp_path, "a.json", {"session": "s1"})
    claimfiles.create(tmp_path, "b.json", {"session": "s2"})
    claimfiles.create(tmp_path, "c.json", {"session": "s1"})
    assert sorted(claimfiles.owned_by(tmp_path, "s1")) == ["a.json", "c.json"]
    assert claimfiles.owned_by(tmp_path, "s3") == []
