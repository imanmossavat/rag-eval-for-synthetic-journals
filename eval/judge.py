"""
judge.py — LLM judge for answers that code can't grade.

The pipeline's answer key is a set of evidence notes, not a sentence, so whether a reply
to an answerable question is right needs reading. The judge sees the question, the
evidence notes (the answer key), the OTHER notes the chatbot was shown, and the reply.
It is not told any label code already gave or any retrieval score: a judge shown the
label it is checking tends to confirm it. Everything code can decide stays in code.

Why the other notes: the corpus has near-duplicate notes (the same activity on several
days). A reply that rests on a later near-duplicate is not a hallucination, and it can
mean the answer key itself is incomplete. The first real run (2026-10-28) had the judge
call such replies hallucinations because it could only see the key. OTHER_NOTES flags
them for a human instead.

Use a judge that is not the answering model (REPORTING_STANDARDS rule 5); run_eval.py
warns if they're the same.
"""

import json

import run_eval

LABELS = {
    "CORRECT":                  "matches the evidence notes",
    "PARTIAL_ANSWER":           "right as far as it goes, but leaves out part of what the evidence says",
    "CONTRADICTS_NOTES":        "says something the evidence notes contradict",
    "GENERATION_HALLUCINATION": "states a concrete fact (name, number, date, event) not in the evidence",
    "GENERATION_OVERREACH":     "adds psychological or causal claims the evidence doesn't license",
    "OTHER_NOTES":              "rests on a shown note outside the answer key; a human should check the key",
    "JUDGE_PARSE_ERROR":        "the judge's reply wasn't valid JSON with a known label",
}

JUDGE_SYSTEM = "You grade answers strictly against the evidence you are given. Output JSON only."

JUDGE_PROMPT = """A chatbot answered a question about the user's personal journal. The EVIDENCE notes below are
the answer key: a correct answer is one these notes support. Grade the ANSWER with exactly one label.
Judge the answer against the EVIDENCE alone first. Use the OTHER NOTES only to tell OTHER_NOTES apart
from a hallucination: if the answer's main claim (a date, state or outcome) comes from an OTHER NOTE
rather than the evidence, the label is OTHER_NOTES, even if the answer seems reasonable.

- CORRECT: the EVIDENCE alone supports the answer, and it answers the question. Wording may differ.
- PARTIAL_ANSWER: right as far as it goes, but leaves out part the question asks for.
- CONTRADICTS_NOTES: says something the evidence contradicts.
- GENERATION_HALLUCINATION: states a concrete fact (name, number, date, event detail) not in the evidence.
- GENERATION_OVERREACH: adds psychological, causal or diagnostic claims the evidence doesn't support.
- OTHER_NOTES: disagrees with or goes beyond the evidence, but what it says is stated in the OTHER NOTES.
{order_rule}
QUESTION: {question}

EVIDENCE:
{evidence}

OTHER NOTES the chatbot was also shown (not part of the answer key):
{other}

ANSWER: {answer}

Reply with JSON only: {{"label": "<LABEL>", "rationale": "<one sentence citing the evidence>"}}"""

ORDER_RULE = "\nThe evidence is listed in time order and the question depends on that order (what happened first/after).\n"


def build_prompt(q: dict, evidence: list[dict], other: list[dict], reply: str) -> str:
    fmt = lambda ns: run_eval.format_notes(sorted(ns, key=lambda n: n["date"])) or "(none)"  # noqa: E731
    return JUDGE_PROMPT.format(order_rule=ORDER_RULE if q["ordered"] else "", question=q["question"],
                               evidence=fmt(evidence), other=fmt(other), answer=reply)


def parse_verdict(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"label": "JUDGE_PARSE_ERROR", "rationale": text[:200]}
    label = data.get("label") if isinstance(data, dict) else None
    if label not in LABELS or label == "JUDGE_PARSE_ERROR":
        return {"label": "JUDGE_PARSE_ERROR", "rationale": f"unknown label: {label!r}"}
    return {"label": label, "rationale": str(data.get("rationale", ""))[:400]}


def grade(model: str, q: dict, evidence: list[dict], other: list[dict], reply: str) -> dict:
    return parse_verdict(run_eval.chat(model, JUDGE_SYSTEM, build_prompt(q, evidence, other, reply), json_mode=True))
