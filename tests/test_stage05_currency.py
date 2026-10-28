"""Bundle 23 Item S7: belief-currency QA type -- find_currency_seeds() narrows
CONFLICT's seed pairing to genuinely-differing pairs, and QAType.CURRENCY's
branch in generate_qa_pair() sets evidence=[later] with a stale_distractor
pointing at the earlier note (SINGLE_HOP's shape, not CONFLICT's
both-in-order shape)."""
import stage_05_qa_generation as s5
from stage_05_qa_generation import QAType, find_currency_seeds, generate_qa_pair

# find_conflict_seeds pairs on (entity, raw_fact_text[:40]) -- its own docstring calls
# this "fact-id prefix" matching. That only actually works when the shared subject
# clause (everything before the arrow) is long enough that differing resolutions still
# share their first 40 characters -- so fixtures below use a long, identical subject
# clause and only vary the text after "->".
_RENT_SUBJECT = "the ongoing situation about apartment rent payments with the landlord"
_GYM_SUBJECT = "the arrangement about the gym membership and its monthly billing cycle"


def _note(note_id, entities, facts, timestamp, text="some note text"):
    return {
        "note_id": note_id, "entities": entities, "latent_facts": facts,
        "timestamp": timestamp, "text": text,
    }


def test_find_currency_seeds_keeps_only_genuinely_differing_pairs():
    notes = [
        _note("n1", ["p_001"], [f"f_009: {_RENT_SUBJECT} -> confirmed still paused"], "2024-01-01T09:00:00"),
        _note("n2", ["p_001"], [f"f_009: {_RENT_SUBJECT} -> resumed active payments"], "2024-01-05T09:00:00"),
        # identical resolution both times -- not a real change, must be filtered out
        _note("n3", ["p_002"], [f"f_010: {_GYM_SUBJECT} -> confirmed active"], "2024-01-02T09:00:00"),
        _note("n4", ["p_002"], [f"f_010: {_GYM_SUBJECT} -> confirmed active"], "2024-01-06T09:00:00"),
    ]
    seeds = find_currency_seeds(notes)
    assert seeds == [["n1", "n2"]]


def test_find_currency_seeds_empty_when_no_conflict_seeds():
    notes = [_note("n1", ["p_001"], ["f_009: rent -> confirmed"], "2024-01-01T09:00:00")]
    assert find_currency_seeds(notes) == []


def test_currency_branch_sets_later_only_evidence_and_stale_distractor(monkeypatch):
    notes_by_id = {
        "n1": _note("n1", ["p_001"], ["f_009: rent -> confirmed paused"],
                    "2024-01-01T09:00:00", "rent is paused"),
        "n2": _note("n2", ["p_001"], ["f_009: rent -> resumed paying"],
                    "2024-01-05T09:00:00", "started paying rent again"),
    }
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (True, "ok"))
    monkeypatch.setattr(s5, "_ask_question", lambda qa_type, notes_text, facts: "What is the current rent status?")

    qa = generate_qa_pair(["n1", "n2"], notes_by_id, QAType.CURRENCY, 0)

    assert qa["reasoning_type"] == "belief_currency"
    assert qa["answer_key"]["evidence"] == ["n2"]
    assert qa["answer_key"]["ordered"] is False
    assert qa["answer_key"]["stale_distractor"] == ["n1"]


def test_currency_branch_discards_when_sides_dont_differ(monkeypatch):
    notes_by_id = {
        "n1": _note("n1", ["p_001"], ["f_009: rent -> confirmed active"], "2024-01-01T09:00:00"),
        "n2": _note("n2", ["p_001"], ["f_009: rent -> confirmed active"], "2024-01-05T09:00:00"),
    }
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (True, "ok"))
    try:
        generate_qa_pair(["n1", "n2"], notes_by_id, QAType.CURRENCY, 0)
        assert False, "expected Discarded"
    except s5.Discarded as exc:
        assert "don't actually differ" in exc.reason


def test_other_qa_types_answer_key_has_no_stale_distractor(monkeypatch):
    notes_by_id = {
        "n1": _note("n1", ["p_001"], ["f_009: rent -> confirmed paused"], "2024-01-01T09:00:00"),
    }
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (True, "ok"))
    monkeypatch.setattr(s5, "_ask_question", lambda qa_type, notes_text, facts: "What happened with rent?")
    qa = generate_qa_pair(["n1"], notes_by_id, QAType.SINGLE_HOP, 0)
    assert "stale_distractor" not in qa["answer_key"]


# ── Mutation-hardening (cosmic-ray-bundle23.toml, first run) ──────────────
# These three close real gaps the initial run's precise (line-range-filtered)
# survivors pointed at -- not cosmetic/equivalent mutants. See
# docs/bundles/BUNDLE_23.md § Mutation pass for the full triage.

def test_currency_branch_discards_when_only_one_side_lacks_facts(monkeypatch):
    """`if not early_facts or not later_facts` -- mutating `or` to `and` only
    discards when BOTH sides are empty, missing the one-sided-empty case
    (which would otherwise IndexError on `early_facts[0]`)."""
    notes_by_id = {
        "n1": _note("n1", ["p_001"], [], "2024-01-01T09:00:00"),  # no informative facts
        "n2": _note("n2", ["p_001"], ["f_009: rent -> resumed paying"], "2024-01-05T09:00:00"),
    }
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (True, "ok"))
    try:
        generate_qa_pair(["n1", "n2"], notes_by_id, QAType.CURRENCY, 0)
        assert False, "expected Discarded"
    except s5.Discarded as exc:
        assert "no informative fact" in exc.reason


def test_currency_branch_prefers_topic_matched_later_fact(monkeypatch):
    """When `later` carries multiple facts, the branch must pick the one whose
    topic matches `f_early` (via `_topic_key`), not just `later_facts[0]`."""
    shared_subject = "f_020: the ongoing car repair invoice review and approval process"
    notes_by_id = {
        "n1": _note("n1", ["p_001"], [f"{shared_subject} -> pending quote"], "2024-01-01T09:00:00"),
        "n2": _note("n2", ["p_001"], [
            "f_099: completely different vacation planning topic -> some unrelated update",
            f"{shared_subject} -> quote approved and repair started",
        ], "2024-01-05T09:00:00"),
    }
    seen_facts = []
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (seen_facts.append(fact) or (True, "ok")))
    monkeypatch.setattr(s5, "_ask_question", lambda qa_type, notes_text, facts: "What's the current repair status?")

    generate_qa_pair(["n1", "n2"], notes_by_id, QAType.CURRENCY, 0)

    # the topic-matched fact (car repair), not later_facts[0] (vacation planning), must
    # be the one checked against the note and phrased into the question.
    assert any("quote approved" in f for f in seen_facts)
    assert not any("vacation planning" in f for f in seen_facts)


def test_currency_branch_differing_check_is_equality_not_ordering(monkeypatch):
    """The genuinely-differing guard must use `==` (equal resolved statements
    -> discard), not an ordering comparison -- fixture chosen so the two
    resolved strings compare unequal but the EARLIER one sorts
    lexicographically >= the LATER one, which would make a `>=` mutant wrongly
    discard a pair that should be kept."""
    notes_by_id = {
        "n1": _note("n1", ["p_001"], ["f_030: loan application status -> still needs review"],
                    "2024-01-01T09:00:00"),
        "n2": _note("n2", ["p_001"], ["f_030: loan application status -> already approved"],
                    "2024-01-05T09:00:00"),
    }
    monkeypatch.setattr(s5, "_fact_supported", lambda note_text, fact: (True, "ok"))
    monkeypatch.setattr(s5, "_ask_question", lambda qa_type, notes_text, facts: "What's the loan status now?")

    qa = generate_qa_pair(["n1", "n2"], notes_by_id, QAType.CURRENCY, 0)
    assert qa["answer_key"]["evidence"] == ["n2"]
