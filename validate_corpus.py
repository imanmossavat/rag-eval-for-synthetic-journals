"""validate_corpus.py — hard invariants for the generated journal corpus.

Run after any generation; exits non-zero on hard failures. This checks the
F1–F4 GENERATOR invariants (below), the ones that made the note-rendering stage
a lossy/inventive renderer of the structured truth (see
tag-mvp/eval/results/extraction.md and observation.md). It deliberately does
NOT re-check gold integrity (entity/arc counts, timestamp monotonicity, gold
recall gaps) — that is tag-mvp/eval/synthetic_gold_check.py's job. Run that
separately, or pass --gold-check PATH to shell out to it at the end.

Invariants:
  F1  no note prose contains an invented proper name outside the world roster
      (+ the user's own name). The Marcus check — reuses stage_04's exact
      _invented_names / _roster_name_tokens so the validator and the generator
      enforce the SAME rule.
  F2  every event's involved_entity has a renderings entry in its note, and
      every rendering claiming explicit:true has its surface form appear
      verbatim in the note text (a lying manifest is a hard failure).
  F3  every event carries a well-formed affect
      {emotion:str, valence in {-1,0,1}, intensity in {0,1,2,3}}.
  F4  one canonical note schema: note_type == CANONICAL_NOTE_TYPE for all
      notes, all REQUIRED_NOTE_KEYS present, no duplicate note_ids; and all
      cross-file ids resolve (note.source_event_id -> events,
      qa.supporting_notes -> notes, event.involved_entities -> world roster).

Usage:
    python validate_corpus.py
    python validate_corpus.py --data-dir /path/to/data
    python validate_corpus.py --gold-check /path/to/tag-mvp/eval/synthetic_gold_check.py
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import config
from stage_04_note_generation import (
    CANONICAL_NOTE_TYPE, REQUIRED_NOTE_KEYS,
    _roster_name_tokens, _invented_names,
)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _as_list(obj, key):
    if isinstance(obj, dict):
        return obj.get(key, [])
    return obj


def _span_days(notes):
    """Realized calendar span of a note set, in days, or None if < 2 timestamps."""
    parsed = []
    for n in notes:
        t = n.get("timestamp")
        try:
            parsed.append(datetime.fromisoformat(t))
        except (ValueError, TypeError):
            continue
    if len(parsed) < 2:
        return None
    return (max(parsed) - min(parsed)).total_seconds() / 86400.0


def _span_warning(notes, configured_days, tolerance_frac=0.5):
    """N12: DURATION_DAYS is an event-count product, not a span bound, so the
    realized timeline can be far shorter than the configured number (measured 21
    vs 90). Return a warning when they disagree by more than tolerance, else None,
    so the mismatch stops being silent."""
    realized = _span_days(notes)
    if realized is None:
        return None
    lo = configured_days * (1 - tolerance_frac)
    hi = configured_days * (1 + tolerance_frac)
    if lo <= realized <= hi:
        return None
    return (f"corpus span {realized:.1f} days is far from configured "
            f"DURATION_DAYS={configured_days} (N12: DURATION_DAYS is an event "
            f"count, not a span bound)")


def validate(data_dir):
    world = _load(os.path.join(data_dir, "world_state.json"))
    events = _as_list(_load(os.path.join(data_dir, "events_repaired.json")), "events")
    notes = _as_list(_load(os.path.join(data_dir, "notes.json")), "notes")
    qa_path = os.path.join(data_dir, "qa_pairs.json")
    qa = _as_list(_load(qa_path), "qa_pairs") if os.path.exists(qa_path) else []

    ev_by_id = {e.get("event_id"): e for e in events}
    note_ids = {n.get("note_id") for n in notes}
    roster_ids = {e.get("id") for e in world.get("entities", [])}
    allowed_tokens = _roster_name_tokens(world)

    fails = []   # hard failures -> non-zero exit
    warns = []   # soft signals

    span_warn = _span_warning(notes, config.DURATION_DAYS)
    if span_warn:
        warns.append("[N12] " + span_warn)

    # ── F1: invented proper names in note prose ──────────────────────────────
    f1_hits = 0
    for n in notes:
        invented = _invented_names(n.get("text", "") or "", allowed_tokens)
        if invented:
            f1_hits += 1
            fails.append(f"[F1] note {n.get('note_id')}: invented name(s) not in "
                         f"roster: {invented}")

    # ── F2: renderings manifest complete + explicit claims verified ──────────
    for n in notes:
        e = ev_by_id.get(n.get("source_event_id"))
        if e is None:
            continue  # cross-file failure caught in F4
        text_lc = (n.get("text", "") or "").lower()
        rends = {r.get("entity_id"): r for r in n.get("renderings", [])
                 if isinstance(r, dict)}
        for eid in e.get("involved_entities", []):
            if eid not in rends:
                fails.append(f"[F2] note {n.get('note_id')}: involved_entity "
                             f"{eid} missing from renderings")
                continue
            r = rends[eid]
            if r.get("explicit"):
                surface = r.get("as")
                if not (isinstance(surface, str) and surface.lower() in text_lc):
                    fails.append(f"[F2] note {n.get('note_id')}: explicit:true for "
                                 f"{eid} but surface {surface!r} not in text")
    # health: oblique reference must still occur (F2 must not force all explicit)
    all_rends = [r for n in notes for r in n.get("renderings", []) if isinstance(r, dict)]
    n_explicit = sum(1 for r in all_rends if r.get("explicit"))
    n_implicit = len(all_rends) - n_explicit
    if all_rends and n_implicit == 0:
        fails.append("[F2] no implicit renderings anywhere — oblique reference was "
                     "flattened; the fix over-corrected.")

    # ── F3: well-formed affect on every event ────────────────────────────────
    for e in events:
        a = e.get("affect")
        if not isinstance(a, dict) or not isinstance(a.get("emotion"), str) \
                or not a.get("emotion", "").strip():
            fails.append(f"[F3] event {e.get('event_id')}: affect missing/malformed: {a}")
            continue
        if a.get("valence") not in (-1, 0, 1):
            fails.append(f"[F3] event {e.get('event_id')}: affect.valence out of range: {a.get('valence')}")
        if a.get("intensity") not in (0, 1, 2, 3):
            fails.append(f"[F3] event {e.get('event_id')}: affect.intensity out of range: {a.get('intensity')}")

    # ── F4: canonical note schema + cross-file id resolution ─────────────────
    seen = set()
    for n in notes:
        nid = n.get("note_id")
        if nid in seen:
            fails.append(f"[F4] duplicate note_id: {nid}")
        seen.add(nid)
        missing = REQUIRED_NOTE_KEYS - n.keys()
        if missing:
            fails.append(f"[F4] note {nid}: missing keys {missing}")
        if n.get("note_type") != CANONICAL_NOTE_TYPE:
            fails.append(f"[F4] note {nid}: note_type {n.get('note_type')!r} != "
                         f"canonical {CANONICAL_NOTE_TYPE!r}")
        sid = n.get("source_event_id")
        if sid not in ev_by_id:
            fails.append(f"[F4] note {nid}: source_event_id {sid!r} does not resolve")
        ps = n.get("phase_state")
        if not isinstance(ps, dict) or not isinstance(ps.get("stress"), int) \
                or not isinstance(ps.get("focus"), str) \
                or not isinstance(ps.get("dominant_emotion"), str):
            fails.append(f"[F4] note {nid}: phase_state missing/malformed: {ps!r}")
    for e in events:
        for eid in e.get("involved_entities", []):
            if eid not in roster_ids:
                fails.append(f"[F4] event {e.get('event_id')}: involved_entity "
                             f"{eid!r} not in world roster")
    for q in qa:
        for sid in q.get("supporting_notes", []):
            if sid not in note_ids:
                fails.append(f"[F4] qa {q.get('question_id')}: supporting_note "
                             f"{sid!r} does not resolve")

    return fails, warns, {
        "notes": len(notes), "events": len(events), "qa": len(qa),
        "f1_invented_notes": f1_hits,
        "renderings_explicit": n_explicit, "renderings_implicit": n_implicit,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_dir = str(config.PATHS["notes"].parent)
    ap.add_argument("--data-dir", default=default_dir)
    ap.add_argument("--gold-check", default=None,
                    help="path to tag-mvp/eval/synthetic_gold_check.py to run after")
    args = ap.parse_args()

    fails, warns, stats = validate(args.data_dir)

    print("=" * 66)
    print(f"validate_corpus.py — {args.data_dir}")
    print("=" * 66)
    print(f"notes={stats['notes']} events={stats['events']} qa={stats['qa']}")
    print(f"F1 notes with invented names: {stats['f1_invented_notes']}")
    print(f"F2 renderings: {stats['renderings_explicit']} explicit / "
          f"{stats['renderings_implicit']} implicit (oblique)")
    for w in warns:
        print("  ! " + w)
    if fails:
        print(f"\n✗ {len(fails)} HARD FAILURE(S):")
        for f in fails[:60]:
            print("   " + f)
        if len(fails) > 60:
            print(f"   … and {len(fails) - 60} more")
    else:
        print("\n✓ all F1–F4 invariants hold")

    if args.gold_check:
        print("\n-- delegating gold-integrity to synthetic_gold_check.py --")
        rc = subprocess.call([sys.executable, args.gold_check])
        if rc != 0:
            fails.append(f"[gold] synthetic_gold_check.py exited {rc}")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
