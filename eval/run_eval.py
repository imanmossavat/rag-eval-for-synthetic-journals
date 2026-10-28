"""
run_eval.py — evaluate a RAG chatbot on the pipeline corpus (data/notes.json + data/qa_pairs.json).

The pipeline's answer key is a set of note IDs (`answer_key.evidence`), not a prose answer.
So scoring has two layers:

  1. Code, no LLM. Retrieval metrics against the evidence notes, plus every answer label
     that needs no reading: refusals on unanswerable questions, and refusals on answerable
     ones split by how much evidence the model was actually shown.
  2. An LLM judge (judge.py, optional) — only for answers to answerable questions. It sees
     the question, the evidence notes and the reply, and says whether the reply matches the
     evidence. It is never shown the retrieval result, so it can't be anchored by it.

    .venv/bin/python eval/run_eval.py                                  # qwen3:4b, k=5, no judge
    .venv/bin/python eval/run_eval.py --model qwen3:4b --judge-model qwen3:30b
    .venv/bin/python eval/run_eval.py --score eval/runs/<run-folder> [--judge-model ...]

Output: eval/runs/<timestamp>/ with config.json, raw.jsonl (one row per question),
scored.jsonl and report.md. See eval/README.md and eval/REPORTING_STANDARDS.md.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parent
DATA = ROOT / "data"
CACHE = EVAL / "runs" / "cache"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"

ANSWER_SYSTEM = (
    "You answer questions about the user's personal journal, using ONLY the journal notes you are given. "
    "The user wrote the journal, so 'I'/'my' in the question means the journal's author. "
    "Answer in one to three sentences, with no preamble. "
    "If the notes do not contain the answer, reply exactly: I don't know"
)

# ─────────────────────────────────────────────────────────────── dataset

def load_dataset(data_dir: Path = DATA) -> tuple[list[dict], list[dict]]:
    """Notes (date order) and questions in one flat shape the rest of this file uses."""
    raw_notes = json.loads((data_dir / "notes.json").read_text())["notes"]
    notes = sorted(({"id": n["note_id"], "date": n["timestamp"], "text": n["text"]} for n in raw_notes),
                   key=lambda n: n["date"])
    questions = []
    for q in json.loads((data_dir / "qa_pairs.json").read_text())["qa_pairs"]:
        key = q["answer_key"]
        questions.append({"id": q["question_id"], "type": q["reasoning_type"], "question": q["question"],
                          "gold_notes": list(key["evidence"]), "ordered": key["ordered"],
                          "answerable": q["reasoning_type"] != "unanswerable"})
    return notes, questions


def check_dataset(notes: list[dict], questions: list[dict]) -> list[str]:
    """The joins every number in a report rests on. An evidence ID that isn't a real note
    silently turns into a retrieval miss, so this must be empty before a run counts."""
    ids = [n["id"] for n in notes]
    errs = [f"duplicate note id {i}" for i, c in Counter(ids).items() if c > 1]
    known = set(ids)
    for q in questions:
        errs += [f"{q['id']}: evidence {g} is not in notes.json" for g in q["gold_notes"] if g not in known]
        if q["answerable"] and not q["gold_notes"]:
            errs.append(f"{q['id']}: answerable but has no evidence notes")
        if not q["answerable"] and q["gold_notes"]:
            errs.append(f"{q['id']}: unanswerable but has evidence notes")
    return errs


def manifest_check(data_dir: Path = DATA) -> dict:
    """Corpus version plus whether each data file still matches the manifest's hash
    (a partial regeneration once left notes.json and qa_pairs.json from different runs)."""
    m = json.loads((data_dir / "MANIFEST.json").read_text())
    files = {}
    for name, f in m["files"].items():
        path = data_dir / Path(f["path"]).name
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() == f["sha256"]
    return {"corpus_version": m["corpus_version"], "files_match_manifest": files}

# ─────────────────────────────────────────────────────────────── models (Ollama)

def _ollama(endpoint: str, payload: dict) -> dict:
    try:
        r = requests.post(f"{OLLAMA}/api/{endpoint}", json=payload, timeout=1800)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Ollama is not reachable at {OLLAMA} — run `ollama serve`")
    r.raise_for_status()
    return r.json()


def chat(model: str, system: str, user: str, json_mode: bool = False) -> str:
    if model.startswith("qwen3:"):
        user += " /no_think"  # some qwen3 builds ignore think=False
    body = _ollama("chat", {"model": model, "stream": False, "think": False,
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
                            **({"format": "json"} if json_mode else {}),
                            "options": {"num_ctx": 16384, "temperature": 0}})
    return body["message"]["content"].split("</think>")[-1].strip()


def embed(texts: list[str], kind: str) -> list[list[float]]:
    prefix = "search_query: " if kind == "query" else "search_document: "  # nomic's task prefixes
    return _ollama("embed", {"model": EMBED_MODEL, "input": [prefix + t for t in texts]})["embeddings"]

# ─────────────────────────────────────────────────────────────── retrieval

def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def rank(query_vec, notes: list[dict], vectors: list, k: int) -> list[str]:
    scored = sorted(zip(notes, vectors), key=lambda nv: -cosine(query_vec, nv[1]))
    return [n["id"] for n, _ in scored[:k]]


def note_vectors(notes: list[dict]) -> list:
    key = hashlib.sha1("".join(n["text"] for n in notes).encode()).hexdigest()[:8]
    path = CACHE / f"embeddings_{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    vectors = embed([n["text"] for n in notes], kind="document")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vectors))
    return vectors


def format_notes(notes: list[dict]) -> str:
    return "\n\n".join(f"[{n['date'][:16]}] {n['text']}" for n in notes)

# ─────────────────────────────────────────────────────────────── scoring (code)

def retrieval_metrics(gold: list[str], ranked: list[str]) -> dict:
    """precision@K  share of fetched notes that are evidence
    recall@K     share of evidence notes that were fetched
    hit@K        at least one evidence note fetched (often called "context recall")
    all@K        EVERY evidence note fetched — what a multi-note question actually needs
    MRR          1 / rank of the first evidence note"""
    g = set(gold)
    hits = [r for r in ranked if r in g]
    first = next((i + 1 for i, r in enumerate(ranked) if r in g), None)
    return {"precision": len(hits) / len(ranked), "recall": len(hits) / len(g),
            "hit": float(bool(hits)), "all": float(g <= set(ranked)),
            "mrr": 1 / first if first else 0.0}


def evidence_shown(gold: list[str], ranked: list[str]) -> str:
    """'all' | 'some' | 'none' of the evidence notes reached the model."""
    got = len(set(gold) & set(ranked))
    return "all" if got == len(set(gold)) else "some" if got else "none"


def is_refusal(reply: str) -> bool:
    t = re.sub(r"\s+", " ", (reply or "").lower().replace("’", "'")).strip()
    return t.startswith(("i don't know", "i do not know", "i dont know"))


# Labels decided by code. Answers to answerable questions get NEEDS_JUDGE until judge.py runs.
CODE_LABELS = {
    "CORRECT_REFUSAL":   "unanswerable question, correctly said 'I don't know'",
    "FAILED_REFUSAL":    "unanswerable question, made an answer up",
    "INCORRECT_REFUSAL": "said 'I don't know' although EVERY evidence note was shown (reading failure)",
    "PARTIAL_RETRIEVAL": "said 'I don't know'; only some evidence notes were shown",
    "RETRIEVAL_MISS":    "said 'I don't know'; no evidence note was shown (retrieval failure)",
    "NEEDS_JUDGE":       "gave an answer to an answerable question; only the judge can grade it",
}
RIGHT = {"CORRECT", "CORRECT_REFUSAL"}


def code_label(q: dict, reply: str, shown: str | None) -> str:
    if not q["answerable"]:
        return "CORRECT_REFUSAL" if is_refusal(reply) else "FAILED_REFUSAL"
    if is_refusal(reply):
        return {"all": "INCORRECT_REFUSAL", "some": "PARTIAL_RETRIEVAL", "none": "RETRIEVAL_MISS"}[shown]
    return "NEEDS_JUDGE"

# ─────────────────────────────────────────────────────────────── run

def run(model: str, k: int, out_dir: Path) -> None:
    notes, questions = load_dataset()
    errs = check_dataset(notes, questions)
    if errs:
        raise SystemExit("dataset is broken, refusing to run:\n  " + "\n  ".join(errs))
    by_id = {n["id"]: n for n in notes}
    vectors = note_vectors(notes)
    out_dir.mkdir(parents=True)
    (out_dir / "config.json").write_text(json.dumps(
        {"model": model, "k": k, "retriever": f"dense cosine, {EMBED_MODEL}",
         "n_notes": len(notes), "n_questions": len(questions), **manifest_check(),
         "answer_system_prompt": ANSWER_SYSTEM}, indent=2))
    with (out_dir / "raw.jsonl").open("w") as raw:
        for q in questions:
            ranked = rank(embed([q["question"]], kind="query")[0], notes, vectors, k)
            context = format_notes(sorted((by_id[i] for i in ranked), key=lambda n: n["date"]))
            t0 = time.time()
            reply = chat(model, ANSWER_SYSTEM, f"JOURNAL NOTES:\n{context}\n\nQUESTION: {q['question']}")
            raw.write(json.dumps({"qid": q["id"], "reply": reply, "retrieved": ranked,
                                  "seconds": round(time.time() - t0, 2)}) + "\n")
            print(f"  {q['id']} {q['type']:<20} {reply[:70]!r}", flush=True)

# ─────────────────────────────────────────────────────────────── report

TYPE_ORDER = ["single_hop", "multi_hop", "temporal_reasoning", "conflict_resolution",
              "belief_currency", "unanswerable"]


def score(out_dir: Path, judge_model: str | None = None) -> str:
    notes, questions = load_dataset()
    qs = {q["id"]: q for q in questions}
    by_id = {n["id"]: n for n in notes}
    cfg = json.loads((out_dir / "config.json").read_text())
    rows = [json.loads(line) for line in (out_dir / "raw.jsonl").open()]
    for r in rows:
        q = qs[r["qid"]]
        r["type"] = q["type"]
        r["shown"] = evidence_shown(q["gold_notes"], r["retrieved"]) if q["answerable"] else None
        r["ret"] = retrieval_metrics(q["gold_notes"], r["retrieved"]) if q["answerable"] else None
        r["label"] = code_label(q, r["reply"], r["shown"])

    if judge_model:
        import judge
        if judge_model == cfg["model"]:
            print(f"warning: judge {judge_model} is also the answering model (self-grading)")
        for r in rows:
            if r["label"] == "NEEDS_JUDGE":
                q = qs[r["qid"]]
                other = [by_id[i] for i in r["retrieved"] if i not in q["gold_notes"]]
                v = judge.grade(judge_model, q, [by_id[g] for g in q["gold_notes"]], other, r["reply"])
                r["label"], r["rationale"] = v["label"], v["rationale"]
        cfg["judge_model"] = judge_model
        (out_dir / "config.json").write_text(json.dumps(cfg, indent=2))
    labels = dict(CODE_LABELS)
    if any(r["label"] not in CODE_LABELS for r in rows):
        import judge
        labels.update(judge.LABELS)

    types = [t for t in TYPE_ORDER if any(q["type"] == t for q in questions)]
    judge_name = cfg.get("judge_model")
    self_grading = judge_name == cfg["model"]
    files_ok = all(cfg["files_match_manifest"].values())
    out = [f"# Pipeline-corpus eval — {out_dir.name}\n",
           "Cold-reader pass (REPORTING_STANDARDS rule 2): ___________  (DRAFT until filled)\n",
           f"- corpus `{cfg['corpus_version']}`, {cfg['n_notes']} notes, {cfg['n_questions']} questions; "
           f"data files match MANIFEST: {'yes' if files_ok else 'NO — ' + str(cfg['files_match_manifest'])}",
           f"- answering model `{cfg['model']}`, retriever {cfg['retriever']}, K={cfg['k']}",
           f"- judge: {('`' + judge_name + '`' + (' — SELF-GRADING, human check required' if self_grading else '')) if judge_name else 'none (answers to answerable questions are ungraded)'}\n"]

    lines = ["### Retrieval (answerable questions)\n",
             "| type | n | precision@K | recall@K | hit@K | all@K | MRR |", "|---|---|---|---|---|---|---|"]
    rag = [r for r in rows if r["ret"]]
    for t in types + ["**all**"]:
        ms = [r["ret"] for r in rag if t == "**all**" or r["type"] == t]
        if ms:
            a = {m: sum(x[m] for x in ms) / len(ms) for m in ms[0]}
            lines.append(f"| {t} | {len(ms)} | {a['precision']:.2f} | {a['recall']:.2f} | {a['hit']:.2f} | "
                         f"{a['all']:.2f} | {a['mrr']:.2f} |")
    out.append("\n".join(lines) + "\n")

    present = [lab for lab in labels if any(r["label"] == lab for r in rows)]
    lines = ["### Answer labels by type\n", "| label | meaning | " + " | ".join(types) + " | all |",
             "|---|---|" + "---|" * (len(types) + 1)]
    for lab in present:
        counts = [sum(1 for r in rows if r["type"] == t and r["label"] == lab) for t in types]
        lines.append(f"| {lab} | {labels[lab]} | " + " | ".join(map(str, counts)) + f" | {sum(counts)} |")
    out.append("\n".join(lines) + "\n")
    if judge_name:
        right = sum(r["label"] in RIGHT for r in rows)
        out.append(f"**Right: {right}/{len(rows)}** (CORRECT + CORRECT_REFUSAL). Judge labels are advisory "
                   "until a human has checked them.\n")
        # Code can check what the judge can't be trusted to: was the evidence even there?
        unproven = [r for r in rows if r["label"] == "CORRECT" and r["shown"] != "all"]
        if unproven:
            out.append("**Judged correct without all the evidence shown:** "
                       + ", ".join(f"{r['qid']} ({r['shown']})" for r in unproven)
                       + ". Either a lucky guess, a near-duplicate note carrying the same fact, or a "
                         "judge mistake. Check these first.\n")

    # Rule 1 + 3: every non-right row, verbatim, with the fields its label rests on.
    lines = ["### Every answer that isn't right, with its evidence\n",
             "| q | type | question | evidence | retrieved (rank order) | shown | reply | label | judge rationale |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["label"] in RIGHT:
            continue
        q = qs[r["qid"]]
        cell = lambda s: str(s).replace("|", "/").replace("\n", " ")  # noqa: E731
        lines.append(f"| {r['qid']} | {q['type']} | {cell(q['question'])} | {', '.join(q['gold_notes']) or '-'} | "
                     f"{', '.join(r['retrieved'])} | {r['shown'] or '-'} | {cell(r['reply'])} | {r['label']} | "
                     f"{cell(r.get('rationale', ''))} |")
    out.append("\n".join(lines) + "\n")

    report = "\n".join(out)
    (out_dir / "report.md").write_text(report)
    (out_dir / "scored.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:4b", help="answering model (Ollama)")
    ap.add_argument("--k", type=int, default=5, help="notes retrieved per question")
    ap.add_argument("--judge-model", help="Ollama model for judge.py; omit to skip the judge")
    ap.add_argument("--score", type=Path, help="re-score an existing run folder instead of running")
    args = ap.parse_args()

    if args.score:
        out_dir = args.score
    else:
        out_dir = EVAL / "runs" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run(args.model, args.k, out_dir)
    print(score(out_dir, args.judge_model))
    print(f"\nwrote {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
