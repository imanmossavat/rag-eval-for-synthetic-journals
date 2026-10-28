"""Rolling phase_state snapshot, arc-batched context window and mutation log: tested as pure functions, not full generate_note()
(which calls the LLM) -- same pattern as test_stage04_revision.py."""
import config
import stage_04_note_generation as s4


def _note(note_id, arc_id, text, latent_facts=None, timestamp="2024-01-01T09:00:00"):
    return {
        "note_id": note_id, "story_arc_id": arc_id, "text": text,
        "latent_facts": latent_facts or [], "timestamp": timestamp,
    }


# ── S3: recent-arc-notes window ──────────────────────────────────────────

def test_recent_arc_notes_filters_by_arc_and_windows_to_k():
    notes_by_event_id = {
        "E1": _note("n1", "a_001", "first"),
        "E2": _note("n2", "a_002", "other-arc"),
        "E3": _note("n3", "a_001", "second"),
        "E4": _note("n4", "a_001", "third"),
    }
    out = s4._recent_arc_notes("a_001", notes_by_event_id, k=2)
    assert [n["note_id"] for n in out] == ["n3", "n4"]


def test_recent_arc_notes_k_zero_is_empty():
    notes_by_event_id = {"E1": _note("n1", "a_001", "first")}
    assert s4._recent_arc_notes("a_001", notes_by_event_id, k=0) == []


def test_recent_arc_notes_no_arc_id_is_empty():
    notes_by_event_id = {"E1": _note("n1", "a_001", "first")}
    assert s4._recent_arc_notes(None, notes_by_event_id, k=3) == []


def test_k_zero_reproduces_blind_prompt_byte_identical():
    """Regression guard: with no arc context notes, build_note_prompt's output
    must be identical to the pre-S3 prompt (revision directive only, no arc
    context block) for the same event/world/prior_notes inputs."""
    world = {"entities": [], "story_arcs": []}
    event = {"event_id": "E2", "involved_entities": []}
    prior = {"E1": {"text": "old belief"}}

    baseline = s4.build_note_prompt(event, world, prior)
    with_empty_context = s4.build_note_prompt(event, world, prior, arc_context_notes=[], phase_state=None)
    with_k_zero_computed = s4.build_note_prompt(
        event, world, prior,
        arc_context_notes=s4._recent_arc_notes("a_001", {}, config.ARC_CONTEXT_NOTES),
        phase_state=None,
    )
    assert baseline == with_empty_context == with_k_zero_computed


def test_arc_context_directive_present_when_notes_given():
    recent = [_note("n1", "a_001", "went to the gym again")]
    directive = s4._arc_context_directive(
        recent, {"stress": 1, "focus": "gym", "dominant_emotion": "tired"}
    )
    assert "ARC CONTEXT" in directive
    assert "went to the gym again" in directive
    assert "stress=1" in directive


def test_arc_context_directive_empty_when_no_notes():
    assert s4._arc_context_directive(
        [], {"stress": 1, "focus": "gym", "dominant_emotion": "tired"}
    ) == ""


def test_arc_context_directive_with_notes_but_no_phase_state():
    """Mutation-hardening: `if phase_state and
    any(...)` must short-circuit on a falsy phase_state -- a mutant flipping
    `and` to `or` would evaluate `any(None.values())` and crash instead. The
    signature allows `phase_state: dict | None = None`, so this is a real
    reachable call shape, not just a defensive corner."""
    recent = [_note("n1", "a_001", "went to the gym again")]
    directive = s4._arc_context_directive(recent, None)
    assert "ARC CONTEXT" in directive
    assert "went to the gym again" in directive
    assert "Current rolling state" not in directive


# ── S2: rolling phase_state snapshot ─────────────────────────────────────

def test_compute_phase_state_aggregates_affect_and_facts():
    affects = [
        {"emotion": "anxious", "valence": -1, "intensity": 2},
        {"emotion": "anxious", "valence": -1, "intensity": 4},
        {"emotion": "relieved", "valence": 1, "intensity": 1},
    ]
    facts = ["f_001: rent due -> confirmed", "f_002: gym_membership -> cancelled"]
    out = s4.compute_phase_state(affects, facts)
    assert out == {"stress": 3, "focus": "gym membership", "dominant_emotion": "anxious"}


def test_compute_phase_state_empty_inputs_are_zeroed():
    assert s4.compute_phase_state([], []) == {"stress": 0, "focus": "", "dominant_emotion": ""}


def test_compute_phase_state_no_negative_affect_zero_stress():
    affects = [{"emotion": "content", "valence": 1, "intensity": 2}]
    out = s4.compute_phase_state(affects, [])
    assert out["stress"] == 0
    assert out["dominant_emotion"] == "content"


# ── S6: mutation log ──────────────────────────────────────────────────────

def test_mutation_log_add_for_new_fact_id():
    note = {"note_id": "n2", "story_arc_id": "a_001", "timestamp": "t2",
            "latent_facts": ["f_009: rent -> confirmed"]}
    entries = s4.mutation_log_entries(note, {}, {})
    assert entries == [{
        "op": "ADD", "fact_id": "f_009", "arc_id": "a_001",
        "from_note_id": None, "to_note_id": "n2", "timestamp": "t2",
    }]


def test_mutation_log_update_for_seen_fact_id_no_contradiction_event():
    prior_note = {"note_id": "n1"}
    note = {"note_id": "n2", "story_arc_id": "a_001", "timestamp": "t2",
            "latent_facts": ["f_009: rent -> paid"]}
    entries = s4.mutation_log_entries(note, {}, {"f_009": prior_note})
    assert entries[0]["op"] == "UPDATE"
    assert entries[0]["from_note_id"] == "n1"


def test_mutation_log_invalidate_for_contradiction_event():
    prior_note = {"note_id": "n1"}
    note = {"note_id": "n2", "story_arc_id": "a_001", "timestamp": "t2",
            "latent_facts": ["f_009: rent -> actually still unpaid"]}
    event = {"_contradiction_of": "E1"}
    entries = s4.mutation_log_entries(note, event, {"f_009": prior_note})
    assert entries[0]["op"] == "INVALIDATE"
    assert entries[0]["from_note_id"] == "n1"


def test_mutation_log_skips_facts_with_no_id():
    note = {"note_id": "n2", "story_arc_id": "a_001", "timestamp": "t2",
            "latent_facts": ["no id here, just prose"]}
    assert s4.mutation_log_entries(note, {}, {}) == []


def test_mutation_log_continues_past_a_no_id_fact_to_later_facts():
    """Mutation-hardening: the no-id-fact skip must
    be `continue`, not `break` -- the prior test only had one fact in the
    list, so it couldn't distinguish "skip this one" from "stop the loop"."""
    note = {"note_id": "n2", "story_arc_id": "a_001", "timestamp": "t2",
            "latent_facts": ["no id here, just prose", "f_009: rent -> confirmed"]}
    entries = s4.mutation_log_entries(note, {}, {})
    assert [e["fact_id"] for e in entries] == ["f_009"]
