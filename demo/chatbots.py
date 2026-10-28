"""
chatbots.py — four tiny journal chatbots that differ ONLY in how they remember.

Every bot uses the same answering prompt and the same local model; what changes is
the MEMORY the model is shown when a question comes in:

  full_context   Every note, in date order. No retrieval at all. The baseline —
                 only possible while the whole journal fits in the model's window.
  vector_rag     Standard RAG: embed every note, fetch the K most similar to the
                 question, show only those (in date order).
  summary        A running summary, rewritten after every note, capped in length
                 (the "rolling summary" / ConversationSummaryMemory pattern).
  facts          An extracted fact list: after every note, the model writes down the
                 facts it contains as short dated lines; all lines are kept
                 (append-only — the simplest Mem0-style memory).

Each bot exposes  .memory_for(question) -> (context_text, retrieved_note_ids | None).
Building summary/facts memories costs one model call per note, so they're cached
in runs/cache/ per model.
"""

import hashlib
import json
import math
from pathlib import Path

import llm_clients as llm

CACHE = Path(__file__).parent / "runs" / "cache"

ANSWER_SYSTEM = (
    "You answer questions about the user's personal journal, using ONLY the memory you are given. "
    "The user wrote the journal, so 'I'/'my' in the question means the journal's author. "
    "Reply with the short answer only: a name, place, number or short list - no explanation. "
    "If the memory does not contain the answer, reply exactly: I don't know"
)


def _fmt(note: dict) -> str:
    return f"[{note['date']}] {note['text']}"


def answer(model: str, context: str, question: str) -> str:
    return llm.chat(model, ANSWER_SYSTEM, f"MEMORY:\n{context}\n\nQUESTION: {question}")


class FullContext:
    name = "full_context"

    def __init__(self, notes, model):
        self.context = "\n\n".join(_fmt(n) for n in notes)

    def memory_for(self, question):
        return self.context, None


class VectorRAG:
    name = "vector_rag"

    def __init__(self, notes, model, k: int = 5):
        self.notes, self.k = notes, k
        path = CACHE / f"embeddings_{_key(notes)}.json"
        if path.exists():
            self.vectors = json.loads(path.read_text())
        else:
            self.vectors = llm.embed([n["text"] for n in notes], kind="document")
            CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.vectors))

    def memory_for(self, question):
        q = llm.embed([question], kind="query")[0]
        scored = sorted(zip(self.notes, self.vectors), key=lambda nv: -_cosine(q, nv[1]))
        top = [n for n, _ in scored[: self.k]]
        ranked_ids = [n["id"] for n in top]
        context = "\n\n".join(_fmt(n) for n in sorted(top, key=lambda n: n["id"]))
        return context, ranked_ids


SUMMARY_PROMPT = """You keep the memory of a personal journal. Below is the current memory and one new journal entry.
Rewrite the memory so it also includes what matters from the new entry: people, names, places,
things that changed (and when), and recurring activities. Keep it under {words} words.
Return only the new memory text.

CURRENT MEMORY:
{memory}

NEW ENTRY:
{note}"""


class Summary:
    name = "summary"

    def __init__(self, notes, model, words: int = 250):
        path = CACHE / f"summary_{_safe(model)}_{_key(notes)}.txt"
        if path.exists():
            self.memory = path.read_text()
            return
        memory = "(empty)"
        for n in notes:
            memory = llm.chat(model, "You are a careful note-keeper.",
                              SUMMARY_PROMPT.format(words=words, memory=memory, note=_fmt(n)))
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(memory)
        self.memory = memory

    def memory_for(self, question):
        return self.memory, None


FACTS_PROMPT = """Extract the facts stated in this journal entry as short lines, one per line, in the form
<date> | <fact>. Name people and things exactly as written. Only facts actually stated;
if there are none worth keeping, return nothing.

ENTRY:
{note}"""


class Facts:
    name = "facts"

    def __init__(self, notes, model):
        path = CACHE / f"facts_{_safe(model)}_{_key(notes)}.txt"
        if path.exists():
            self.memory = path.read_text()
            return
        lines = []
        for n in notes:
            out = llm.chat(model, "You extract facts precisely.", FACTS_PROMPT.format(note=_fmt(n)))
            lines += [ln.strip() for ln in out.splitlines() if "|" in ln]
        CACHE.mkdir(parents=True, exist_ok=True)
        self.memory = "\n".join(lines)
        path.write_text(self.memory)

    def memory_for(self, question):
        return self.memory, None


BOTS = {b.name: b for b in (FullContext, VectorRAG, Summary, Facts)}


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _safe(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def _key(notes) -> str:
    """Short hash of the corpus, so cached memories are rebuilt when the notes change."""
    return hashlib.sha1("".join(n["text"] for n in notes).encode()).hexdigest()[:8]
