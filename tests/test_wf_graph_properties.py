"""Property tests of the unit-loop graph (X3): invariants of EDGES and legal_options."""

import copy

from graph import BACK_EDGES, EDGES, REVIEW_PASSES, ROUND_CAP, STOPS, back_rounds, cap_reached, kind, legal_options
from hypothesis import assume, given, settings
from hypothesis import strategies as st

SETTINGS = settings(max_examples=200, deadline=None)
DECIDE_NODES = sorted(n for n in EDGES if kind(n) == "decide")
ALL_PASSES = sorted({p for ps in REVIEW_PASSES.values() for p in ps})
TARGETS = sorted(set(EDGES) | set(BACK_EDGES.values()))


@st.composite
def back_entry(draw):
    (node, option), to = draw(st.sampled_from(sorted(BACK_EDGES.items())))
    return {"node": node, draw(st.sampled_from(["decision", "outcome"])): option, "to": to}


@st.composite
def wrong_entry(draw):
    ids = draw(st.lists(st.sampled_from(["f1", "f2", "f3", "f4"]), max_size=4, unique=True))
    passes = {i: draw(st.sampled_from(ALL_PASSES)) for i in ids}
    node = draw(st.sampled_from(DECIDE_NODES))
    return {"node": node, "decision": "wrong", "evidence": {"findings": ids}, "passes": passes}


continue_entry = st.builds(lambda key: {"node": "user", key: "user_continue"}, st.sampled_from(["decision", "outcome"]))
histories = st.lists(st.one_of(back_entry(), back_entry(), wrong_entry(), continue_entry), max_size=14)
uncovered_sets = st.sets(st.sampled_from(["c1", "c2", "c3"]), min_size=1)


def test_us_x3_every_edge_target_is_a_node():
    for node, edges in EDGES.items():
        for option, target in edges.items():
            assert target in EDGES, (node, option, target)


def test_us_x3_terminals_have_no_edges_and_others_have_some():
    for node, edges in EDGES.items():
        assert (not edges) == (node in ("user", "done")), node


def _reach(start):
    seen, todo = {start}, [start]
    while todo:
        for t in EDGES[todo.pop()].values():
            if t not in seen:
                seen.add(t)
                todo.append(t)
    return seen


def test_us_x3_done_reachable_and_every_node_reaches_an_end():
    assert "done" in _reach("write_unit")
    for node in EDGES:
        assert _reach(node) & {"user", "done"}, node


@SETTINGS
@given(node=st.sampled_from(DECIDE_NODES), entries=histories, uncovered=st.sets(st.sampled_from(["c1", "c2"])))
def test_us_x3_legal_options_nonempty_unique_subset_of_edges(node, entries, uncovered):
    opts = legal_options(node, entries, uncovered)
    assert opts
    assert len(opts) == len(set(opts))
    assert set(opts) <= set(EDGES[node])


CAPPED_NODES = sorted({n for n, _ in BACK_EDGES} & set(DECIDE_NODES))


@st.composite
def capped(draw):
    node = draw(st.sampled_from(CAPPED_NODES))
    (n, option), to = draw(st.sampled_from(sorted((k, t) for k, t in BACK_EDGES.items() if k[0] == node)))
    extra = [{"node": n, "decision": option, "to": to}] * ROUND_CAP
    return node, draw(histories) + extra


@SETTINGS
@given(case=capped())
def test_us_x3_cap_reached_without_uncovered_offers_only_stops(case):
    node, entries = case
    assume(cap_reached(entries, node))
    assert legal_options(node, entries, set()) == list(STOPS)


@SETTINGS
@given(node=st.sampled_from(DECIDE_NODES), entries=histories, uncovered=uncovered_sets)
def test_us_x3_uncovered_gives_only_architecture_stop(node, entries, uncovered):
    assert legal_options(node, entries, uncovered) == ["architecture_stop"]


@SETTINGS
@given(entries=histories, key=st.sampled_from(["decision", "outcome"]))
def test_us_x3_user_continue_resets_back_rounds(entries, key):
    history = entries + [{"node": "user", key: "user_continue"}]
    assert all(back_rounds(history, t) == 0 for t in TARGETS)


@SETTINGS
@given(node=st.sampled_from(DECIDE_NODES), entries=histories, uncovered=st.sets(st.sampled_from(["c1", "c2"])))
def test_us_x3_legal_options_does_not_mutate_history(node, entries, uncovered):
    before = copy.deepcopy(entries)
    legal_options(node, entries, uncovered)
    assert entries == before
