"""Tests of scripts/workflow/units.py: unit text from the plan, and fix units."""

import units

PLAN = """# Plan

Intro text.

## User stories
- US-1: something

## Subtasks
Each `### N.` heading is one unit.

### 1. state.py: create the state (US-6)
Estimate: ~24 lines.

Contracts:
- `new_state()` gives the shape.

### 2. graph.py: nodes (US-1, US-2)
Estimate: ~10 lines.

#### Details
| col | val |
|-----|-----|
| a   | 1   |

More text.

### 6b. review.py: extra (US-3)
Body of 6b.

### Notes
This is not a unit.

### 3. last.py: final (US-4)
Final body line one.
Final body line two.

## Files and functions
- state.py: new_state

## Decisions
- D1: something
"""


def _by_prefix(result, prefix):
    return [u for u in result if u.startswith(prefix)]


def test_us6_plan_units_count_and_order():
    got = units.plan_units(PLAN)
    heads = [u.splitlines()[0] for u in got]
    assert heads == [
        "### 1. state.py: create the state (US-6)",
        "### 2. graph.py: nodes (US-1, US-2)",
        "### 6b. review.py: extra (US-3)",
        "### 3. last.py: final (US-4)",
    ]


def test_us6_plan_units_exact_text_of_each_unit():
    got = [u.rstrip("\n") for u in units.plan_units(PLAN)]
    assert got[0] == (
        "### 1. state.py: create the state (US-6)\nEstimate: ~24 lines.\n\nContracts:\n- `new_state()` gives the shape."
    ).rstrip("\n")
    assert got[2] == "### 6b. review.py: extra (US-3)\nBody of 6b."
    assert got[3] == ("### 3. last.py: final (US-4)\nFinal body line one.\nFinal body line two.")


def test_us6_plan_units_keep_subheading_and_table_inside_unit():
    unit2 = units.plan_units(PLAN)[1].rstrip("\n")
    assert unit2 == (
        "### 2. graph.py: nodes (US-1, US-2)\n"
        "Estimate: ~10 lines.\n"
        "\n"
        "#### Details\n"
        "| col | val |\n"
        "|-----|-----|\n"
        "| a   | 1   |\n"
        "\n"
        "More text."
    )


def test_us6_plan_units_last_unit_stops_at_next_section():
    last = units.plan_units(PLAN)[-1]
    assert "## Files and functions" not in last
    assert "## Decisions" not in last
    assert "new_state" not in last
    assert "D1" not in last


def test_us6_plan_units_unit_n_is_item_n_minus_1():
    got = units.plan_units(PLAN)
    assert got[0].startswith("### 1. ")
    assert got[1].startswith("### 2. ")


def test_us6_plan_units_6b_heading_counts_as_unit():
    got = units.plan_units(PLAN)
    assert len(_by_prefix(got, "### 6b. ")) == 1
    assert "Body of 6b." in got[2]


def test_us6_plan_units_unnumbered_heading_is_not_unit_and_ends_previous():
    got = units.plan_units(PLAN)
    assert not _by_prefix(got, "### Notes")
    assert all("This is not a unit." not in u for u in got)
    assert all("### Notes" not in u for u in got)
    assert "Body of 6b." in got[2]


def test_us6_plan_units_no_headings_gives_empty_list():
    assert units.plan_units("# Plan\n\n## Subtasks\nNothing here.\n### Notes\nx\n") == []
    assert units.plan_units("") == []


def test_us6_plan_units_requires_dot_and_space_after_number():
    assert units.plan_units("### 1 no dot\nbody\n### 2.nospace\nbody\n") == []


def test_us6_fix_text_exact_output():
    unit = "### 7. thing (US-7)\nEstimate: ~5 lines.\nBody."
    out = units.fix_text(unit, "principles P2 on abc1234", ["FAIL a", "FAIL b"])
    # no trailing newline
    assert out == ("### 7. thing (US-7)\nFix: principles P2 on abc1234\nFAIL a\nFAIL b")


def test_us6_fix_text_excludes_rest_of_plan_unit_body():
    unit = "### 7. thing (US-7)\nEstimate: ~5 lines.\nBody."
    out = units.fix_text(unit, "tests T1,T2 on deadbee", ["tests/x.py::t1"])
    assert "Estimate" not in out and "Body." not in out
    assert out.splitlines()[:2] == ["### 7. thing (US-7)", "Fix: tests T1,T2 on deadbee"]


def test_us6_fix_text_keeps_every_line_in_order():
    lines = [f"line {i}" for i in range(5)]
    out = units.fix_text("### 1. x (US-1)\nbody", "p 1 on s", lines)
    assert out.splitlines()[2:] == lines


def test_us6_fix_text_no_lines_is_heading_and_fix_line():
    assert units.fix_text("### 1. x (US-1)\nbody", "p 1 on s", []) == "### 1. x (US-1)\nFix: p 1 on s"


UNIT3 = """### 3. graph.py: edges of the unit loop (US-7)
Estimate: ~10 lines.

Contracts:
- something (not a story)
"""


def test_us10_commit_message_plan_unit():
    assert units.commit_message(UNIT3) == "US-7: graph.py: edges of the unit loop"


def test_us10_commit_message_keeps_multiple_stories_whole():
    md = "### 5. a.py: two things (US-9, US-10)\nBody."
    assert units.commit_message(md) == "US-9, US-10: a.py: two things"


def test_us10_commit_message_fix_unit():
    md = units.fix_text(UNIT3, "principles P4 on abc1234", ["detail line"])
    assert units.commit_message(md) == ("US-7: Fix principles P4 on abc1234: graph.py: edges of the unit loop")


def test_us10_commit_message_last_parentheses_are_the_stories():
    md = "### 4. graph.py: kinds (and tables) (US-7)\nBody."
    assert units.commit_message(md) == "US-7: graph.py: kinds (and tables)"


def test_us10_commit_message_6b_heading():
    md = "### 6b. review.py: extra (US-3)\nBody of 6b."
    assert units.commit_message(md) == "US-3: review.py: extra"


def test_us10_commit_message_no_parentheses_gives_title_alone():
    md = "### 7. misc.py: no stories\nBody."
    assert units.commit_message(md) == "misc.py: no stories"


def test_us10_commit_message_ignores_body_lines():
    md = "### 3. graph.py: edges (US-7)\nNote (US-99) here\nFix: not directly after\nmore"
    assert units.commit_message(md) == "US-7: graph.py: edges"
