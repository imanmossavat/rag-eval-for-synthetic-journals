"""
generate.py — build a small, fully-known test corpus in three steps.

  1. world      A big model (the API by default) invents the HIDDEN FACTS of one
                fictional person's month: people, facts, things that change, habits,
                and things that are never mentioned. Code validates the structure.
  2. notes      Each fact becomes one short diary note (one LLM call per note).
                Code checks every note contains the fact's exact words and none of
                the words it must avoid. Filler notes pad the corpus.
  3. questions  Pure code. Every question, its answer, and the notes that prove it
                come straight from step 1 — nothing is guessed after the fact.

The key idea: the answer key exists BEFORE any text is written, so it never has to
be reverse-engineered (and verified) from text.

    .venv/bin/python demo/generate.py                   # all steps, API backend
    .venv/bin/python demo/generate.py --backend local   # no API key: local model
    .venv/bin/python demo/generate.py --step questions  # re-run one step

No API key? Write data/world.json yourself (or paste the prompt from `--step prompts`
into a Claude chat), then: --step plan, write data/note_texts.json, --step check,
--step questions. The checked-in data/ was made this way (written in a Claude Code session).
"""

import argparse
import datetime as dt
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import llm_clients as llm

DATA = Path(__file__).parent / "data"
START = dt.date(2026, 3, 2)
DAYS = 30

FILLER_TOPICS = [
    "the weather and what you wore", "something you cooked", "a TV series episode",
    "errands in town", "a podcast you listened to", "cleaning the flat", "a bad night's sleep",
    "groceries and prices", "a long walk alone", "a book chapter", "fixing something broken",
    "a train delay", "rearranging furniture", "a rainy evening in", "trying a new recipe",
    "doing laundry", "a slow work afternoon", "paying bills", "watering plants", "a museum visit alone",
]


def date_of(day: int) -> str:
    return (START + dt.timedelta(days=day - 1)).isoformat()


# ─────────────────────────────────────────────────────────────── step 1: world

_STR = {"type": "string"}
_INT = {"type": "integer"}


def _obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


WORLD_SCHEMA = _obj(
    narrator=_obj(name=_STR, city=_STR),
    people={"type": "array", "items": _obj(id=_STR, name=_STR, relation=_STR, intro_day=_INT)},
    facts={"type": "array", "items": _obj(id=_STR, subject=_STR, attribute=_STR, value=_STR, day=_INT)},
    changes={"type": "array", "items": _obj(
        id=_STR, attribute=_STR,
        history={"type": "array", "items": _obj(value=_STR, day=_INT)})},
    habits={"type": "array", "items": _obj(
        id=_STR, activity=_STR, keyword=_STR, days={"type": "array", "items": _INT})},
    never_mentioned={"type": "array", "items": _obj(subject=_STR, attribute=_STR)},
)

WORLD_PROMPT = """Design the HIDDEN FACTS behind a fictional person's 30-day diary (days 1-30).
This is test data for a memory benchmark: every fact becomes a question with a known answer,
so precision matters more than flair. Return JSON matching the schema.

- narrator: a first name and a city.
- people: exactly 4 people close to the narrator. id "P1".."P4". relation is ONE lowercase
  word, all different (e.g. sister, colleague, neighbour, roommate). name: a distinct first
  name. intro_day: 2-8 (the day the diary first introduces them).
- facts: exactly 8 stable facts. id "F1".."F8". subject is "ME" or a person id.
  attribute is a short noun phrase that reads naturally after "my" or "Lena's"
  (e.g. "dog's name", "favourite cafe", "car"). value: 1-3 words, distinctive (a proper
  noun or brand is ideal), never a common word. day: 3-28, and for a person it must be
  AFTER that person's intro_day.
  * At least 3 attributes must appear twice, for two different subjects (look-alike pairs,
    e.g. the narrator's "dog's name" and Lena's "dog's name").
  * At least 5 facts must be about people (not ME).
- changes: exactly 3 things about the narrator that change over the month. id "C1".."C3".
  attribute e.g. "workplace", "phone", "running shoes". history: values in order with strictly
  increasing days (2-29); one change has 3 values, the others 2. Values distinctive.
- habits: exactly 2 recurring activities. id "H1","H2". activity: base-form verb phrase
  ("go bouldering"). keyword: one distinctive lowercase word that names the activity
  ("bouldering"). days: H1 has 7 distinct days, H2 has 3 distinct days.
- never_mentioned: exactly 3 (subject, attribute) pairs about people (P1-P4) that are
  plausible questions but are NEVER stated. Prefer an attribute that someone else has in
  `facts` (e.g. ask about P2's "car" when the narrator has a car).

Hard rules: all values (facts and change histories) are different from each other and from
the city; no value contains a person's name; no keyword appears inside any value."""


def validate_world(w: dict) -> list[str]:
    errs = []
    people = {p["id"]: p for p in w["people"]}
    if len(people) != 4:
        errs.append("need exactly 4 people")
    rels = [p["relation"] for p in w["people"]]
    if len(set(rels)) != len(rels) or any(" " in r for r in rels):
        errs.append("relations must be distinct single words")
    for f in w["facts"]:
        if f["subject"] != "ME" and f["subject"] not in people:
            errs.append(f"{f['id']}: unknown subject {f['subject']}")
        elif f["subject"] != "ME" and f["day"] <= people[f["subject"]]["intro_day"]:
            errs.append(f"{f['id']}: day must be after {f['subject']}'s intro_day")
    attrs = [f["attribute"] for f in w["facts"]]
    if sum(1 for a in set(attrs) if attrs.count(a) >= 2) < 3:
        errs.append("need at least 3 look-alike attribute pairs in facts")
    if sum(1 for f in w["facts"] if f["subject"] != "ME") < 5:
        errs.append("need at least 5 facts about people")
    for c in w["changes"]:
        days = [h["day"] for h in c["history"]]
        if len(days) < 2 or days != sorted(set(days)):
            errs.append(f"{c['id']}: history needs 2+ values on strictly increasing days")
    if not any(len(c["history"]) >= 3 for c in w["changes"]):
        errs.append("one change needs 3 values")
    for h in w["habits"]:
        if len(set(h["days"])) != len(h["days"]):
            errs.append(f"{h['id']}: duplicate days")
    for n in w["never_mentioned"]:
        if n["subject"] not in people:
            errs.append(f"never_mentioned subject {n['subject']} is not a person")
    values = all_values(w)
    lowered = [v.lower() for v in values]
    if len(set(lowered)) != len(lowered):
        errs.append("values must all be different")
    for v in values:
        for p in w["people"]:
            if _has_word(v, p["name"]):
                errs.append(f"value '{v}' contains a person's name")
        for h in w["habits"]:
            if _has_word(v, h["keyword"]):
                errs.append(f"value '{v}' contains habit keyword '{h['keyword']}'")
    every_day = [f["day"] for f in w["facts"]] + [p["intro_day"] for p in w["people"]] + \
        [h_["day"] for c in w["changes"] for h_ in c["history"]] + [d for h in w["habits"] for d in h["days"]]
    if any(not 1 <= d <= DAYS for d in every_day):
        errs.append(f"all days must be within 1-{DAYS}")
    return errs


def all_values(w: dict) -> list[str]:
    return [f["value"] for f in w["facts"]] + [h["value"] for c in w["changes"] for h in c["history"]]


def make_world(backend: str) -> dict:
    prompt = WORLD_PROMPT
    for attempt in range(1, 4):
        world = llm.api_json(prompt, WORLD_SCHEMA) if backend == "api" else llm.local_json(prompt, WORLD_SCHEMA)
        errs = validate_world(world)
        if not errs:
            return world
        print(f"  world attempt {attempt} invalid: {errs}")
        prompt = WORLD_PROMPT + "\n\nYour previous attempt broke these rules, fix them:\n- " + "\n- ".join(errs)
    raise RuntimeError("could not produce a valid world in 3 attempts")


# ─────────────────────────────────────────────────────────────── step 2: notes

def _has_word(text: str, word: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(word.lower()) + r"(?![\w])", text.lower()) is not None


def plan_notes(w: dict, n_filler: int, seed: int = 7) -> list[dict]:
    """One planned note per hidden fact, plus filler. Each plan says what the note MUST
    contain and what it must NOT mention — that's what makes the answer key exact."""
    rng = random.Random(seed)
    people = {p["id"]: p for p in w["people"]}
    names = [p["name"] for p in w["people"]]
    relations = [p["relation"] for p in w["people"]]
    keywords = [h["keyword"] for h in w["habits"]]
    values = all_values(w)
    plans = []

    def add(kind, ref, day, statement, include, allowed=()):
        # Forbid every name/relation/value/keyword the note isn't explicitly about.
        forbidden = [x for x in names + relations + values + keywords
                     if x not in include and x not in allowed]
        plans.append({"kind": kind, "ref": ref, "day": day, "statement": statement,
                      "must_include": include, "must_exclude": forbidden})

    for p in w["people"]:
        add("intro", p["id"], p["intro_day"],
            f"Introduce my {p['relation']} {p['name']} naturally, through something we did together.",
            [p["name"], p["relation"]])
    for f in w["facts"]:
        if f["subject"] == "ME":
            add("fact", f["id"], f["day"], f"My {f['attribute']} is {f['value']}.", [f["value"]])
        else:
            p = people[f["subject"]]
            # The note names the person but NOT their relation: so "my sister's X"
            # needs the intro note too. That's what makes the two-hop question two hops.
            add("fact", f["id"], f["day"], f"{p['name']}'s {f['attribute']} is {f['value']}.",
                [p["name"], f["value"]])
    for c in w["changes"]:
        for i, h in enumerate(c["history"]):
            text = (f"My {c['attribute']} is {h['value']}." if i == 0 else
                    f"My {c['attribute']} has changed: it is now {h['value']}. "
                    f"Do not name what it was before.")
            add("change", f"{c['id']}#{i}", h["day"], text, [h["value"]])
    for h in w["habits"]:
        for d in h["days"]:
            add("habit", h["id"], d, f"Today I did this: {h['activity']}.", [h["keyword"]])
    for _ in range(n_filler):
        add("filler", None, rng.randint(1, DAYS),
            f"Nothing special happened. Write about: {rng.choice(FILLER_TOPICS)}. No other people by name.", [])

    rng.shuffle(plans)
    plans.sort(key=lambda p: p["day"])  # stable within a day after the shuffle
    for i, p in enumerate(plans, 1):
        p["id"] = f"N{i:03d}"
        p["date"] = date_of(p["day"])
    return plans


NOTE_SCHEMA = _obj(text=_STR)


def note_prompt(w: dict, plan: dict) -> str:
    n = w["narrator"]
    include = ", ".join(f'"{x}"' for x in plan["must_include"]) or "(nothing specific)"
    exclude = ", ".join(f'"{x}"' for x in plan["must_exclude"])
    return f"""Write one private diary entry dated {plan['date']} by {n['name']}, who lives in {n['city']}.
First person, casual, 50-110 words, concrete everyday detail, no title, no date line.

The entry must convey exactly this: {plan['statement']}
It must contain these exact words: {include}
It must NOT contain any of these words: {exclude}
Do not mention any other people by name. Do not invent other facts about named people.
Return JSON: {{"text": "..."}}"""


def check_note(text: str, plan: dict) -> list[str]:
    errs = [f"missing '{x}'" for x in plan["must_include"] if x.lower() not in text.lower()]
    errs += [f"contains forbidden '{x}'" for x in plan["must_exclude"] if _has_word(text, x)]
    return errs


def render_note(w: dict, plan: dict, backend: str) -> dict:
    prompt = note_prompt(w, plan)
    for attempt in range(1, 5):
        out = (llm.api_json(prompt, NOTE_SCHEMA, effort="low") if backend == "api"
               else llm.local_json(prompt, NOTE_SCHEMA))
        errs = check_note(out["text"], plan)
        if not errs:
            return {"id": plan["id"], "date": plan["date"], "text": out["text"].strip(),
                    "kind": plan["kind"], "ref": plan["ref"]}
        prompt = note_prompt(w, plan) + "\n\nA previous draft failed these checks: " + "; ".join(errs)
    raise RuntimeError(f"{plan['id']} ({plan['kind']} {plan['ref']}) failed checks 4 times: {errs}")


def make_notes(w: dict, backend: str, n_filler: int) -> list[dict]:
    plans = plan_notes(w, n_filler)
    workers = 8 if backend == "api" else 1
    with ThreadPoolExecutor(workers) as pool:
        notes = list(pool.map(lambda p: render_note(w, p, backend), plans))
    return notes


# ─────────────────────────────────────────────────────────────── step 3: questions

def _possessive(subject: str, people: dict) -> str:
    return "my" if subject == "ME" else f"{people[subject]['name']}'s"


def make_questions(w: dict, notes: list[dict]) -> list[dict]:
    people = {p["id"]: p for p in w["people"]}
    by_ref: dict = {}
    for n in notes:
        by_ref.setdefault(n["ref"], []).append(n["id"])
    qs = []

    def q(level, qtype, question, answer, gold, distractors=(), conjunct=False):
        qs.append({"id": f"Q{len(qs) + 1:02d}", "level": level, "type": qtype,
                   "question": question, "answer": answer, "conjunct": conjunct,
                   "gold_notes": gold, "distractor_values": list(distractors),
                   "answerable": bool(answer)})

    def lookalikes(f):
        return [g["value"] for g in w["facts"] if g["attribute"] == f["attribute"] and g["id"] != f["id"]]

    for f in w["facts"]:
        q(1, "single_fact", f"What is {_possessive(f['subject'], people)} {f['attribute']}?",
          [f["value"]], by_ref[f["id"]], lookalikes(f))
    for c in w["changes"]:
        hist = c["history"]
        ids = [by_ref[f"{c['id']}#{i}"][0] for i in range(len(hist))]
        others = [h["value"] for h in hist[:-1]]
        plural = c["attribute"].endswith("s")
        q(2, "current_state", f"What {'are' if plural else 'is'} my {c['attribute']} now?",
          [hist[-1]["value"]], [ids[-1]], others)
        q(3, "previous_state", f"What {'were' if plural else 'was'} my {c['attribute']} before {hist[-1]['value']}?",
          [hist[-2]["value"]], ids[-2:], [h["value"] for i, h in enumerate(hist) if i != len(hist) - 2])
    for f in w["facts"]:
        if f["subject"] != "ME":
            p = people[f["subject"]]
            q(3, "two_hop", f"What is my {p['relation']}'s {f['attribute']}?",
              [f["value"]], by_ref[p["id"]] + by_ref[f["id"]], lookalikes(f))
    for h in w["habits"]:
        q(4, "count", f"How many times did I {h['activity']} this month?",
          [str(len(h["days"]))], by_ref[h["id"]])
    for c in w["changes"]:
        if len(c["history"]) >= 3:
            q(4, "history", f"List every {c['attribute']} I have had this month, in order.",
              [h["value"] for h in c["history"]],
              [by_ref[f"{c['id']}#{i}"][0] for i in range(len(c["history"]))], conjunct=True)
    for n in w["never_mentioned"]:
        same_attr = [f["value"] for f in w["facts"] if f["attribute"] == n["attribute"]]
        q(5, "unanswerable", f"What is {people[n['subject']]['name']}'s {n['attribute']}?",
          [], [], same_attr)
    return qs


# ─────────────────────────────────────────────────────────────── main

def _load(name):
    return json.loads((DATA / name).read_text())


def _save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    print(f"  wrote data/{name}")


CHAT_NOTES_PROMPT = """Below is a JSON list of planned diary notes for a fictional person ({name}, lives in {city}).
For EACH plan write one private diary entry: first person, casual, 50-110 words, concrete
everyday detail, no title, no date line. The entry must convey the plan's "statement", must
contain every string in "must_include" exactly, and must not contain ANY word in
"must_exclude". Do not mention any other people by name.
Return only JSON: an object mapping each plan "id" to its text, e.g. {{"N001": "...", ...}}.

{plans}"""


def write_chat_prompts(w: dict | None) -> None:
    """For people without API access: prompts to paste into a Claude chat. Paste the
    world prompt, save the reply as data/world.json, run `--step plan`, then run this
    again to get the notes prompt; save that reply as data/note_texts.json, run `--step check`."""
    parts = ["# Prompts to paste into a Claude chat\n",
             "## 1. World (save the JSON reply as `data/world.json`)\n",
             WORLD_PROMPT, "\n\nJSON schema:\n```json\n" + json.dumps(WORLD_SCHEMA, indent=1) + "\n```\n"]
    plan_path = DATA / "notes_plan.json"
    if w and plan_path.exists():
        plans = [{k: p[k] for k in ("id", "date", "statement", "must_include", "must_exclude")}
                 for p in _load("notes_plan.json")]
        parts += ["\n## 2. Notes (save the JSON reply as `data/note_texts.json`)\n",
                  "Long list: if the reply gets cut off, paste the plans in chunks of ~20.\n\n",
                  CHAT_NOTES_PROMPT.format(name=w["narrator"]["name"], city=w["narrator"]["city"],
                                           plans=json.dumps(plans, indent=1, ensure_ascii=False))]
    (DATA / "chat_prompts.md").write_text("".join(parts))
    print("  wrote data/chat_prompts.md")


def check_texts(texts: dict) -> list[dict]:
    """Validate hand-written / chat-written note texts against the plan."""
    notes, failures = [], []
    for p in _load("notes_plan.json"):
        text = texts.get(p["id"], "")
        errs = check_note(text, p) if text else ["no text"]
        if errs:
            failures.append(f"{p['id']} ({p['kind']} {p['ref']}): {'; '.join(errs)}")
        notes.append({"id": p["id"], "date": p["date"], "text": text.strip(),
                      "kind": p["kind"], "ref": p["ref"]})
    if failures:
        raise SystemExit("note checks failed:\n  " + "\n  ".join(failures))
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["api", "local"], default="api")
    ap.add_argument("--step", default="all",
                    choices=["all", "world", "plan", "notes", "check", "questions", "prompts"],
                    help="all = world+notes+questions by LLM. Without an API: write world.json "
                         "(by hand or via `prompts`), then plan -> write note_texts.json -> check -> questions")
    ap.add_argument("--filler", type=int, default=30, help="number of filler notes (the haystack)")
    args = ap.parse_args()

    if args.step in ("all", "world"):
        print("step 1: world")
        _save("world.json", make_world(args.backend))
    if args.step == "prompts":
        write_chat_prompts(_load("world.json") if (DATA / "world.json").exists() else None)
    if args.step == "plan":
        w = _load("world.json")
        errs = validate_world(w)
        if errs:
            raise SystemExit("world.json is invalid:\n  " + "\n  ".join(errs))
        _save("notes_plan.json", plan_notes(w, args.filler))
    if args.step in ("all", "notes"):
        print("step 2: notes")
        _save("notes.json", make_notes(_load("world.json"), args.backend, args.filler))
    if args.step == "check":
        _save("notes.json", check_texts(_load("note_texts.json")))
    if args.step in ("all", "questions"):
        print("step 3: questions")
        qs = make_questions(_load("world.json"), _load("notes.json"))
        _save("questions.json", qs)
        for t in sorted({(x["level"], x["type"]) for x in qs}):
            print(f"    L{t[0]} {t[1]:<15} {sum(1 for x in qs if x['type'] == t[1])}")


if __name__ == "__main__":
    main()
