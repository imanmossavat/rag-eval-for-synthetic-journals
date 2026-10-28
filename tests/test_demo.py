"""Tests for the deterministic parts of demo/ — no LLM needed.

The demo's claim is "the answer key is exact by construction". These tests pin the
pieces that claim rests on: world validation, the note checker, question building
from the checked-in data, and the answer scorer."""

import copy
import json
import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parent.parent / "demo"
sys.path.insert(0, str(DEMO))

import evaluate  # noqa: E402
import generate  # noqa: E402


@pytest.fixture
def world():
    return json.loads((DEMO / "data" / "world.json").read_text())


@pytest.fixture
def notes():
    return json.loads((DEMO / "data" / "notes.json").read_text())


def test_checked_in_world_is_valid(world):
    assert generate.validate_world(world) == []


def test_world_rejects_fact_before_intro(world):
    w = copy.deepcopy(world)
    w["facts"][1]["day"] = 1  # F2 is about P1, introduced on day 2
    assert any("intro_day" in e for e in generate.validate_world(w))


def test_world_rejects_duplicate_values(world):
    w = copy.deepcopy(world)
    w["facts"][1]["value"] = w["facts"][0]["value"]
    assert "values must all be different" in generate.validate_world(w)


def test_checked_in_notes_pass_their_plan(notes):
    plan = {p["id"]: p for p in json.loads((DEMO / "data" / "notes_plan.json").read_text())}
    for n in notes:
        assert generate.check_note(n["text"], plan[n["id"]]) == [], n["id"]


def test_two_hop_fact_note_hides_the_relation(world, notes):
    # The whole point of a two-hop question: the fact note names the person but not
    # the relation, so "my sister's X" needs the intro note too.
    people = {p["id"]: p for p in world["people"]}
    for n in notes:
        if n["kind"] == "fact":
            fact = next(f for f in world["facts"] if f["id"] == n["ref"])
            if fact["subject"] != "ME":
                assert not generate._has_word(n["text"], people[fact["subject"]]["relation"])


def test_count_answer_matches_keyword_notes(world, notes):
    for h in world["habits"]:
        mentioning = [n for n in notes if generate._has_word(n["text"], h["keyword"])]
        assert len(mentioning) == len(h["days"])


def test_unanswerable_attributes_never_stated(world, notes):
    people = {p["id"]: p for p in world["people"]}
    for nm in world["never_mentioned"]:
        name = people[nm["subject"]]["name"]
        for n in notes:
            if generate._has_word(n["text"], name):
                assert nm["attribute"] not in n["text"].lower(), (n["id"], nm)


def test_questions_cover_every_level(world, notes):
    qs = generate.make_questions(world, notes)
    assert {q["level"] for q in qs} == {1, 2, 3, 4, 5}
    note_ids = {n["id"] for n in notes}
    for q in qs:
        assert set(q["gold_notes"]) <= note_ids
        assert q["answerable"] == bool(q["gold_notes"])


def test_note_checker_is_word_boundary_aware():
    plan = {"must_include": [], "must_exclude": ["Ines"]}
    assert generate.check_note("A few lines about nothing.", plan) == []
    assert generate.check_note("Ines came by.", plan) != []


Q_SINGLE = {"type": "single_fact", "answerable": True, "answer": ["Biscotti"],
            "conjunct": False, "distractor_values": ["Pickle"]}
Q_LIST = {"type": "history", "answerable": True, "answer": ["A One", "B Two"],
          "conjunct": True, "distractor_values": []}
Q_COUNT = {"type": "count", "answerable": True, "answer": ["7"], "conjunct": False, "distractor_values": []}
Q_NONE = {"type": "unanswerable", "answerable": False, "answer": [], "conjunct": False,
          "distractor_values": ["Pickle"]}


@pytest.mark.parametrize("q,reply,in_mem,expected", [
    (Q_SINGLE, "Biscotti.", True, "CORRECT"),
    (Q_SINGLE, "Pickle", True, "WRONG_DISTRACTOR"),
    (Q_SINGLE, "Rex", True, "WRONG_OTHER"),
    (Q_SINGLE, "I don't know", True, "IDK_BUT_IN_MEMORY"),
    (Q_SINGLE, "I don't know", False, "IDK_NOT_IN_MEMORY"),
    (Q_LIST, "A One, then B Two", True, "CORRECT"),
    (Q_LIST, "A One", True, "PARTIAL"),
    (Q_COUNT, "Seven times", None, "CORRECT"),
    (Q_COUNT, "5", None, "WRONG_OTHER"),
    (Q_NONE, "I don't know", None, "CORRECT_IDK"),
    (Q_NONE, "Pickle", None, "HALLUCINATED"),
    (Q_SINGLE, "Let me look. " + "Biscotti and Pickle are dogs. " * 10, True, "RAMBLED"),
])
def test_label(q, reply, in_mem, expected):
    assert evaluate.label(q, reply, in_mem) == expected


def test_value_match_needs_whole_words():
    # "Pixel 8" must not match "Pixel 80"
    assert not evaluate.contains(evaluate.norm("I have a Pixel 80"), "Pixel 8")
    assert evaluate.contains(evaluate.norm("A Pixel 8, I think."), "Pixel 8")


def test_retrieval_metrics():
    m = evaluate.retrieval_metrics(["N1", "N2"], ["N9", "N1", "N3", "N4", "N5"])
    assert m == {"precision": 0.2, "recall": 0.5, "hit": 1.0, "all": 0.0, "mrr": 0.5}
