"""Per-note intent-verification — a contradiction
note must read as a belief revision, wired into generate_note's retry loop such
that a persistent quality miss keeps the note (with a warning) rather than
dropping it, while a structural break still drops as before."""
import config
import note_quality as nq
import stage_04_note_generation as s4


# ── pure checks ───────────────────────────────────────────────────────────────

def test_contradiction_lacks_transition():
    event = {"_contradiction_of": "E1"}
    restated = {"text": "went back to the gym, same as ever, all good."}
    revised = {"text": "i used to think the gym was worth it; now i feel differently."}
    assert nq.contradiction_lacks_transition(restated, event) is not None
    assert nq.contradiction_lacks_transition(revised, event) is None


def test_non_contradiction_event_never_flagged():
    event = {}  # no _contradiction_of
    assert nq.contradiction_lacks_transition({"text": "just a normal day."}, event) is None


def test_hedge_overuse():
    assert nq.hedge_overuse("all clear, nothing to note.") is None
    over = " ".join(["maybe"] * 7)
    assert nq.hedge_overuse(over) is not None


# ── retry-loop wiring ─────────────────────────────────────────────────────────

def _isolate(monkeypatch, note_factory, call_counter):
    """Reduce generate_note to the quality-retry path: structural/name/rendering
    checks are stubbed out so only note_quality drives the loop."""
    def fake_call_llm(prompt, stage=None):
        call_counter.append(1)
        return ""
    monkeypatch.setattr(s4, "call_llm", fake_call_llm)
    monkeypatch.setattr(s4, "parse_json_response", lambda raw: dict(note_factory()))
    monkeypatch.setattr(s4, "_broken_reason", lambda note: None)
    monkeypatch.setattr(s4, "_invented_names", lambda text, allowed: [])
    monkeypatch.setattr(s4, "_verify_renderings", lambda note, event: [])


def test_good_contradiction_note_returned_first_try(monkeypatch):
    calls = []
    _isolate(monkeypatch, lambda: {"text": "i used to think it mattered; now i feel it doesn't."}, calls)
    event = {"event_id": "E2", "_contradiction_of": "E1"}
    note = s4.generate_note(event, {"entities": []}, 0)
    assert note["text"].startswith("i used to think")
    assert len(calls) == 1


def test_weak_contradiction_note_retries_then_kept(monkeypatch):
    calls = []
    _isolate(monkeypatch, lambda: {"text": "back at the gym, business as usual."}, calls)
    event = {"event_id": "E2", "_contradiction_of": "E1"}
    note = s4.generate_note(event, {"entities": []}, 0)
    # Kept, not dropped — quality misses don't raise.
    assert note["text"] == "back at the gym, business as usual."
    # Retried the full budget looking for a better one.
    assert len(calls) == config.MAX_RETRIES


def test_structural_break_still_raises(monkeypatch):
    calls = []
    _isolate(monkeypatch, lambda: {"text": "whatever"}, calls)
    # Re-break the structural check the isolation stubbed out: this is the guard
    # that quality-keep didn't accidentally swallow the drop-on-break path.
    monkeypatch.setattr(s4, "_broken_reason", lambda note: "missing text")
    event = {"event_id": "E2"}
    try:
        s4.generate_note(event, {"entities": []}, 0)
        assert False, "expected RuntimeError on persistent structural break"
    except RuntimeError:
        pass
    assert len(calls) == config.MAX_RETRIES
