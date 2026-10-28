"""Per-note quality checks for stage_04 note generation (intent-verification).

Ports the belief-transition and hedge vocabulary from Bundle 17's
eval/rag/datasets/syn_v2_drift/checks.py — which validates a whole corpus — down
to single-note checks that stage_04's generate_note() retry loop can enforce as
each note is written. The point (REPORT_drift_framework_gaps.md, gap 4): when an
event is a contradiction, the note it produces should actually read as a belief
revision, not restate the earlier stance unchanged. Nothing checked that before.

The transition regex is the ported one, broadened with a few general cues so it
isn't tuned only to the syn_v2 rewrite's phrasing. Thresholds here (HEDGE_CAP_
PER_NOTE, and how strictly a contradiction must show transition language) are a
first cut — they can only be tuned honestly against a real regeneration run,
which this build deliberately does not do.
"""
import re

# Ported verbatim from checks.py.
HEDGE_PHRASES = ["maybe", "should've", "not sure", "don't know", "wonder if", "probably"]

# A single note over this many hedge phrases reads as mush regardless of corpus
# totals. checks.py's per-phrase corpus budget was 10; per-note total is stricter.
HEDGE_CAP_PER_NOTE = 6

# checks.py's BELIEF_TRANSITION_RE, plus general-purpose transition cues so a
# freshly generated (not rewrite-derived) note can still match.
BELIEF_TRANSITION_RE = re.compile(
    r"used to think|used to feel|now i (?:think|feel)|changed my mind"
    r"|no longer (?:feel|think)|too clean|landed different|not the same thing as before"
    r"|used to|no longer|these days|turns out|was wrong|thought i|not so sure anymore"
    r"|don't feel that way|looking back",
    re.IGNORECASE,
)


def hedge_overuse(text: str, cap: int = HEDGE_CAP_PER_NOTE) -> str | None:
    """One reason string if the note over-hedges, else None."""
    low = text.lower()
    total = sum(low.count(phrase) for phrase in HEDGE_PHRASES)
    if total > cap:
        return f"over-hedged: {total} hedge phrases in one note (cap {cap})"
    return None


def contradiction_lacks_transition(note: dict, event: dict) -> str | None:
    """A contradiction note must carry belief-transition language, else it likely
    restates the earlier stance instead of revising it. None for non-contradiction
    events (nothing to verify)."""
    if not event.get("_contradiction_of"):
        return None
    if BELIEF_TRANSITION_RE.search(note.get("text", "")):
        return None
    return "contradiction note has no belief-transition language (restates earlier stance?)"


def note_quality_problem(note: dict, event: dict) -> str | None:
    """One reason string if the note fails a per-note quality check, else None.

    Kept separate from stage_04's _broken_reason / _invented_names (which drop a
    note on persistent failure) because a quality miss makes a note *weak*, not
    unusable — the caller should retry to give the model another shot but keep the
    note rather than drop it if the miss persists.
    """
    return (
        contradiction_lacks_transition(note, event)
        or hedge_overuse(note.get("text", ""))
    )
