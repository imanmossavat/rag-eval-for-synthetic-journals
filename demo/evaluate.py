"""
evaluate.py — run every (model x memory design) chatbot on every question, then score.

Scoring is deterministic — no LLM judge. That is possible only because the data is
controlled: every answer is a short exact string (a name, a brand, a number) that we
wrote down before the notes existed.

    .venv/bin/python demo/evaluate.py                              # default models, all bots
    .venv/bin/python demo/evaluate.py --models qwen3:4b --bots vector_rag full_context
    .venv/bin/python demo/evaluate.py --score runs/<run-folder>    # re-score an old run

Output: demo/runs/<timestamp>/raw.jsonl (one row per answer) + report.md (the tables).
"""

import argparse
import datetime as dt
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import chatbots

DEMO = Path(__file__).parent
DEFAULT_MODELS = ["qwen3:4b", "qwen3:30b"]

# ─────────────────────────────────────────────────────────────── answer scoring

NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}

# A label per answer. CORRECT + CORRECT_IDK count as right; the rest say HOW it was wrong.
LABELS = {
    "CORRECT":           "answered correctly",
    "PARTIAL":           "list question, only some items named",
    "WRONG_DISTRACTOR":  "named a look-alike or an out-of-date value (the trap worked)",
    "WRONG_OTHER":       "wrong in some other way",
    "IDK_BUT_IN_MEMORY": "said 'I don't know' although the answer WAS in what it was shown (reading failure)",
    "IDK_NOT_IN_MEMORY": "said 'I don't know' and the answer was NOT in what it was shown (memory/retrieval failure)",
    "CORRECT_IDK":       "unanswerable question, correctly said 'I don't know'",
    "HALLUCINATED":      "unanswerable question, made an answer up",
    "RAMBLED":           "ignored the short-answer format (over 40 words), so no answer to grade",
}
MAX_WORDS = 40  # every expected answer is under 12 words; past this the model is thinking out loud
RIGHT = {"CORRECT", "CORRECT_IDK"}


def norm(s: str) -> str:
    s = re.sub(r"<think>.*?</think>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()


def contains(text_norm: str, value: str) -> bool:
    return f" {norm(value)} " in f" {text_norm} "


def is_idk(reply: str) -> bool:
    t = norm(reply)
    return (t.startswith(("i don t know", "i do not know", "unknown"))
            or "not mentioned" in t or "no information" in t or "does not contain" in t)


def first_number(reply: str):
    for tok in norm(reply).split():
        if tok.isdigit():
            return tok
        if tok in NUMBER_WORDS:
            return NUMBER_WORDS[tok]
    return None


def memory_has_answer(q: dict, context: str):
    """Was the answer even present in what the model was shown? Separates
    'memory lost it' from 'model couldn't use it'. None = can't tell by string match."""
    if not q["answerable"] or q["type"] == "count":
        return None
    c = norm(context)
    return all(contains(c, a) for a in q["answer"])


def label(q: dict, reply: str, in_memory) -> str:
    # A long reply would match almost any answer by accident (one 13,000-word ramble
    # contained every name in the journal), so it gets no credit.
    if len(norm(reply).split()) > MAX_WORDS:
        return "RAMBLED"
    if not q["answerable"]:
        return "CORRECT_IDK" if is_idk(reply) else "HALLUCINATED"
    if is_idk(reply):
        return "IDK_BUT_IN_MEMORY" if in_memory else "IDK_NOT_IN_MEMORY"
    r = norm(reply)
    if q["type"] == "count":
        return "CORRECT" if first_number(reply) == q["answer"][0] else "WRONG_OTHER"
    present = [a for a in q["answer"] if contains(r, a)]
    if len(present) == len(q["answer"]):
        return "CORRECT"
    if q["conjunct"] and present:
        return "PARTIAL"
    if any(contains(r, d) for d in q["distractor_values"]):
        return "WRONG_DISTRACTOR"
    return "WRONG_OTHER"


# ─────────────────────────────────────────────────────────────── retrieval scoring

def retrieval_metrics(gold: list[str], ranked: list[str]) -> dict:
    """Standard retrieval metrics over the K notes the RAG bot fetched.
    precision@K  share of fetched notes that are evidence
    recall@K     share of evidence notes that were fetched
    hit@K        at least one evidence note fetched
    all@K        EVERY evidence note fetched (what multi-note questions actually need)
    MRR          1 / rank of the first evidence note (1.0 = it was the top result)"""
    g = set(gold)
    hits = [r for r in ranked if r in g]
    rank = next((i + 1 for i, r in enumerate(ranked) if r in g), None)
    return {"precision": len(hits) / len(ranked), "recall": len(hits) / len(g),
            "hit": float(bool(hits)), "all": float(g <= set(ranked)),
            "mrr": 1 / rank if rank else 0.0}


# ─────────────────────────────────────────────────────────────── run

def run(models, bot_names, k, out_dir: Path):
    notes = json.loads((DEMO / "data" / "notes.json").read_text())
    questions = json.loads((DEMO / "data" / "questions.json").read_text())
    out_dir.mkdir(parents=True)
    (out_dir / "config.json").write_text(json.dumps(
        {"models": models, "bots": bot_names, "k": k, "n_notes": len(notes),
         "n_questions": len(questions), "answer_system_prompt": chatbots.ANSWER_SYSTEM}, indent=2))
    raw = (out_dir / "raw.jsonl").open("w")
    for model in models:
        for bname in bot_names:
            t0 = time.time()
            cls = chatbots.BOTS[bname]
            bot = cls(notes, model, k=k) if bname == "vector_rag" else cls(notes, model)
            print(f"{model:<12} {bname:<13} memory ready in {time.time() - t0:5.0f}s", flush=True)
            for q in questions:
                context, ranked = bot.memory_for(q["question"])
                t1 = time.time()
                reply = chatbots.answer(model, context, q["question"])
                raw.write(json.dumps({"model": model, "bot": bname, "qid": q["id"], "reply": reply,
                                      "retrieved": ranked, "context": context,
                                      "seconds": round(time.time() - t1, 2)}) + "\n")
                raw.flush()
            print(f"{'':<12} {bname:<13} answered in {time.time() - t0:5.0f}s", flush=True)
    raw.close()


# ─────────────────────────────────────────────────────────────── report

TYPE_ORDER = ["single_fact", "current_state", "previous_state", "two_hop", "count", "history", "unanswerable"]


def score(out_dir: Path) -> str:
    questions = {q["id"]: q for q in json.loads((DEMO / "data" / "questions.json").read_text())}
    rows = [json.loads(line) for line in (out_dir / "raw.jsonl").open()]
    for r in rows:
        q = questions[r["qid"]]
        r["in_memory"] = memory_has_answer(q, r["context"])
        r["label"] = label(q, r["reply"], r["in_memory"])
        r["type"], r["level"] = q["type"], q["level"]
        if r["retrieved"] and q["gold_notes"]:
            r["ret"] = retrieval_metrics(q["gold_notes"], r["retrieved"])
    combos = list(dict.fromkeys((r["model"], r["bot"]) for r in rows))
    levels = {q["type"]: q["level"] for q in questions.values()}
    n_type = Counter(q["type"] for q in questions.values())
    types = [t for t in TYPE_ORDER if t in n_type]

    def table(title, cell, note=""):
        head = "| question type | n | " + " | ".join(f"{b}<br>{m}" for m, b in combos) + " |"
        lines = [f"### {title}\n", note, head, "|" + "---|" * (len(combos) + 2)]
        for t in types:
            cells = [cell([r for r in rows if r["type"] == t and (r["model"], r["bot"]) == c]) for c in combos]
            lines.append(f"| L{levels[t]} {t} | {n_type[t]} | " + " | ".join(cells) + " |")
        cells = [cell([r for r in rows if (r["model"], r["bot"]) == c]) for c in combos]
        lines.append(f"| **all** | {len(questions)} | " + " | ".join(f"**{x}**" for x in cells) + " |")
        return "\n".join(lines) + "\n"

    def acc(rs):
        return f"{sum(r['label'] in RIGHT for r in rs)}/{len(rs)}" if rs else "-"

    def in_mem(rs):
        known = [r for r in rs if r["in_memory"] is not None]
        return f"{sum(r['in_memory'] for r in known)}/{len(known)}" if known else "n/a"

    out = [f"# Results — {out_dir.name}\n",
           table("Accuracy (right answers / questions)", acc),
           table("Was the answer in what the model was shown?", in_mem,
                 "String check on the context each bot handed the model (n/a: counts and unanswerables).\n")]

    lines = ["### Why answers were wrong (label counts)\n",
             "| label | meaning | " + " | ".join(f"{b}<br>{m}" for m, b in combos) + " |",
             "|---|---|" + "---|" * len(combos)]
    for lab, meaning in LABELS.items():
        counts = [str(sum(1 for r in rows if (r["model"], r["bot"]) == c and r["label"] == lab)) for c in combos]
        lines.append(f"| {lab} | {meaning} | " + " | ".join(counts) + " |")
    out.append("\n".join(lines) + "\n")

    rag = [r for r in rows if r.get("ret")]
    if rag:
        model0 = rag[0]["model"]  # retrieval doesn't depend on the answering model
        rr = [r for r in rag if r["model"] == model0]
        lines = ["### Retrieval quality of vector_rag (same for every model)\n",
                 "| question type | precision@K | recall@K | hit@K | all@K | MRR |", "|---|---|---|---|---|---|"]
        by = defaultdict(list)
        for r in rr:
            by[r["type"]].append(r["ret"])
        for t in types + ["**all**"]:
            ms = [m for r in rr for m in [r["ret"]]] if t == "**all**" else by.get(t)
            if ms:
                avg = {k: sum(m[k] for m in ms) / len(ms) for k in ms[0]}
                lines.append(f"| {t} | {avg['precision']:.2f} | {avg['recall']:.2f} | {avg['hit']:.2f} | "
                             f"{avg['all']:.2f} | {avg['mrr']:.2f} |")
        out.append("\n".join(lines) + "\n")

    lines = ["### Every answer\n", "| q | type | expected | " + " | ".join(f"{b}<br>{m}" for m, b in combos) + " |",
             "|---|---|---|" + "---|" * len(combos)]
    for qid, q in questions.items():
        cells = []
        for c in combos:
            r = next((r for r in rows if r["qid"] == qid and (r["model"], r["bot"]) == c), None)
            if r:
                mark = "✅" if r["label"] in RIGHT else "❌"
                cells.append(f"{mark} {r['reply'][:60].replace('|', '/').replace(chr(10), ' ')}")
            else:
                cells.append("-")
        exp = ", ".join(q["answer"]) or "(I don't know)"
        lines.append(f"| {qid} {q['question']} | L{q['level']} {q['type']} | {exp} | " + " | ".join(cells) + " |")
    out.append("\n".join(lines) + "\n")

    report = "\n".join(out)
    (out_dir / "report.md").write_text(report)
    (out_dir / "scored.jsonl").write_text("".join(
        json.dumps({k: v for k, v in r.items() if k != "context"}) + "\n" for r in rows))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--bots", nargs="+", default=list(chatbots.BOTS), choices=list(chatbots.BOTS))
    ap.add_argument("--k", type=int, default=5, help="notes fetched by vector_rag")
    ap.add_argument("--score", type=Path, help="re-score an existing run folder instead of running")
    args = ap.parse_args()

    if args.score:
        out_dir = args.score
    else:
        out_dir = DEMO / "runs" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run(args.models, args.bots, args.k, out_dir)
    print(score(out_dir))
    print(f"\nwrote {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
