"""
grounding_gate.py — independent cross-model grounding check for qa_pairs.json
================================================================================
WHY: a QA pair's key can cite notes that don't actually answer its question, and
an "unanswerable" pair can be answerable after all. A second model from a
different family checks both.

This script is a SEPARATE, READ-ONLY validator. It does not touch generation
code or regenerate anything. For each existing QA pair it asks an independent
model (gemma3:27b -- different family from the qwen3 generator, so it isn't
grading its own homework) one question: is this answer key actually supported
by (only) its cited notes? For "unanswerable" pairs the question flips: do the
notes genuinely NOT contain the answer?

The key is a set of evidence note ids (`answer_key.evidence`), not prose, so
`ANSWERABLE_PROMPT` checks whether the cited notes are sufficient to answer the
question at all.

Usage:
    python grounding_gate.py                      # full corpus
    python grounding_gate.py --ids q_0018,q_0028   # just these ids (calibration/spot-check)
    python grounding_gate.py --model gemma3:27b --out data/grounding_gate_results.json
"""

import argparse
import json
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
OLLAMA_URL = "http://localhost:11434/api/generate"
MAX_RETRIES = 3
TIMEOUT_SECONDS = 600

## v4 (2026-07-14): stage_05 no longer stores a prose answer -- the graded key is a pointer set
## (answer_key.evidence, the same note ids passed here as CITED NOTES). This prompt no longer
## checks a pre-written answer TEXT against the notes; it checks that the cited notes are
## actually SUFFICIENT to answer the question at all, which is the pointer-set equivalent of the
## same defect class (a cited note that doesn't really support the question it's pinned to).
ANSWERABLE_PROMPT = """You are an independent fact-checker for a RAG benchmark question. You did \
NOT write this question or these notes. Do not use outside knowledge -- only the notes below.

QUESTION: {question}

CITED NOTES (the note(s) this question's answer key points to as its evidence):
{notes_text}

Check ONLY one thing: do the cited notes, together, actually contain enough information to give a
specific, concrete answer to the question -- not just touch on the same topic, but actually
resolve it?

- If the notes do NOT contain enough information to answer the question -- they only hint at it,
  are about a related but different topic, or never address it -- return verdict "DEFECT",
  defect_type "unsupported_answer".
- If the notes clearly state something different or more specific than what the question implies
  (for example the question implies "free" but a note says "$2"), return verdict "DEFECT",
  defect_type "contradicted_by_notes".
- Otherwise, if the notes genuinely support a specific answer to the question, return verdict
  "PASS", defect_type null.

Return ONLY valid JSON, no markdown, no commentary:
{{
  "verdict": "PASS" | "DEFECT",
  "defect_type": null | "unsupported_answer" | "contradicted_by_notes",
  "quote": "the exact sentence or phrase from the cited notes your verdict rests on",
  "explanation": "one sentence"
}}"""

## v3: fully blind Q&A, no mention that the question was ever labeled "unanswerable" --
## v1/v2 both told the model the label up front ("this has been labeled unanswerable, check
## the claim"), and calibration showed that primed it to rationalize confirming that label
## even when its own stated reasoning found the notes contained a direct answer (q_0024/25/27:
## explanation admitted the note states the fact, verdict said PASS anyway). Removing any
## mention of the label and just asking it to answer the question directly removes that anchor.
UNANSWERABLE_PROMPT = """Answer the question below using ONLY the notes provided. Do not use \
outside knowledge and do not guess beyond what the notes state.

QUESTION: {question}

NOTES (the ONLY source you may use):
{notes_text}

If the notes state or clearly imply a specific, concrete answer to the question, give that exact
answer and quote the sentence it comes from.

If the notes do NOT contain enough information to answer the question -- they only hint at it,
hedge about it, or never address it at all -- say you cannot answer it.

Return ONLY valid JSON, no markdown, no commentary:
{{
  "can_answer": true | false,
  "answer": "the specific answer you found stated in the notes, or null if you cannot answer",
  "quote": "the exact sentence from the notes that supports your answer, or null",
  "explanation": "one sentence"
}}"""


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def call_ollama(prompt: str, model: str) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": -1},
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            body = resp.json()
            if body.get("done_reason") == "length":
                raise ValueError("truncated (done_reason=length)")
            return body.get("response", "").strip()
        except (requests.exceptions.RequestException, ValueError) as exc:
            if attempt < MAX_RETRIES:
                wait = attempt * 2
                print(f"    ⚠ attempt {attempt} failed ({exc}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"gemma3 call failed after {MAX_RETRIES} attempts") from exc


def parse_json_response(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def build_notes_text(note_ids: list[str], notes_by_id: dict) -> str:
    parts = []
    for nid in note_ids:
        n = notes_by_id.get(nid)
        if n is None:
            parts.append(f"[{nid}] <<UNRESOLVED NOTE ID -- does not exist in notes.json>>")
        else:
            parts.append(f"[{nid}] {n['text']}")
    return "\n\n".join(parts)


def check_qa(qa: dict, notes_by_id: dict, model: str) -> dict:
    notes_text = build_notes_text(qa["supporting_notes"], notes_by_id)
    if qa["reasoning_type"] == "unanswerable":
        prompt = UNANSWERABLE_PROMPT.format(question=qa["question"], notes_text=notes_text)
    else:
        prompt = ANSWERABLE_PROMPT.format(question=qa["question"], notes_text=notes_text)
    raw = call_ollama(prompt, model)
    try:
        parsed = parse_json_response(raw)
    except json.JSONDecodeError as exc:
        return {
            "question_id": qa["question_id"],
            "reasoning_type": qa["reasoning_type"],
            "verdict": "ERROR",
            "defect_type": None,
            "quote": None,
            "explanation": f"gate response was not valid JSON: {exc}. raw={raw[:200]!r}",
        }

    if qa["reasoning_type"] == "unanswerable":
        # blind-QA schema (can_answer/answer/quote) -> verdict/defect_type
        can_answer = bool(parsed.get("can_answer"))
        return {
            "question_id": qa["question_id"],
            "reasoning_type": qa["reasoning_type"],
            "verdict": "DEFECT" if can_answer else "PASS",
            "defect_type": "mislabeled_unanswerable" if can_answer else None,
            "quote": parsed.get("quote"),
            "explanation": parsed.get("explanation"),
        }

    return {
        "question_id": qa["question_id"],
        "reasoning_type": qa["reasoning_type"],
        "verdict": parsed.get("verdict"),
        "defect_type": parsed.get("defect_type"),
        "quote": parsed.get("quote"),
        "explanation": parsed.get("explanation"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--model", default="gemma3:27b")
    ap.add_argument("--ids", default=None, help="comma-separated question_ids to restrict to")
    ap.add_argument("--out", default=None, help="path to write JSON results")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    qa_pairs = load_json(data_dir / "qa_pairs.json")["qa_pairs"]
    notes = load_json(data_dir / "notes.json")["notes"]
    notes_by_id = {n["note_id"]: n for n in notes}

    # exact-id join check (REPORTING_STANDARDS rule 6): confirm every
    # supporting_notes id resolves before trusting anything downstream.
    unresolved = [
        (q["question_id"], sid)
        for q in qa_pairs
        for sid in q["supporting_notes"]
        if sid not in notes_by_id
    ]
    if unresolved:
        print(f"⚠ {len(unresolved)} unresolved supporting_notes ids: {unresolved}")
    else:
        print(f"✓ join check: all supporting_notes ids resolve exactly against notes.json "
              f"({len(qa_pairs)} qa pairs, {len(notes)} notes)")

    if args.ids:
        wanted = set(args.ids.split(","))
        qa_pairs = [q for q in qa_pairs if q["question_id"] in wanted]

    print(f"Running grounding gate ({args.model}) on {len(qa_pairs)} QA pair(s)...\n")

    results = []
    for qa in qa_pairs:
        print(f"  {qa['question_id']} ({qa['reasoning_type']})...", end=" ", flush=True)
        r = check_qa(qa, notes_by_id, args.model)
        results.append(r)
        print(r["verdict"], r["defect_type"] or "")

    n_total = len(results)
    n_defect = sum(1 for r in results if r["verdict"] == "DEFECT")
    n_error = sum(1 for r in results if r["verdict"] == "ERROR")
    n_pass = n_total - n_defect - n_error

    print("\n" + "=" * 66)
    print(f"GATE SUMMARY — model={args.model}  n={n_total}")
    print(f"  PASS:   {n_pass}")
    print(f"  DEFECT: {n_defect}  ({n_defect/n_total:.1%})" if n_total else "  DEFECT: 0")
    if n_error:
        print(f"  ERROR:  {n_error} (gate itself failed to produce a parseable verdict)")
    if n_defect:
        print("\n  Defective ids:")
        for r in results:
            if r["verdict"] == "DEFECT":
                print(f"    {r['question_id']} [{r['defect_type']}]: {r['quote']!r}")
    print("=" * 66)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"model": args.model, "results": results}, f, indent=2, ensure_ascii=False)
        print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
