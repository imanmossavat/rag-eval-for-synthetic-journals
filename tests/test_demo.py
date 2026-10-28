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


def test_rag_in_memory_needs_every_gold_note():
    # "my roommate's car": the Volvo note alone has the answer string but not the link
    q = {"type": "two_hop", "answerable": True, "answer": ["Volvo Amazon"], "gold_notes": ["N022", "N038"]}
    ctx = "Kofi drove his Volvo Amazon."
    assert evaluate.memory_has_answer(q, ctx) is True
    assert evaluate.memory_has_answer(q, ctx, ["N038", "N001"]) is False
    assert evaluate.memory_has_answer(q, ctx, ["N038", "N022"]) is True


def test_retrieval_metrics():
    m = evaluate.retrieval_metrics(["N1", "N2"], ["N9", "N1", "N3", "N4", "N5"])
    assert m == {"precision": 0.2, "recall": 0.5, "hit": 1.0, "all": 0.0, "mrr": 0.5}


# ── The explainer's claims, pinned to the recorded run ──────────────────────
# demo/explainer.html quotes numbers from demo/runs/20261025_171940. These tests
# re-derive them from the raw replies, so the page can't drift from its data.

RUN = DEMO / "runs" / "20261025_171940"
EXPLAINER = (DEMO / "explainer.html").read_text()


@pytest.fixture(scope="module")
def rescored():
    questions = {q["id"]: q for q in json.loads((DEMO / "data" / "questions.json").read_text())}
    rows = [json.loads(line) for line in (RUN / "raw.jsonl").open()]
    for r in rows:
        q = questions[r["qid"]]
        r["label"] = evaluate.label(q, r["reply"], evaluate.memory_has_answer(q, r["context"], r["retrieved"]))
    return rows


def test_recorded_run_rescores_to_its_saved_labels(rescored):
    saved = {(r["model"], r["bot"], r["qid"]): r["label"] for r in map(json.loads, (RUN / "scored.jsonl").open())}
    assert {(r["model"], r["bot"], r["qid"]): r["label"] for r in rescored} == saved


def test_explainer_headline_scores(rescored):
    right = {}
    for r in rescored:
        right[(r["model"], r["bot"])] = right.get((r["model"], r["bot"]), 0) + (r["label"] in evaluate.RIGHT)
    assert right == {("qwen3:4b", "full_context"): 24, ("qwen3:4b", "vector_rag"): 22,
                     ("qwen3:4b", "summary"): 11, ("qwen3:4b", "facts"): 18,
                     ("qwen3:30b", "full_context"): 26, ("qwen3:30b", "vector_rag"): 23}
    refusals = sum(r["label"] in ("IDK_BUT_IN_MEMORY", "IDK_NOT_IN_MEMORY") for r in rescored)
    assert refusals == 20  # "20 of the wrong answers on this page were refusals"


def test_explainer_embedded_answers_match_the_run(rescored):
    import re
    embedded = json.loads(re.search(r"const D = (\{.*?\});\n", EXPLAINER).group(1))["r"]
    for r in rescored:
        assert embedded[f"{r['model']}|{r['bot']}"][r["qid"]][0] == r["label"]


def test_explainer_multi_note_claim(rescored):
    # Lesson 3: "5 of the 12 multi-note questions were missing at least one proof note"
    questions = {q["id"]: q for q in json.loads((DEMO / "data" / "questions.json").read_text())}
    rag = [r for r in rescored if r["bot"] == "vector_rag" and r["model"] == "qwen3:4b"]
    multi = [r for r in rag if len(questions[r["qid"]]["gold_notes"]) > 1]
    missing = [r for r in multi if not set(questions[r["qid"]]["gold_notes"]) <= set(r["retrieved"])]
    assert (len(missing), len(multi)) == (5, 12)
    assert "5 of the 12 multi-note questions" in EXPLAINER


def test_explainer_n027_plan_card():
    plan = next(p for p in json.loads((DEMO / "data" / "notes_plan.json").read_text()) if p["id"] == "N027")
    shown = ["sister", "Pickle", "Kofi", "bouldering"]
    assert set(shown) <= set(plan["must_exclude"])
    assert f"… {len(plan['must_exclude']) - len(shown)} more" in EXPLAINER
    assert "world.json · 43 lines" in EXPLAINER
    assert len((DEMO / "data" / "world.json").read_text().splitlines()) == 43


def test_explainer_rejected_draft_is_rejected():
    plan = next(p for p in json.loads((DEMO / "data" / "notes_plan.json").read_text()) if p["id"] == "N027")
    draft = ("Femke brought Biscotti along to the market this morning. Her dog's name suits him. "
             "He tried to eat a whole herring from the fish stall and got very offended when he wasn't "
             "allowed. Biscotti and Pickle sniffed each other for ages and then decided they were best friends.")
    assert generate.check_note(draft, plan) == ["contains forbidden 'Pickle'"]
    assert generate.check_note(draft.replace("Biscotti and Pickle", "Biscotti and my dog"), plan) == []


def test_explainer_rag_refusals_are_memory_failures(rescored):
    # Chapters 10 and 12: with the all-gold-notes rule, vector search has no reading failures
    rag = [(r["model"], r["qid"]) for r in rescored if r["bot"] == "vector_rag"
           and r["label"] in ("IDK_BUT_IN_MEMORY", "IDK_NOT_IN_MEMORY")]
    labels = {r["label"] for r in rescored if r["bot"] == "vector_rag"}
    assert "IDK_BUT_IN_MEMORY" not in labels
    assert sorted(rag) == [("qwen3:30b", "Q18"), ("qwen3:4b", "Q18"), ("qwen3:4b", "Q20"), ("qwen3:4b", "Q23")]


def test_explainer_full_context_word_count():
    # Counted as the model sees it, with the date prefix on every note (as the ~270 for vector search is)
    import chatbots
    notes = json.loads((DEMO / "data" / "notes.json").read_text())
    context, _ = chatbots.FullContext(notes, None).memory_for("")
    assert len(context.split()) == 2863
    assert "shows 2,863 words" in EXPLAINER


def test_explainer_ramble_counts():
    # Chapter 7: the 13,000-word reply would pass a plain text match
    raw = [json.loads(line) for line in (RUN / "raw.jsonl").open()]
    reply = next(r["reply"] for r in raw if (r["bot"], r["qid"], r["model"]) == ("facts", "Q15", "qwen3:4b"))
    assert 12_500 < len(reply.split()) < 13_500
    assert reply.count("Biscotti") > 1000 and reply.count("Pickle") == 22
    assert "Biscotti, over a thousand times, and named the look-alike Pickle 22 times" in EXPLAINER


def test_explainer_compressed_memories():
    # Chapters 6 and 11, from the memory text saved with every answer in raw.jsonl
    raw = [json.loads(line) for line in (RUN / "raw.jsonl").open()]
    summary = next(r["context"] for r in raw if r["bot"] == "summary")
    facts = next(r["context"] for r in raw if r["bot"] == "facts")
    assert len(summary.split()) == 395 and "shows 395 words" in EXPLAINER
    assert not any(w in summary.lower() for w in ("sister", "colleague", "neighbour", "roommate"))
    assert "Femke brought stroopwafels and Biscotti." in summary
    assert len(facts.split()) == 2748 and len(facts.splitlines()) == 349
    assert "2026-03-15 | First day at the Openbare Bibliotheek" in facts.splitlines()
    assert "2026-03-26 | Started at Museum Speelklok" in facts.splitlines()


def test_explainer_cites_only_tracked_files():
    # A fresh clone has no gitignored files, so the page must not lean on them
    for gone in ("REFLECT", "internal report", "ISSUES", "REPORT_", "TALK_NOTES", "runs/cache", "17–20", "17 to 20", "4 times out of 6"):
        assert gone not in EXPLAINER, gone
    assert (DEMO.parent / "data" / "qa_pairs_v1_snapshot.json").exists()
