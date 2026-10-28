"""
Stage 04 — Note Generation
============================
Reads the repaired events from stage 03 and converts each event into
a realistic, human-like personal note. The LLM only handles surface
realization — the structure comes from the event, not the model.

Only the entities and arc relevant to each event are sent as context
(not the full world state), to keep prompts small and on-topic.

Input:  data/events_repaired.json
        data/world_state.json
Output: data/notes.json

Pipeline position:
  stage_03 → [stage_04] → stage_05

Usage:
  python stage_04_note_generation.py
"""

import json
import re
from collections import Counter

import config
from llm import call_llm, parse_json_response
from note_quality import note_quality_problem
from prompts import STAGE_04_NOTE_GENERATION


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(label: str, key: str) -> dict:
    path = config.PATHS[key]
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found at '{path}'. Run the previous stage first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_notes(notes: list[dict]) -> None:
    path = config.PATHS["notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"notes": notes}, f, indent=2, ensure_ascii=False)
    print(f"Saved → {path}")


def save_mutation_log(mutations: list[dict]) -> None:
    path = config.PATHS["mutation_log"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"mutations": mutations}, f, indent=2, ensure_ascii=False)
    print(f"Saved → {path}")


def _importance_label(value) -> str:
    """Convert numeric importance (1-5) to the low/medium/high label the schema expects."""
    try:
        v = int(value)
    except (ValueError, TypeError):
        return "medium"
    if v <= 2:
        return "low"
    if v == 3:
        return "medium"
    return "high"


REQUIRED_NOTE_KEYS = {
    "note_id", "timestamp", "note_type", "text", "entities",
    "tags", "latent_facts", "story_arc_id", "importance", "renderings",
    "phase_state",
}

# The corpus is one person's personal journal; note_type carried 7 spellings
# (personal / personal_note / "personal note" / journal / work / routine / None)
# that are pure drift — work/routine are the event's type leaking in. Collapse
# to one canonical value at write time (F4).
CANONICAL_NOTE_TYPE = "personal"

# Common capitalized tokens that are NOT invented character names — pronouns,
# days/months, interjections, common sentence-openers. Used by the F1 name scan
# to avoid false positives. Roster names + the user's name are added per-run.
# (Brands like "TikTok"/"MacBook" are excluded structurally — see below: only
# SIMPLE-capitalized tokens are candidates, so internal-caps brands never fire.)
_NAME_STOPWORDS = {
    "i", "i'm", "i'll", "i've", "i'd", "you", "your", "you're", "he", "she",
    "we", "they", "it", "me", "him", "her", "us", "them", "his", "our", "my",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun", "january",
    "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul",
    "aug", "sep", "sept", "oct", "nov", "dec", "ok", "okay", "yeah", "yes",
    "no", "nope", "maybe", "good", "great", "well", "still", "just", "now",
    "then", "today", "tomorrow", "yesterday", "tonight", "again", "anyway",
    "anyways", "honestly", "ugh", "meh", "the", "and", "but", "also", "though",
    "sure", "thanks", "thank", "god", "why", "what", "when", "where", "how",
    "who", "this", "that", "there", "here", "not", "guess", "feel", "felt",
    "tried", "trying", "sometimes", "everything", "nothing", "something",
    "morning", "afternoon", "evening", "night", "week", "weekend",
}
# A word regex over letters + apostrophes; we classify each token in code so we
# can require SIMPLE capitalization (Xxxx) and skip camelCase brands.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
_SIMPLE_CAP_RE = re.compile(r"^[A-Z][a-z]+$")


def _broken_reason(note: dict) -> str | None:
    """Return why a note is unusable, or None if it's well-formed."""
    missing = REQUIRED_NOTE_KEYS - note.keys()
    if missing:
        return f"missing keys: {missing}"
    if not note.get("text", "").strip():
        return "empty text"
    return None


def _canonical_note_type(_value=None) -> str:
    """F4: every note in this corpus is a personal journal note — one canonical value."""
    return CANONICAL_NOTE_TYPE


def _roster_name_tokens(world_state: dict) -> set:
    """Lowercase word tokens of every allowed proper name: entity names + the user."""
    tokens = set(_NAME_STOPWORDS)
    for e in world_state.get("entities", []):
        for w in re.findall(r"[a-z']+", e.get("name", "").lower()):
            if len(w) >= 2:
                tokens.add(w)
    for w in re.findall(r"[a-z']+", world_state.get("user_profile", {}).get("name", "").lower()):
        if len(w) >= 2:
            tokens.add(w)
    return tokens


def _invented_names(text: str, allowed_tokens: set) -> list:
    """F1: person-like proper names in the prose that aren't in the allowed set.

    Deliberately conservative to keep false positives near zero (a false flag
    would block an otherwise-clean corpus):
      - only SIMPLE-capitalized tokens (``Marcus``) are candidates; camelCase
        brands (``TikTok``, ``MacBook``) and ALLCAPS are never flagged, so
        realistic oblique product references survive;
      - sentence-initial words are skipped (they are ordinary words, not names);
      - a stopword list of common capitalized words (pronouns, days, openers) is
        excluded; roster + user-name tokens are in ``allowed_tokens``.
    The remaining tokens are invented proper names — the Marcus failure mode.
    """
    found = []
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        base = word[:-2] if word.endswith("'s") else word
        if not _SIMPLE_CAP_RE.match(base) or len(base) < 3:
            continue
        # sentence-initial? look back past whitespace/quotes/brackets
        j = m.start() - 1
        while j >= 0 and text[j] in " \t\"'(-–—[":
            j -= 1
        if j < 0 or text[j] in ".!?\n:":
            continue  # first word of a sentence — not treated as a name
        tok = base.lower()
        if tok not in allowed_tokens and tok not in _NAME_STOPWORDS and tok not in found:
            found.append(tok)
    return found


def _verify_renderings(note: dict, event: dict) -> list:
    """F2: return a complete, code-verified renderings manifest.

    One entry per event involved_entity. The LLM's `explicit: true` claims are
    trusted only after a verbatim string match of the surface form against the
    note text — unverifiable claims are demoted to `explicit: false`. The `as`
    wording of oblique references is taken from the LLM (not code-checkable).
    """
    text = note.get("text", "") or ""
    text_lc = text.lower()
    claimed = {r.get("entity_id"): r for r in note.get("renderings", [])
               if isinstance(r, dict)}
    out = []
    for eid in event.get("involved_entities", []):
        r = claimed.get(eid, {})
        surface = r.get("as")
        explicit = bool(r.get("explicit")) and isinstance(surface, str) \
            and surface.strip() != "" and surface.lower() in text_lc
        out.append({"entity_id": eid, "explicit": explicit,
                    "as": surface if isinstance(surface, str) and surface.strip() else None})
    return out


# ── Prompt construction ───────────────────────────────────────────────────────

def _revision_directive(event: dict, prior_notes_by_event_id: dict | None) -> str:
    """Return a revise-this-earlier-belief instruction, or "" when not applicable.

    When the event carries `_contradiction_of` (set deterministically by
    stage_02's restore_contradiction_links) and the referenced earlier note has
    already been generated, the note-writer is told to overturn that specific
    earlier stance rather than writing the contradiction blind.
    """
    ref_id = event.get("_contradiction_of")
    if not ref_id or not prior_notes_by_event_id:
        return ""
    prior = prior_notes_by_event_id.get(ref_id)
    prior_text = (prior or {}).get("text", "").strip()
    if not prior_text:
        return ""
    return (
        "\n\nREVISION DIRECTIVE — this note must REVISE or CONTRADICT a belief you "
        "expressed in an earlier note:\n"
        f"\"{prior_text}\"\n"
        "Write today's note as a later reflection on the same situation whose stance "
        "has shifted or been overturned — acknowledge the change, don't restate the "
        "earlier belief as if it still held."
    )


def _recent_arc_notes(arc_id: str | None, notes_by_event_id: dict, k: int) -> list[dict]:
    """The most recent k already-generated notes belonging to this arc.

    `notes_by_event_id` preserves insertion order, which already matches
    generation order (events are processed in global timestamp order, no
    reordering) -- so a plain filter + tail is correct without re-sorting by
    timestamp. k <= 0 always returns [] (the K=0 regression guard: no arc
    context notes means build_note_prompt's arc-context directive is empty,
    reproducing today's blind per-event prompt byte-for-byte).
    """
    if k <= 0 or not arc_id:
        return []
    arc_notes = [n for n in notes_by_event_id.values() if n.get("story_arc_id") == arc_id]
    return arc_notes[-k:]


def _arc_context_directive(recent_notes: list[dict], phase_state: dict | None) -> str:
    """Anti-repetition instruction generalizing `_revision_directive`'s
    "acknowledge the change, don't restate" framing from the one
    contradiction-referenced note to the arc's recent notes as a whole."""
    lines = [t for n in recent_notes if (t := (n.get("text") or "").strip())]
    if not lines:
        return ""
    state_line = ""
    if phase_state and any(phase_state.values()):
        state_line = (
            f"\nCurrent rolling state for this arc: stress={phase_state.get('stress')}, "
            f"focus={phase_state.get('focus')!r}, dominant_emotion={phase_state.get('dominant_emotion')!r}."
        )
    return (
        "\n\nARC CONTEXT — recent notes you already wrote for this same story arc "
        "(most recent last). Build on them: acknowledge what's already been said, "
        "don't restate it, and don't reuse the same phrasing or stock hedges you "
        "already used.\n" + "\n".join(f"- {t}" for t in lines) + state_line
    )


def _fact_topic(fact) -> str:
    """Best-effort short label for one latent_facts entry (string or dict
    shape), used only for the coarse rolling `focus` snapshot below -- NOT
    the QA pipeline's own fact parsing (stage_05_qa_generation.py's
    _fact_entries/_resolved_fact_statement are the source of truth there;
    this is a much rougher aggregate with no verifier check behind it)."""
    if isinstance(fact, dict):
        text = fact.get("transition") or fact.get("value") or json.dumps(fact, ensure_ascii=False)
    else:
        text = str(fact)
    text = re.sub(r"^[A-Za-z][\w]*:\s*", "", text.strip(), count=1)
    topic = re.split(r"→|->", text)[0].strip()
    return topic.replace("_", " ") if "_" in topic and " " not in topic else topic


def compute_phase_state(arc_affects: list[dict], arc_latent_facts: list) -> dict:
    """Roll an arc's events-so-far affect + notes-so-far latent_facts into a
    coarse snapshot: stress = mean intensity of negative-valence affect (0 if
    none), dominant_emotion = the most common affect.emotion so far, focus =
    the most recently mentioned fact's topic. Pure function -- same inputs
    always give the same {stress, focus, dominant_emotion}, no carried
    mutable state between calls.
    """
    negative = [a for a in arc_affects if isinstance(a, dict) and a.get("valence") == -1]
    stress = round(sum(a.get("intensity", 0) or 0 for a in negative) / len(negative)) if negative else 0

    emotions = [a.get("emotion") for a in arc_affects if isinstance(a, dict) and a.get("emotion")]
    dominant_emotion = Counter(emotions).most_common(1)[0][0] if emotions else ""

    focus = ""
    for fact in reversed(arc_latent_facts):
        topic = _fact_topic(fact)
        if topic:
            focus = topic
            break

    return {"stress": stress, "focus": focus, "dominant_emotion": dominant_emotion}


def _fact_id(fact) -> str:
    """Extract a latent_facts entry's fact_id (string 'f_009: ...' prefix or
    the dict shape's own 'fact_id' key), or '' if it doesn't carry one."""
    if isinstance(fact, dict):
        return fact.get("fact_id", "") or ""
    m = re.match(r"^([A-Za-z][\w]*):", str(fact).strip())
    return m.group(1) if m else ""


def mutation_log_entries(note: dict, event: dict, prior_notes_by_fact_id: dict) -> list[dict]:
    """S6: {op, fact_id, arc_id, from_note_id, to_note_id, timestamp} records
    for this note's latent_facts, relative to the arc's own prior notes.

    `prior_notes_by_fact_id` maps fact_id -> the most recent note (any arc)
    that carried it so far in generation order. A fact_id seen for the first
    time is ADD; seen again on an event carrying `_contradiction_of` is
    INVALIDATE (the deterministic contradiction mechanism revising a prior
    belief); seen again otherwise is UPDATE.
    """
    entries = []
    arc_id = note.get("story_arc_id", "")
    is_contradiction_event = bool(event.get("_contradiction_of"))
    for fact in note.get("latent_facts") or []:
        fid = _fact_id(fact)
        if not fid:
            continue
        prior_note = prior_notes_by_fact_id.get(fid)
        if prior_note is None:
            op, from_note_id = "ADD", None
        elif is_contradiction_event:
            op, from_note_id = "INVALIDATE", prior_note["note_id"]
        else:
            op, from_note_id = "UPDATE", prior_note["note_id"]
        entries.append({
            "op": op,
            "fact_id": fid,
            "arc_id": arc_id,
            "from_note_id": from_note_id,
            "to_note_id": note.get("note_id"),
            "timestamp": note.get("timestamp"),
        })
    return entries


def build_note_prompt(
    event: dict,
    world_state: dict,
    prior_notes_by_event_id: dict | None = None,
    arc_context_notes: list[dict] | None = None,
    phase_state: dict | None = None,
) -> str:
    """Inject only the entities and arc relevant to this event, not the full world state."""
    event_json = json.dumps(event, indent=2, ensure_ascii=False)

    relevant_entity_ids = set(event.get("involved_entities", []))
    relevant_entities = [
        e for e in world_state.get("entities", [])
        if e["id"] in relevant_entity_ids
    ]

    arc_id = event.get("story_arc_id")
    relevant_arcs = [
        a for a in world_state.get("story_arcs", [])
        if a["arc_id"] == arc_id
    ]

    slim_context = {"entities": relevant_entities, "story_arcs": relevant_arcs}
    context_json = json.dumps(slim_context, indent=2, ensure_ascii=False)

    revision = _revision_directive(event, prior_notes_by_event_id)
    arc_context = _arc_context_directive(arc_context_notes or [], phase_state)
    return f"Context:\n{context_json}\n\nEvent:\n{event_json}{revision}{arc_context}\n\n{STAGE_04_NOTE_GENERATION}"


# ── Generation ────────────────────────────────────────────────────────────────

def generate_note(
    event: dict,
    world_state: dict,
    index: int,
    prior_notes_by_event_id: dict | None = None,
    arc_context_notes: list[dict] | None = None,
    phase_state: dict | None = None,
) -> dict:
    """Generate one note from one event.

    Retries up to config.MAX_RETRIES times if the LLM returns a
    schema-incomplete note (e.g. leaks the prompt's slim_context back
    instead of generating a note, as seen with n_0062). Raises
    RuntimeError if every attempt stays broken — callers should drop
    the note rather than save it half-formed.

    `prior_notes_by_event_id` maps already-generated notes by their source
    event id, so a contradiction event can be told which earlier belief to
    revise (see _revision_directive). `arc_context_notes` (S3) and
    `phase_state` (S2) are this arc's recent-notes window and rolling
    snapshot, threaded into the prompt and persisted on the note.
    """
    prompt = build_note_prompt(
        event, world_state, prior_notes_by_event_id, arc_context_notes, phase_state
    )
    allowed = _roster_name_tokens(world_state)
    reason = None

    for attempt in range(1, config.MAX_RETRIES + 1):
        raw  = call_llm(prompt, stage="stage_04")
        note = parse_json_response(raw)

        if not note.get("note_id"):
            note["note_id"] = f"n_{index:04d}"
        if not note.get("timestamp"):
            note["timestamp"] = event.get("timestamp", "")
        if not note.get("story_arc_id"):
            note["story_arc_id"] = event.get("story_arc_id", "")
        if not note.get("importance"):
            note["importance"] = _importance_label(event.get("importance", 3))
        note["note_type"] = _canonical_note_type()          # F4: kill the drift
        note.setdefault("renderings", [])
        note["renderings"] = _verify_renderings(note, event)  # F2: code-verified

        note["source_event_id"] = event.get("event_id", "")
        note["phase_state"] = phase_state or {"stress": 0, "focus": "", "dominant_emotion": ""}

        reason = _broken_reason(note)
        # F1: reject notes that invent a proper name not in the roster (Marcus).
        if reason is None:
            invented = _invented_names(note.get("text", ""), allowed)
            if invented:
                reason = f"invented name(s): {invented}"

        # A structural break drops the note on persistent failure (below); a
        # quality miss only makes it weak, so retry for a better one but keep the
        # note rather than drop it if the miss survives every attempt.
        quality_reason = note_quality_problem(note, event) if reason is None else None

        if reason is None and quality_reason is None:
            return note

        if reason is None:  # quality miss only
            if attempt < config.MAX_RETRIES:
                print(f"⚠ weak note ({quality_reason}), retrying [{attempt}/{config.MAX_RETRIES}]...", end=" ", flush=True)
                continue
            print(f"⚠ keeping weak note ({quality_reason}) after {config.MAX_RETRIES} attempts", flush=True)
            return note

        if attempt < config.MAX_RETRIES:
            print(f"⚠ broken note ({reason}), retrying [{attempt}/{config.MAX_RETRIES}]...", end=" ", flush=True)

    raise RuntimeError(
        f"Note for event '{event.get('event_id', index)}' still broken "
        f"after {config.MAX_RETRIES} attempts: {reason}"
    )


# ── Validation ────────────────────────────────────────────────────────────────

def validate_notes(notes: list[dict]) -> list[str]:
    warnings = []
    seen_ids = set()

    for note in notes:
        nid = note.get("note_id", "?")

        if nid in seen_ids:
            warnings.append(f"Duplicate note_id: '{nid}'")
        seen_ids.add(nid)

        missing = REQUIRED_NOTE_KEYS - note.keys()
        if missing:
            warnings.append(f"Note '{nid}' missing keys: {missing}")

        if not note.get("text", "").strip():
            warnings.append(f"Note '{nid}' has empty text")

        imp = note.get("importance", "")
        if imp not in ("low", "medium", "high"):
            warnings.append(f"Note '{nid}' has unexpected importance value: '{imp}'")

    return warnings


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(notes: list[dict], failed: int) -> None:
    if not notes:
        print("No notes generated.")
        return

    type_counts: dict[str, int] = {}
    imp_counts:  dict[str, int] = {}
    for n in notes:
        t = n.get("note_type", "unknown")
        i = n.get("importance", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        imp_counts[i]  = imp_counts.get(i, 0) + 1

    print("\n── Note Generation Summary ──────────────────────────")
    print(f"  Notes generated : {len(notes)}")
    print(f"  Failed / skipped: {failed}")
    print(f"\n  By note type:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {count:3d}x  {t}")
    print(f"\n  By importance:")
    for i in ("high", "medium", "low", "unknown"):
        if i in imp_counts:
            print(f"    {imp_counts[i]:3d}x  {i}")
    sample = next((n for n in notes if n.get("text")), None)
    if sample:
        print(f"\n  Sample note:")
        print(f"    [{sample.get('note_id')}] {sample.get('timestamp', '')[:10]}")
        print(f"    \"{sample.get('text', '')[:120]}...\"")
    print("─────────────────────────────────────────────────────\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    events_data = load_json("Repaired events", "events_repaired")
    events      = events_data.get("events", [])
    world_state = load_json("World state", "world_state")

    print(f"Loaded {len(events)} repaired events. Generating notes...")

    notes  = []
    failed = 0
    notes_by_event_id: dict[str, dict] = {}
    mutation_log: list[dict] = []
    prior_notes_by_fact_id: dict[str, dict] = {}

    for i, event in enumerate(events):
        eid = event.get("event_id", f"index {i}")
        print(f"  [{i+1:3d}/{len(events)}] {eid}...", end=" ", flush=True)

        arc_id = event.get("story_arc_id")
        prior_arc_events = [e for e in events[:i] if e.get("story_arc_id") == arc_id]
        prior_arc_notes = [n for n in notes_by_event_id.values() if n.get("story_arc_id") == arc_id]
        arc_context_notes = _recent_arc_notes(arc_id, notes_by_event_id, config.ARC_CONTEXT_NOTES)
        phase_state = compute_phase_state(
            [e.get("affect") for e in prior_arc_events if e.get("affect")],
            [f for n in prior_arc_notes for f in (n.get("latent_facts") or [])],
        )

        try:
            note = generate_note(
                event, world_state, i, notes_by_event_id,
                arc_context_notes=arc_context_notes, phase_state=phase_state,
            )
            notes.append(note)
            mutation_log.extend(mutation_log_entries(note, event, prior_notes_by_fact_id))
            for fact in note.get("latent_facts") or []:
                fid = _fact_id(fact)
                if fid:
                    prior_notes_by_fact_id[fid] = note
            if event.get("event_id"):
                notes_by_event_id[event["event_id"]] = note
            print("✓")
        except Exception as exc:
            print(f"✗ ({type(exc).__name__}: {exc})")
            failed += 1

    warnings = validate_notes(notes)
    if warnings:
        print(f"\n⚠️  Validation warnings ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")
    else:
        print("✓  Validation passed")

    save_notes(notes)
    save_mutation_log(mutation_log)
    print_summary(notes, failed)
    print("Stage 04 complete. Next: python stage_05_qa_generation.py")


if __name__ == "__main__":
    main()