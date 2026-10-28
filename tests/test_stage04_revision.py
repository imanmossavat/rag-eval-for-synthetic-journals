"""Piece 1 (Bundle 21, item A1): stage_04 threads the contradicted note's text +
a revise instruction into the prompt when an event carries _contradiction_of."""
import stage_04_note_generation as s4


def test_no_directive_without_contradiction_link():
    event = {"event_id": "E2", "involved_entities": []}
    assert s4._revision_directive(event, {"E1": {"text": "old belief"}}) == ""


def test_no_directive_when_referenced_note_missing_or_empty():
    event = {"event_id": "E2", "_contradiction_of": "E1", "involved_entities": []}
    assert s4._revision_directive(event, {}) == ""
    assert s4._revision_directive(event, {"E1": {"text": "   "}}) == ""
    assert s4._revision_directive(event, None) == ""


def test_directive_carries_prior_note_text():
    event = {"event_id": "E2", "_contradiction_of": "E1", "involved_entities": []}
    prior = {"E1": {"text": "The gym was clearly worth every penny."}}
    directive = s4._revision_directive(event, prior)
    assert "REVISION DIRECTIVE" in directive
    assert "The gym was clearly worth every penny." in directive


def test_build_note_prompt_includes_directive_only_when_applicable():
    world = {"entities": [], "story_arcs": []}
    prior = {"E1": {"text": "I was sure about the move."}}

    contra_event = {"event_id": "E2", "_contradiction_of": "E1", "involved_entities": []}
    with_directive = s4.build_note_prompt(contra_event, world, prior)
    assert "REVISION DIRECTIVE" in with_directive
    assert "I was sure about the move." in with_directive

    # Guard: same event with no prior-note lookup, or a plain event, must not
    # inject the directive — if this assertion held regardless, the feature is a no-op.
    plain_event = {"event_id": "E2", "involved_entities": []}
    without_directive = s4.build_note_prompt(plain_event, world, prior)
    assert "REVISION DIRECTIVE" not in without_directive
    assert s4.build_note_prompt(contra_event, world, None).count("REVISION DIRECTIVE") == 0
