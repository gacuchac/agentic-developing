"""Tests for schema.check: generic recursive shape check (US-10)."""

import copy

import pytest

import schema


def errs(sch, value, path=""):
    out = schema.check(sch, value, path)
    assert isinstance(out, list) and all(isinstance(e, str) for e in out)
    return out


# leaf types
@pytest.mark.parametrize("sch,value", [(str, "a"), (int, 3), (bool, True), (int, 0), (bool, False)])
def test_us10_leaf_matching_value_gives_no_errors(sch, value):
    assert errs(sch, value) == []


@pytest.mark.parametrize("sch,value", [(str, 3), (int, "3"), (bool, "x"), (int, 1.5), (str, None), (int, None)])
def test_us10_leaf_wrong_type_gives_one_error_naming_path(sch, value):
    out = errs(sch, value, "x")
    assert len(out) == 1 and "x" in out[0]


def test_us10_bool_is_not_int():
    out = errs(int, True, "n")
    assert len(out) == 1 and "n" in out[0]


def test_us10_int_is_not_bool():
    for v in (1, 0):
        out = errs(bool, v, "flag")
        assert len(out) == 1 and "flag" in out[0]


def test_us10_bool_inside_int_list_is_bad_element():
    out = errs({"n": [int]}, {"n": [1, True, 3]})
    assert len(out) == 1 and "n[1]" in out[0]


def test_us10_leaf_top_level_error_is_not_empty():
    out = errs(str, 5)
    assert len(out) == 1 and out[0].strip()


# lists
def test_us10_list_all_match():
    assert errs({"xs": [str]}, {"xs": ["a", "b"]}) == []
    assert errs({"xs": [str]}, {"xs": []}) == []


def test_us10_list_names_only_bad_elements_with_index():
    out = errs({"x": [str]}, {"x": ["a", 2, "c", None]})
    assert len(out) == 2
    assert "x[1]" in out[0] and "x[3]" in out[1]
    assert not any("x[0]" in e or "x[2]" in e for e in out)


def test_us10_list_expected_but_not_a_list_one_error():
    for bad in ("abc", 5, None, {"a": 1}):
        out = errs({"x": [str]}, {"x": bad})
        assert len(out) == 1 and "x" in out[0]


def test_us10_top_level_list_paths_have_no_prefix():
    out = errs([int], [1, "a"])
    assert len(out) == 1 and "[1]" in out[0]


def test_us10_nested_lists():
    out = errs({"m": [[int]]}, {"m": [[1, 2], [3, "x"], [4]]})
    assert len(out) == 1 and "m[1][1]" in out[0]


def test_us10_list_of_objects_paths():
    sch = {"items": [{"id": int, "name": str}]}
    out = errs(sch, {"items": [{"id": 1, "name": "a"}, {"id": "z", "name": "b"}, {"id": 3}]})
    assert len(out) == 2
    assert "items[1].id" in out[0]
    assert "items[2].name: missing" in out[1] or out[1].endswith("items[2].name: missing")


# maps
def test_us10_map_matching():
    assert errs({"files": {str: int}}, {"files": {"a.py": 1, "b.py": 2}}) == []
    assert errs({"files": {str: int}}, {"files": {}}) == []


def test_us10_map_bad_value_path_uses_key():
    out = errs({"files": {str: int}}, {"files": {"a.py": "x", "b.py": 2}})
    assert len(out) == 1 and "files.a.py" in out[0]


def test_us10_map_bad_key_type_names_map_path():
    out = errs({"files": {str: int}}, {"files": {1: 2, "ok": 3}})
    assert len(out) == 1 and "files" in out[0]


def test_us10_map_bad_key_and_bad_value_both_reported():
    out = errs({"files": {str: int}}, {"files": {5: 1, "a": "x"}})
    assert len(out) == 2
    assert any("files.a" in e for e in out)


def test_us10_map_with_list_values():
    out = errs({"m": {str: [int]}}, {"m": {"a": [1], "b": [2, "x"]}})
    assert len(out) == 1 and "m.b[1]" in out[0]


def test_us10_map_not_a_dict_one_error():
    out = errs({"files": {str: int}}, {"files": [1]})
    assert len(out) == 1 and "files" in out[0]


def test_us10_map_top_level_path():
    out = errs({str: int}, {"a": "x"})
    assert len(out) == 1 and "a" in out[0] and not out[0].startswith(".")


# fixed-key dicts
def test_us10_dict_missing_key_message():
    assert errs({"a": int, "b": str}, {"a": 1}) == ["b: missing"]


def test_us10_dict_missing_key_with_path_prefix():
    assert errs({"a": int}, {}, "p") == ["p.a: missing"]


def test_us10_dict_nested_dotted_path_no_leading_dot():
    sch = {"a": {"b": {"c": int}}}
    out = errs(sch, {"a": {"b": {"c": "x"}}})
    assert len(out) == 1 and "a.b.c" in out[0] and not out[0].startswith(".")
    assert errs(sch, {"a": {"b": {}}}) == ["a.b.c: missing"]
    assert errs(sch, {"a": {}}) == ["a.b: missing"]


def test_us10_dict_extra_keys_allowed():
    assert errs({"a": int}, {"a": 1, "zzz": object(), "q": None}) == []


def test_us10_dict_wrong_type_value():
    out = errs({"a": int, "b": str}, {"a": "no", "b": "ok"})
    assert len(out) == 1 and "a" in out[0] and not out[0].startswith(".")


def test_us10_each_bad_field_gives_exactly_one_error():
    sch = {"a": int, "b": str, "c": [int], "d": {"e": bool}}
    out = errs(sch, {"a": "x", "b": 1, "c": "no", "d": {"e": 1}})
    assert len(out) == 4
    for name in ("a", "b", "c", "d.e"):
        assert sum(name in e for e in out) >= 1
    assert sum("d.e" in e for e in out) == 1


def test_us10_mixed_missing_and_wrong():
    out = errs({"a": int, "b": str, "c": bool}, {"a": "x", "c": True})
    assert len(out) == 2
    assert "b: missing" in out


def test_us10_matching_nested_value_gives_empty_list():
    sch = {"ok": bool, "files": {str: int}, "tags": [str], "meta": {"n": int, "ids": [{"i": int}]}}
    val = {"ok": True, "files": {"a": 1}, "tags": ["x"], "meta": {"n": 2, "ids": [{"i": 1}, {"i": 2}]}, "extra": 1}
    assert errs(sch, val) == []


# non-dict where object expected
def test_us10_non_dict_for_object_names_path():
    for bad in (None, [], "s", 4, True):
        out = errs({"a": {"b": int}}, {"a": bad})
        assert len(out) == 1 and "a" in out[0]


def test_us10_non_dict_at_top_level_says_result():
    for bad in (None, [], "s", 4):
        out = errs({"a": int}, bad)
        assert len(out) == 1 and "result" in out[0]


def test_us10_non_dict_at_nonempty_path_names_that_path_not_result():
    out = errs({"a": int}, 5, "p.q")
    assert len(out) == 1 and "p.q" in out[0] and "result" not in out[0]


# path prefix
def test_us10_path_prefixes_every_error():
    sch = {"a": int, "b": [str], "c": {str: int}}
    out = errs(sch, {"a": "x", "b": [1], "c": {"k": "v"}}, "root")
    assert len(out) == 3
    assert all("root" in e for e in out)
    assert any("root.a" in e for e in out)
    assert any("root.b[0]" in e for e in out)
    assert any("root.c.k" in e for e in out)


def test_us10_path_prefixes_leaf_and_list_errors():
    assert "pre" in errs(int, "x", "pre")[0]
    assert "pre[0]" in errs([int], ["x"], "pre")[0]


# robustness
WEIRD = [None, [], [None], "str", 5, 1.5, True, {}, {"a": None}, {1: 2}, [[]], ([1],), object()]
SCHEMAS = [str, int, bool, [str], [[int]], {str: int}, {"a": int}, {"a": {"b": [str]}}, {"a": {str: [int]}},
           {"a": [{"b": int}]}]


@pytest.mark.parametrize("sch", SCHEMAS)
def test_us10_never_raises_on_odd_values(sch):
    for v in WEIRD:
        errs(sch, v)
        errs(sch, v, "p")
        errs(sch, {"a": v}, "")
        errs(sch, {"a": {"b": v}}, "")
        errs(sch, [v], "")


def test_us10_odd_values_in_nested_positions_report_errors():
    for v in WEIRD[:7]:
        assert errs({"a": {"b": [int]}}, {"a": {"b": v}}) != [] or v == []
        assert errs({"a": [{"b": int}]}, {"a": [v]}) != []


def test_us10_does_not_mutate_value():
    val = {"a": "x", "b": [1, "y", {"z": 1}], "c": {"k": "v"}}
    before = copy.deepcopy(val)
    errs({"a": int, "b": [int], "c": {str: int}, "d": str}, val, "p")
    assert val == before


def test_us10_does_not_mutate_schema():
    sch = {"a": [int], "b": {str: int}}
    before = copy.deepcopy(sch)
    errs(sch, {"a": ["x"], "b": {"k": "v"}})
    assert sch == before


def test_us10_empty_schema_matches_empty_dict():
    assert errs({}, {}) == []


def test_us10_empty_schema_allows_extra_keys():
    assert errs({}, {"x": 1}) == []


def test_us10_empty_schema_nested_matches():
    assert errs({"a": {}}, {"a": {}}) == []


def test_us10_empty_schema_non_dict_one_error_naming_result():
    out = errs({}, 5)
    assert len(out) == 1 and "result" in out[0]


def test_us10_empty_schema_nested_non_dict_one_error_naming_path():
    out = errs({"a": {}}, {"a": 5})
    assert len(out) == 1 and "a" in out[0]
