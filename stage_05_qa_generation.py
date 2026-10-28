"""
Stage 05 — QA Generation
==========================
Reads notes.json and generates question-answer pairs grounded in the
note corpus. Uses evidence-first generation: the supporting notes are
chosen before the question is written, so gold evidence is always correct.

v2 (2026-07-13/14): the graded key is no longer LLM-invented prose. Each QA pair's
`answer_key` is an evidence-pointer set -- the note ID(s) a correct answer must cite,
in required order where order is the answer (temporal/conflict), plus an empty set +
`off_world_assertion` flag for unanswerable pairs -- computed in code from a fact the
pipeline already knows (a note's own `latent_facts` entry, a chronological order derived
from timestamps, or a contradiction pairing). The LLM's only job is to phrase a question
that evidence would answer; it never writes the key. A second, independent model
(gemma3:27b, config.VERIFIER_MODEL) checks that the pinned fact is actually supported by
its note before the pair is kept. Why: when one model writes the question, the
answer, AND the label in one call, nothing checks the answer against the notes, and
wrong keys get through (data/qa_pairs_v1_snapshot.json is a set made that way). Grading on note-IDs-in-order
tests retrieval and ordering, not answer phrasing -- that's a deliberate scope decision,
not a limitation: this corpus exists to test *which* note a system used, not how it
worded a sentence.

Five QA types with increasing difficulty:
  single_hop          — one note is sufficient
  multi_hop           — two or more notes required
  temporal_reasoning  — answer depends on event ordering
  conflict_resolution — two notes contradict each other
  unanswerable        — answer is not present in the notes

Input:  data/notes.json
Output: data/qa_pairs.json

Pipeline position:
  stage_04 → [stage_05]

Usage:
  python stage_05_qa_generation.py
"""

import json
import random
import re
import time
from collections import Counter, defaultdict
from enum import Enum

import config
from llm import call_llm, parse_json_response
from prompts import (
    STAGE_05_QUESTION_ONLY,
    STAGE_05_UNANSWERABLE_QUESTION,
    STAGE_05_FACT_CHECK,
    STAGE_05_BLIND_ANSWER_CHECK,
)


class QAType(Enum):
    SINGLE_HOP   = "single_hop"
    MULTI_HOP    = "multi_hop"
    TEMPORAL     = "temporal_reasoning"
    CONFLICT     = "conflict_resolution"
    UNANSWERABLE = "unanswerable"
    CURRENCY     = "belief_currency"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(label: str, key: str) -> dict:
    path = config.PATHS[key]
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found at '{path}'. Run the previous stage first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_qa_pairs(qa_pairs: list[dict]) -> None:
    path = config.PATHS["qa_pairs"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"qa_pairs": qa_pairs}, f, indent=2, ensure_ascii=False)
    print(f"Saved → {path}")


def _entity_key(entity) -> str:
    """Notes may store entities as plain ID strings or as dicts with an 'id' field."""
    return entity.get("id") if isinstance(entity, dict) else str(entity)


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace())


# ── Fact extraction ──────────────────────────────────────────────────────────
# stage_04's `latent_facts` field is itself LLM-written (per note, freeform) --
# it is a much smaller and more checkable surface than a whole re-derived answer,
# but it is not guaranteed to match the note's own prose (that's exactly what the
# verifier below is for). Entries come in two shapes seen in the real corpus:
# a plain string ("f_009: uses disposable cup → updated: skipping coffee today")
# or a dict ({"fact_id": "f_006", "transition": "owes money $850 → invoice sent"}).

def _fact_entries(note: dict) -> list[str]:
    out = []
    for f in note.get("latent_facts") or []:
        if isinstance(f, dict):
            fid = f.get("fact_id", "")
            if f.get("transition") or f.get("value"):
                body = f.get("transition") or f.get("value")
            elif "from" in f and "to" in f:
                body = f"{f['from']} → {f['to']}"
            else:
                body = json.dumps(f, ensure_ascii=False)
            out.append(f"{fid}: {body}" if fid else str(body))
        else:
            out.append(str(f))
    return out


def _is_informative(fact_text: str) -> bool:
    """'(no change)' / 'confirmed (no change)' entries restate a static fact rather
    than stating anything new -- not usable as a QA answer on their own."""
    return "no change" not in fact_text.lower()


def _informative_facts(note: dict) -> list[str]:
    return [f for f in _fact_entries(note) if _is_informative(f)]


def _humanize(text: str) -> str:
    """Some latent_facts entries are bare code-like slugs ('couch_stain_expanded',
    'scheduled_for_next_week') rather than prose -- turn underscores into spaces so
    the answer reads as a sentence fragment, not a variable name."""
    return text.replace("_", " ") if "_" in text and " " not in text else text


def _resolved_fact_statement(fact_text: str) -> str:
    """Extract the current/resolved state from a 'fact_id: subject → verb: new' style
    string, stripping the id prefix and change-verb so it reads as a plain statement.

    Some entries only reconfirm the subject with a bare verb ("→ confirmed", no detail
    after it) -- stripping the verb then leaves nothing, so fall back to the subject
    clause (before the arrow) rather than the raw unstripped fact_text, which used to
    leak the "f_010: ...→" id/arrow formatting straight into the answer.
    """
    text = fact_text.strip()
    text = re.sub(r"^[A-Za-z][\w]*:\s*", "", text, count=1)
    if "→" in text:
        subject, _, resolved = text.partition("→")
    elif "->" in text:
        subject, _, resolved = text.partition("->")
    else:
        subject, resolved = "", text
    resolved = re.sub(
        r"^(confirmed|updated|contradicted|activates?)\s*:?\s*", "", resolved.strip(), flags=re.IGNORECASE
    ).strip()
    return _humanize(resolved or subject.strip() or fact_text.strip())


def _topic_key(fact_text: str) -> str:
    """Groups two fact strings as 'the same evolving thing' if they share their
    leading clause (before the '→') -- used to pair near-duplicate facts for
    conflict/temporal seeds instead of pairing on entity alone, which can put
    two unrelated facts from the same note/arc side by side (see
    find_temporal_seeds)."""
    return _norm(fact_text.split("→")[0])[:40]


# ── Evidence finders ───────────────────────────────────────────────────────────
# Each finder returns a list of note-ID groups: the gold evidence for one QA
# pair, chosen BEFORE the question is written. v2: every finder now also requires
# the note(s) to carry the *specific fact* the answer will be pinned to, not just
# a topical/importance signal -- a seed with no checkable fact can't produce a
# checkable answer.

def find_single_hop_seeds(notes: list[dict]) -> list[list[str]]:
    """One note with an informative fact to pin the answer to.

    Replaces the old `importance >= 3` heuristic: importance measures salience,
    not whether there is an actual checkable fact to ask about -- a high-
    importance note with no informative `latent_facts` entry gave the old code
    nothing but the note's prose to build an answer from, which is exactly what
    let the LLM re-derive (and drift).
    """
    return [[n["note_id"]] for n in notes if _informative_facts(n)]


def find_multi_hop_seeds(notes: list[dict]) -> list[list[str]]:
    """Note pairs that share an entity, are not adjacent in time, and BOTH carry
    an informative fact -- each half of the answer is pinned to a real fact.
    """
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for note in sorted(notes, key=lambda n: n.get("timestamp", "")):
        if not _informative_facts(note):
            continue
        for entity in note.get("entities", []):
            by_entity[_entity_key(entity)].append(note)

    pairs = []
    for entity_notes in by_entity.values():
        for i in range(len(entity_notes) - 2):
            pairs.append([entity_notes[i]["note_id"], entity_notes[i + 2]["note_id"]])
    return pairs


def find_temporal_seeds(notes: list[dict]) -> list[list[str]]:
    """Three consecutive notes for the same arc — requires reconstructing the timeline.

    Deliberately left as the pre-existing arc-only grouping, NOT narrowed to a shared
    fact topic. A same-topic version was tried in this session (and did fix a real
    "temporal question built from two unrelated facts" failure seen live) but was
    reverted on request: this seed selector is an explicit do-not-touch boundary
    (narrowing it changes which cases are hard, which breaks comparability with prior
    Probe C runs). The topic-preference fallback in generate_qa_pair()'s TEMPORAL
    branch is the only mitigation for that failure mode now; see its comment.
    """
    by_arc: dict[str, list[dict]] = defaultdict(list)
    for note in sorted(notes, key=lambda n: n.get("timestamp", "")):
        arc = note.get("story_arc_id")
        if arc:
            by_arc[arc].append(note)

    return [
        [n["note_id"] for n in arc_notes[:3]]
        for arc_notes in by_arc.values()
        if len(arc_notes) >= 3
    ]


def find_conflict_seeds(notes: list[dict]) -> list[list[str]]:
    """Notes that share an entity and have differing latent_fact values.

    Deliberately left as the pre-existing permissive pairing (matches on entity +
    fact-id prefix only, no informativeness/differing-value filter), not the
    stricter version tried in this session. That stricter version fixed q_0018
    (a note whose only fact was an uninformative "no change" got paired anyway,
    and the LLM invented a contradiction that wasn't there) but was reverted on
    request since this repo's seed-selection functions are meant to stay as
    close to untouched as the brief allows. generate_qa_pair()'s CONFLICT branch
    now has an explicit empty-informative-facts guard so a seed like q_0018's
    still gets a clean discard instead of a bad answer or a raw crash.
    """
    entity_facts: dict[tuple, dict] = {}
    pairs = []

    for note in sorted(notes, key=lambda n: n.get("timestamp", "")):
        for entity in note.get("entities", []):
            entity_key = _entity_key(entity)
            for fact in note.get("latent_facts", []):
                key = (entity_key, str(fact)[:40])
                if key in entity_facts:
                    prev = entity_facts[key]
                    if prev["note_id"] != note["note_id"]:
                        pairs.append([prev["note_id"], note["note_id"]])
                else:
                    entity_facts[key] = {"note_id": note["note_id"]}
    return pairs


def find_currency_seeds(notes: list[dict]) -> list[list[str]]:
    """CONFLICT's own seed pairing (share an entity + fact-id-prefix match),
    narrowed to pairs whose two sides actually resolve to different
    statements -- a belief-currency question needs a belief that genuinely
    changed, not a seed that would just get discarded downstream for not
    differing (the same guard CONFLICT's own branch in generate_qa_pair()
    applies, done here up front so it's testable as one thing)."""
    notes_by_id = {n["note_id"]: n for n in notes}
    seeds = []
    for note_ids in find_conflict_seeds(notes):
        earlier, later = (notes_by_id[nid] for nid in note_ids)
        early_facts, later_facts = _informative_facts(earlier), _informative_facts(later)
        if not early_facts or not later_facts:
            continue
        f_early = early_facts[0]
        f_late = next((f for f in later_facts if _topic_key(f) == _topic_key(f_early)), later_facts[0])
        if _norm(_resolved_fact_statement(f_early)) != _norm(_resolved_fact_statement(f_late)):
            seeds.append(note_ids)
    return seeds


def find_unanswerable_seeds(notes: list[dict]) -> list[list[str]]:
    """Structural pre-filter only -- NOT the full defense. A note that hedges
    about something AND carries no informative latent fact is a plausible
    candidate for an unanswerable question. That is not sufficient on its own: a
    note can hedge about one thing while flatly stating another in prose that
    never made it into `latent_facts` -- confirmed on this corpus:
    n_202401101533 has zero latent_facts but its text states "five new
    followers" outright. Every candidate from here still goes through
    generate_qa_pair()'s mandatory blind Q&A check before being kept.
    """
    hedge_words = ("think", "maybe", "not sure", "might", "forgot", "can't remember")
    return [
        [n["note_id"]]
        for n in notes
        if any(word in n.get("text", "").lower() for word in hedge_words)
        and not _informative_facts(n)
    ]


SEED_FINDERS = {
    QAType.SINGLE_HOP:   find_single_hop_seeds,
    QAType.MULTI_HOP:    find_multi_hop_seeds,
    QAType.TEMPORAL:     find_temporal_seeds,
    QAType.CONFLICT:     find_conflict_seeds,
    QAType.UNANSWERABLE: find_unanswerable_seeds,
    QAType.CURRENCY:     find_currency_seeds,
}


# ── Verifier (independent model, narrow checks only) ────────────────────────────

def _call_verifier(prompt: str) -> str:
    import requests

    payload = {
        "model":  config.VERIFIER_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": -1},
    }
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = requests.post(
                config.OLLAMA_BASE_URL, json=payload, timeout=config.VERIFIER_TIMEOUT_SECONDS
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("done_reason") == "length":
                raise ValueError("verifier response truncated (done_reason=length)")
            return body.get("response", "").strip()
        except Exception as exc:
            if attempt < config.MAX_RETRIES:
                time.sleep(attempt * 2)
            else:
                raise RuntimeError(
                    f"Verifier ({config.VERIFIER_MODEL}) call failed after "
                    f"{config.MAX_RETRIES} attempts"
                ) from exc


def _fact_supported(note_text: str, fact_text: str) -> tuple[bool, str]:
    """Narrow check: does this ONE note actually support this ONE fact string?
    A much easier judging task than grading a whole free-form QA pair."""
    prompt = STAGE_05_FACT_CHECK.format(note_text=note_text, fact_text=fact_text)
    raw = _call_verifier(prompt)
    parsed = parse_json_response(raw)
    return bool(parsed.get("supported")), parsed.get("explanation", "")


def _blind_can_answer(question: str, notes_text: str) -> tuple[bool, str]:
    """Blind Q&A check for unanswerable candidates: never mentions the pair was
    constructed to be unanswerable, so the model isn't anchored toward
    confirming that label."""
    prompt = STAGE_05_BLIND_ANSWER_CHECK.format(question=question, notes_text=notes_text)
    raw = _call_verifier(prompt)
    parsed = parse_json_response(raw)
    return bool(parsed.get("can_answer")), parsed.get("explanation", "")


# ── Generation ────────────────────────────────────────────────────────────────

class Discarded(Exception):
    """Raised internally when a candidate pair fails a verifier check."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


TYPE_INSTRUCTIONS = {
    QAType.SINGLE_HOP: (
        "Write a direct question whose answer is the given fact."
    ),
    QAType.MULTI_HOP: (
        "Both given facts are required to answer the question -- write ONE question that "
        "cannot be answered from either fact alone, combining both."
    ),
    QAType.TEMPORAL: (
        "Two facts are given, in order: the EARLIER one and the LATER one, about the same "
        "evolving thing. Write a question that explicitly asks for a comparison across time "
        "-- e.g. what changed, or which came first -- NOT a question about only one of them."
    ),
    QAType.CONFLICT: (
        "Two facts are given, in order: an EARLIER state and a LATER, contradicting state of "
        "the same thing. Write a question that asks the reader to identify or resolve the "
        "contradiction between the two -- NOT a question about only one of them."
    ),
    QAType.CURRENCY: (
        "Write a plain, direct question about the CURRENT state of the given fact only -- "
        "e.g. what the status of X is now. Do NOT ask for a comparison across time, and do "
        "NOT reveal or hint that an earlier, different belief ever existed."
    ),
}


def _ask_question(qa_type: QAType, notes_text: str, given_facts: list[str]) -> str:
    prompt = STAGE_05_QUESTION_ONLY.format(
        qa_type=qa_type.value,
        notes_text=notes_text,
        given_facts="\n".join(f"- {f}" for f in given_facts),
        type_instruction=TYPE_INSTRUCTIONS.get(qa_type, ""),
    )
    raw = call_llm(prompt, stage="stage_05")
    return parse_json_response(raw)["question"]


def _notes_text(note_ids: list[str], notes_by_id: dict) -> str:
    return "\n\n".join(
        f"[{nid}] {notes_by_id[nid]['text']}" for nid in note_ids if nid in notes_by_id
    )


def generate_qa_pair(
    note_ids: list[str],
    notes_by_id: dict[str, dict],
    qa_type: QAType,
    index: int,
) -> dict:
    """Build one QA pair: answer pinned in code, question phrased by the LLM,
    fact(s) verified by an independent model. Raises Discarded if the pinned
    fact isn't actually supported by its note, or if an unanswerable candidate
    turns out to be answerable."""
    notes_text = _notes_text(note_ids, notes_by_id)
    if not notes_text.strip():
        raise Discarded("empty notes text")

    stale_distractor = None  # only CURRENCY sets this

    if qa_type is QAType.SINGLE_HOP:
        note = notes_by_id[note_ids[0]]
        fact = _informative_facts(note)[0]
        supported, why = _fact_supported(note["text"], fact)
        if not supported:
            raise Discarded(f"fact not supported by note: {why}")
        question = _ask_question(qa_type, notes_text, [fact])
        evidence, ordered = [note["note_id"]], False

    elif qa_type is QAType.MULTI_HOP:
        n1, n2 = (notes_by_id[nid] for nid in note_ids)
        f1, f2 = _informative_facts(n1)[0], _informative_facts(n2)[0]
        for note, fact in ((n1, f1), (n2, f2)):
            supported, why = _fact_supported(note["text"], fact)
            if not supported:
                raise Discarded(f"fact not supported by note {note['note_id']}: {why}")
        question = _ask_question(qa_type, notes_text, [f1, f2])
        evidence, ordered = [n1["note_id"], n2["note_id"]], False

    elif qa_type is QAType.TEMPORAL:
        group = sorted((notes_by_id[nid] for nid in note_ids), key=lambda n: n["timestamp"])
        fact_notes = [n for n in group if _informative_facts(n)]
        if len(fact_notes) < 2:
            raise Discarded("fewer than 2 notes with informative facts in temporal group")
        earlier, later = fact_notes[0], fact_notes[-1]
        f_early = _informative_facts(earlier)[0]
        # prefer a same-topic fact in `later` so the contrast is about one evolving
        # thing, not two unrelated facts that happen to share an arc (see
        # find_temporal_seeds); fall back to its first fact if no topic match.
        later_facts = _informative_facts(later)
        f_late = next((f for f in later_facts if _topic_key(f) == _topic_key(f_early)), later_facts[0])
        for note, fact in ((earlier, f_early), (later, f_late)):
            supported, why = _fact_supported(note["text"], fact)
            if not supported:
                raise Discarded(f"fact not supported by note {note['note_id']}: {why}")
        question = _ask_question(qa_type, notes_text, [f_early, f_late])
        evidence, ordered = [earlier["note_id"], later["note_id"]], True

    elif qa_type is QAType.CONFLICT:
        earlier, later = (notes_by_id[nid] for nid in note_ids)
        # note_ids already emitted (earlier, later) by find_conflict_seeds' timestamp-sorted scan
        early_facts, later_facts = _informative_facts(earlier), _informative_facts(later)
        # find_conflict_seeds is the permissive pre-existing version (entity + fact-id match
        # only) -- it does NOT guarantee either side has an informative fact, or that the two
        # sides differ. Guard explicitly instead of relying on an IndexError to fall through to
        # the generic except in main(): this is exactly the q_0018 shape (a note paired on a
        # fact-id whose only entry was an uninformative "no change").
        if not early_facts or not later_facts:
            raise Discarded("conflict seed has a side with no informative fact")
        f_early = early_facts[0]
        # prefer the topic-matched fact on the later side; fall back to [0] if no topic overlap
        # (the seed finder doesn't guarantee one -- see its docstring).
        f_late = next((f for f in later_facts if _topic_key(f) == _topic_key(f_early)), later_facts[0])
        if _norm(_resolved_fact_statement(f_early)) == _norm(_resolved_fact_statement(f_late)):
            raise Discarded("conflict seed's two sides don't actually differ (not a real contradiction)")
        for note, fact in ((earlier, f_early), (later, f_late)):
            supported, why = _fact_supported(note["text"], fact)
            if not supported:
                raise Discarded(f"fact not supported by note {note['note_id']}: {why}")
        question = _ask_question(qa_type, notes_text, [f_early, f_late])
        # order is the resolution rule itself, not just provenance: "later wins by
        # construction" IS the answer to a conflict question -- a system that cites
        # both notes but in the wrong order has picked the stale state as current.
        evidence, ordered = [earlier["note_id"], later["note_id"]], True

    elif qa_type is QAType.UNANSWERABLE:
        note = notes_by_id[note_ids[0]]
        prompt = STAGE_05_UNANSWERABLE_QUESTION.format(notes_text=notes_text)
        raw = call_llm(prompt, stage="stage_05")
        question = parse_json_response(raw)["question"]
        can_answer, why = _blind_can_answer(question, notes_text)
        if can_answer:
            raise Discarded(f"blind check answered it: {why}")
        # empty set: no note is correct evidence for a positive answer. off_world_assertion
        # is always False on a surviving pair -- True would mean the blind check found a
        # prose assertion answering the question (the q_0018 "free refill" shape), which
        # discards the pair above instead of shipping it with the flag set.
        evidence, ordered = [], False

    elif qa_type is QAType.CURRENCY:
        earlier, later = (notes_by_id[nid] for nid in note_ids)
        # find_currency_seeds already filtered to genuinely-differing pairs, but redo the
        # same fact selection + guard here rather than trust the seed alone -- same
        # defensive posture as CONFLICT's branch above (the seed finder is permissive by
        # design; this is the last line of defense before a bad pair ships).
        early_facts, later_facts = _informative_facts(earlier), _informative_facts(later)
        if not early_facts or not later_facts:
            raise Discarded("currency seed has a side with no informative fact")
        f_early = early_facts[0]
        f_late = next((f for f in later_facts if _topic_key(f) == _topic_key(f_early)), later_facts[0])
        if _norm(_resolved_fact_statement(f_early)) == _norm(_resolved_fact_statement(f_late)):
            raise Discarded("currency seed's two sides don't actually differ (not a real belief change)")
        supported, why = _fact_supported(later["text"], f_late)
        if not supported:
            raise Discarded(f"fact not supported by note {later['note_id']}: {why}")
        # Only the LATER fact goes to the question-writer -- unlike CONFLICT (given both
        # facts, asked to resolve a contradiction), a currency question must read as a
        # plain single-fact question about the current state and never surface that an
        # earlier, different belief existed.
        question = _ask_question(qa_type, notes_text, [f_late])
        # Correct answer is the later note ALONE (SINGLE_HOP's shape, not CONFLICT's
        # both-in-order requirement) -- citing the earlier note is a scored failure,
        # not an incomplete-but-partial-credit answer.
        evidence, ordered = [later["note_id"]], False
        stale_distractor = [earlier["note_id"]]

    else:
        raise ValueError(f"unhandled QAType: {qa_type}")

    answer_key = {
        "evidence":            evidence,   # note IDs; order is required/meaningful iff "ordered"
        "ordered":             ordered,
        "off_world_assertion": False,
    }
    if stale_distractor is not None:
        # CURRENCY only: note IDs whose citation the harness should score as a failure
        # (the stale belief), additive so no existing answer_key consumer breaks.
        answer_key["stale_distractor"] = stale_distractor

    return {
        "question_id":      f"q_{index:04d}",
        "question":          question,
        "reasoning_type":    qa_type.value,
        "answer_key":        answer_key,
        "supporting_notes":  note_ids,  # notes used to construct the question (provenance) --
                                         # NOT the graded key; for unanswerable this is the
                                         # source note, while answer_key.evidence is empty.
        "required_hops":     len(note_ids),
        "difficulty":        "easy" if len(note_ids) == 1 else "medium",
    }


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(qa_pairs: list[dict], discards: list[dict]) -> None:
    types = Counter(q.get("reasoning_type") for q in qa_pairs)
    hops  = Counter(q.get("required_hops") for q in qa_pairs)
    discard_types = Counter(d["qa_type"] for d in discards)

    print("\n── QA Generation Summary ────────────────────────────")
    print(f"  Generated : {len(qa_pairs)}   Discarded: {len(discards)}")
    print(f"\n  By type:")
    for t, c in sorted(types.items()):
        print(f"    {c:3d}x  {t}")
    print(f"\n  By required hops:")
    for h, c in sorted(hops.items()):
        print(f"    {c:3d}x  {h} hop(s)")
    if discards:
        print(f"\n  Discards by type:")
        for t, c in sorted(discard_types.items()):
            print(f"    {c:3d}x  {t}")
        print(f"\n  Discard reasons:")
        for d in discards:
            print(f"    [{d['qa_type']}] {d['note_ids']}: {d['reason']}")
    print("─────────────────────────────────────────────────────\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    notes_data  = load_json("Notes", "notes")
    notes       = notes_data.get("notes", [])
    notes_by_id = {n["note_id"]: n for n in notes}

    print(f"Loaded {len(notes)} notes.")

    qa_pairs  = []
    discards  = []
    attempted = Counter()
    index     = 0

    for qa_type, finder in SEED_FINDERS.items():
        seeds  = finder(notes)
        count  = config.QA_COUNT.get(qa_type.value, 3)
        random.shuffle(seeds)

        print(f"\n  [{qa_type.value}] {len(seeds)} seeds found, generating up to {min(count, len(seeds))}...")

        kept = 0
        for note_ids in seeds:
            if kept >= count:
                break
            attempted[qa_type.value] += 1
            print(f"    [{index+1:3d}] {note_ids}...", end=" ", flush=True)
            try:
                qa = generate_qa_pair(note_ids, notes_by_id, qa_type, index)
                qa_pairs.append(qa)
                kept += 1
                print("✓")
            except Discarded as exc:
                discards.append({"qa_type": qa_type.value, "note_ids": note_ids, "reason": exc.reason})
                print(f"✗ (discarded: {exc.reason})")
            except Exception as exc:
                discards.append({
                    "qa_type": qa_type.value, "note_ids": note_ids,
                    "reason": f"{type(exc).__name__}: {exc}",
                })
                print(f"✗ ({type(exc).__name__}: {exc})")
            index += 1

    save_qa_pairs(qa_pairs)
    print_summary(qa_pairs, discards)

    print("\n── Discard rate by type (attempted vs kept) ─────────")
    kept_counts = Counter(q["reasoning_type"] for q in qa_pairs)
    for t in QAType:
        a = attempted.get(t.value, 0)
        k = kept_counts.get(t.value, 0)
        rate = (a - k) / a if a else 0.0
        print(f"  {t.value:22s}  attempted={a:3d}  kept={k:3d}  discard_rate={rate:.1%}")
    print("─────────────────────────────────────────────────────\n")

    with open(config.PATHS["qa_pairs"].parent / "qa_gen_discards.json", "w", encoding="utf-8") as f:
        json.dump({"discards": discards, "attempted": dict(attempted)}, f, indent=2, ensure_ascii=False)
    print(f"Discard log → {config.PATHS['qa_pairs'].parent / 'qa_gen_discards.json'}")

    print("Stage 05 complete. Pipeline finished.")


if __name__ == "__main__":
    main()
