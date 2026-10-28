"""Tests for eval/ (the pipeline-corpus eval) — no LLM needed.

The first group pins the checked-in corpus itself: every number an eval report quotes
rests on the evidence IDs resolving to real notes, and on the files coming from one
generation run. Until 2026-10-28 neither held (notes.json was from a later run than
qa_pairs.json, so no answerable question's evidence existed), and nothing noticed."""

import json
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent.parent / "eval"
sys.path.insert(0, str(EVAL))

import judge  # noqa: E402
import run_eval  # noqa: E402


@pytest.fixture(scope="module")
def dataset():
    return run_eval.load_dataset()


def test_checked_in_corpus_joins_cleanly(dataset):
    notes, questions = dataset
    assert run_eval.check_dataset(notes, questions) == []


def test_checked_in_files_are_from_one_run():
    m = run_eval.manifest_check()
    assert all(m["files_match_manifest"].values()), m


def test_supporting_notes_resolve_too():
    notes = {n["note_id"] for n in json.loads((run_eval.DATA / "notes.json").read_text())["notes"]}
    qa = json.loads((run_eval.DATA / "qa_pairs.json").read_text())["qa_pairs"]
    assert [(q["question_id"], s) for q in qa for s in q["supporting_notes"] if s not in notes] == []


def test_check_dataset_catches_a_dangling_evidence_id(dataset):
    notes, questions = dataset
    broken = [dict(questions[0], gold_notes=["N_does_not_exist"])] + questions[1:]
    assert any("N_does_not_exist" in e for e in run_eval.check_dataset(notes, broken))


def test_check_dataset_catches_answerability_mismatch():
    notes = [{"id": "N1", "date": "2024-01-01", "text": "x"}]
    qs = [{"id": "q1", "gold_notes": [], "answerable": True},
          {"id": "q2", "gold_notes": ["N1"], "answerable": False}]
    errs = run_eval.check_dataset(notes, qs)
    assert len(errs) == 2


def test_retrieval_metrics():
    m = run_eval.retrieval_metrics(["N1", "N2"], ["N9", "N1", "N3", "N4", "N5"])
    assert m == {"precision": 0.2, "recall": 0.5, "hit": 1.0, "all": 0.0, "mrr": 0.5}


@pytest.mark.parametrize("gold,ranked,expected", [
    (["A", "B"], ["A", "B", "C"], "all"),
    (["A", "B"], ["A", "C"], "some"),
    (["A", "B"], ["C", "D"], "none"),
])
def test_evidence_shown(gold, ranked, expected):
    assert run_eval.evidence_shown(gold, ranked) == expected


ANS = {"answerable": True}
UNANS = {"answerable": False}


@pytest.mark.parametrize("q,reply,shown,expected", [
    (UNANS, "I don't know", None, "CORRECT_REFUSAL"),
    (UNANS, "I don’t know.", None, "CORRECT_REFUSAL"),
    (UNANS, "Next Friday.", None, "FAILED_REFUSAL"),
    (ANS, "I don't know", "all", "INCORRECT_REFUSAL"),
    (ANS, "I don't know", "some", "PARTIAL_RETRIEVAL"),
    (ANS, "I don't know", "none", "RETRIEVAL_MISS"),
    (ANS, "On the 13th.", "none", "NEEDS_JUDGE"),
])
def test_code_label(q, reply, shown, expected):
    assert run_eval.code_label(q, reply, shown) == expected


def test_rank_orders_by_cosine():
    notes = [{"id": "far"}, {"id": "near"}, {"id": "mid"}]
    vecs = [[0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
    assert run_eval.rank([1.0, 0.0], notes, vecs, k=2) == ["near", "mid"]


@pytest.mark.parametrize("text,label", [
    ('{"label": "CORRECT", "rationale": "N1 says so"}', "CORRECT"),
    ('{"label": "PARTIAL_ANSWER", "rationale": "x"}', "PARTIAL_ANSWER"),
    ('{"label": "OTHER_NOTES", "rationale": "x"}', "OTHER_NOTES"),
    ('{"label": "RETRIEVAL_MISS", "rationale": "x"}', "JUDGE_PARSE_ERROR"),  # code's job, not the judge's
    ('{"label": "JUDGE_PARSE_ERROR"}', "JUDGE_PARSE_ERROR"),
    ("not json", "JUDGE_PARSE_ERROR"),
    ('["CORRECT"]', "JUDGE_PARSE_ERROR"),
])
def test_parse_verdict(text, label):
    assert judge.parse_verdict(text)["label"] == label


def test_judge_prompt_separates_key_from_other_notes(dataset):
    notes, questions = dataset
    by_id = {n["id"]: n for n in notes}
    q = next(x for x in questions if x["ordered"])
    other = [n for n in notes if n["id"] not in q["gold_notes"]][:2]
    prompt = judge.build_prompt(q, [by_id[g] for g in q["gold_notes"]], other, "Some reply")
    evidence_part, other_part = prompt.split("OTHER NOTES the chatbot")
    for g in q["gold_notes"]:
        assert by_id[g]["text"] in evidence_part
    for n in other:
        assert n["text"] in other_part
    assert "time order" in prompt
    # never the label or score code already computed
    for leak in ("RETRIEVAL_MISS", "PARTIAL_RETRIEVAL", "hit@", "all@", "recall"):
        assert leak not in prompt


def _fake_run(tmp_path, dataset, replies):
    """A run folder as run() would write it, with canned replies and retrievals."""
    notes, questions = dataset
    out = tmp_path / "run"
    out.mkdir()
    (out / "config.json").write_text(json.dumps(
        {"model": "fake:1b", "k": 5, "retriever": "test", "n_notes": len(notes),
         "n_questions": len(questions), **run_eval.manifest_check()}))
    with (out / "raw.jsonl").open("w") as f:
        for q in questions:
            reply, retrieved = replies(q)
            f.write(json.dumps({"qid": q["id"], "reply": reply, "retrieved": retrieved}) + "\n")
    return out


def test_score_without_judge(tmp_path, dataset):
    # Perfect retrieval, but the bot refuses everything: unanswerables are right, every
    # answerable refusal is a reading failure because all the evidence was shown.
    out = _fake_run(tmp_path, dataset, lambda q: ("I don't know", q["gold_notes"] or ["N_x"]))
    report = run_eval.score(out)
    rows = [json.loads(line) for line in (out / "scored.jsonl").open()]
    labels = {r["label"] for r in rows}
    assert labels == {"CORRECT_REFUSAL", "INCORRECT_REFUSAL"}
    assert all(r["ret"]["all"] == 1.0 for r in rows if r["ret"])
    assert "DRAFT until filled" in report
    assert "judge: none" in report


def test_score_with_judge_uses_judge_only_for_answers(tmp_path, dataset, monkeypatch):
    calls = []

    def fake_grade(model, q, evidence, other, reply):
        calls.append(q["id"])
        assert not {n["id"] for n in other} & set(q["gold_notes"])
        return {"label": "CORRECT", "rationale": "fine"}

    monkeypatch.setattr(judge, "grade", fake_grade)
    out = _fake_run(tmp_path, dataset,
                    lambda q: ("An answer." if q["answerable"] else "I don't know", q["gold_notes"][:1]))
    report = run_eval.score(out, judge_model="other:7b")
    answerable = [q["id"] for q in dataset[1] if q["answerable"]]
    assert calls == answerable
    assert f"**Right: {len(dataset[1])}/{len(dataset[1])}**" in report
    assert json.loads((out / "config.json").read_text())["judge_model"] == "other:7b"


def test_report_flags_self_grading(tmp_path, dataset, monkeypatch):
    monkeypatch.setattr(judge, "grade", lambda *a: {"label": "CORRECT", "rationale": ""})
    out = _fake_run(tmp_path, dataset, lambda q: ("An answer.", q["gold_notes"]))
    assert "SELF-GRADING" in run_eval.score(out, judge_model="fake:1b")


def test_failure_table_lists_evidence_and_retrieval(tmp_path, dataset):
    out = _fake_run(tmp_path, dataset, lambda q: ("I don't know", ["N_none"]))
    report = run_eval.score(out)
    q = next(x for x in dataset[1] if x["answerable"])
    row = next(line for line in report.splitlines() if line.startswith(f"| {q['id']} "))
    assert ", ".join(q["gold_notes"]) in row and "N_none" in row and "RETRIEVAL_MISS" in row


def test_report_flags_correct_without_evidence(tmp_path, dataset, monkeypatch):
    monkeypatch.setattr(judge, "grade", lambda *a: {"label": "CORRECT", "rationale": ""})
    all_gold = {g for q in dataset[1] for g in q["gold_notes"]}
    decoy = next(n["id"] for n in dataset[0] if n["id"] not in all_gold)
    out = _fake_run(tmp_path, dataset, lambda q: ("An answer.", [decoy]))
    report = run_eval.score(out, judge_model="other:7b")
    line = next(x for x in report.splitlines() if x.startswith("**Judged correct without"))
    first = next(q for q in dataset[1] if q["answerable"])
    assert f"{first['id']} (none)" in line
