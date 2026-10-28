"""Story arcs declare an ordered `phases` list instead of a
flat `status` string. `unresolved_arcs()` becomes "has more than one phase";
`assign_event_phase()` is the pure position-in-list function that later maps
an arc's realized events onto its declared phases."""
from knowledge_graph import GraphValidator, assign_event_phase, load_graph


def _world(phases_by_arc):
    return {
        "entities": [],
        "story_arcs": [
            {"arc_id": arc_id, "title": arc_id, "phases": phases, "involved_entities": []}
            for arc_id, phases in phases_by_arc.items()
        ],
    }


def test_multi_phase_arc_is_unresolved():
    G = load_graph(_world({"a_001": ["setup", "escalation", "fallout"]}))
    validator = GraphValidator(G)
    assert validator.unresolved_arcs() == ["a_001"]


def test_single_phase_arc_behaves_like_old_resolved_status():
    """Regression guard: a single-phase arc is the phases-list analog of the
    old resolved/abandoned status — it must NOT show up as unresolved."""
    G = load_graph(_world({"a_001": ["settled"]}))
    validator = GraphValidator(G)
    assert validator.unresolved_arcs() == []


def test_no_phases_declared_is_not_unresolved():
    G = load_graph(_world({"a_001": []}))
    validator = GraphValidator(G)
    assert validator.unresolved_arcs() == []


def test_mixed_arcs_filters_correctly():
    G = load_graph(_world({
        "a_multi": ["setup", "escalation"],
        "a_single": ["settled"],
    }))
    validator = GraphValidator(G)
    assert validator.unresolved_arcs() == ["a_multi"]


def test_assign_event_phase_boundaries():
    phases = ["setup", "escalation", "fallout"]
    # First event of a 6-event arc -> first phase; last event -> last phase.
    assert assign_event_phase(0, 6, phases) == "setup"
    assert assign_event_phase(5, 6, phases) == "fallout"
    # Middle event lands in the middle phase.
    assert assign_event_phase(3, 6, phases) == "escalation"


def test_assign_event_phase_single_event_arc_gets_first_phase():
    assert assign_event_phase(0, 1, ["only"]) == "only"


def test_assign_event_phase_empty_phases_returns_empty_string():
    assert assign_event_phase(0, 5, []) == ""


def test_assign_event_phase_is_deterministic():
    phases = ["a", "b", "c", "d"]
    first = [assign_event_phase(i, 10, phases) for i in range(10)]
    second = [assign_event_phase(i, 10, phases) for i in range(10)]
    assert first == second


def test_assign_event_phase_clamps_when_idx_reaches_n_in_arc():
    """Mutation-hardening: idx_in_arc == n_in_arc
    makes the raw position == len(phases), which the `min(position,
    len(phases) - 1)` clamp must pull back to the last phase. The boundary
    tests above never hit this because idx was always < n_in_arc."""
    phases = ["setup", "escalation", "fallout"]
    assert assign_event_phase(6, 6, phases) == "fallout"
