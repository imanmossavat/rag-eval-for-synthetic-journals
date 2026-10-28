"""CONTRADICTIONS_PER_ARC controls how many
contradiction skeletons get injected per unresolved arc; default 1 stays
byte-identical to the original single-contradiction behaviour."""
import random

import config
import stage_02_event_timeline as s2


class _StubValidator:
    def __init__(self, arc_ids):
        self._arc_ids = arc_ids

    def unresolved_arcs(self):
        return self._arc_ids


def _skeletons():
    return [
        {"event_id": "E1", "story_arc_id": "a_001", "timestamp": "2024-01-01T09:00:00",
         "primary_entity": "e_1", "involved_entities": ["e_1"]},
        {"event_id": "E2", "story_arc_id": "a_002", "timestamp": "2024-01-02T09:00:00",
         "primary_entity": "e_2", "involved_entities": ["e_2"]},
    ]


def test_default_one_per_arc_keeps_original_id(monkeypatch):
    monkeypatch.setattr(config, "CONTRADICTIONS_PER_ARC", 1)
    random.seed(0)
    out = s2._inject_contradictions(_skeletons(), None, _StubValidator(["a_001", "a_002"]))
    contra = [s for s in out if str(s["event_id"]).startswith("E_contra_")]
    assert len(contra) == 2
    ids = {s["event_id"] for s in contra}
    # Byte-identical to pre-change behaviour: no index suffix at the default.
    assert ids == {"E_contra_a_001", "E_contra_a_002"}
    assert all("_contradiction_of" in s for s in contra)


def test_multiple_per_arc_gets_unique_suffixed_ids(monkeypatch):
    monkeypatch.setattr(config, "CONTRADICTIONS_PER_ARC", 3)
    random.seed(0)
    out = s2._inject_contradictions(_skeletons(), None, _StubValidator(["a_001"]))
    contra = [s for s in out if str(s["event_id"]).startswith("E_contra_")]
    assert len(contra) == 3
    assert {s["event_id"] for s in contra} == {
        "E_contra_a_001_0", "E_contra_a_001_1", "E_contra_a_001_2",
    }
    # All revise the same earliest event of the arc.
    assert {s["_contradiction_of"] for s in contra} == {"E1"}


def test_arc_with_no_skeletons_is_skipped(monkeypatch):
    monkeypatch.setattr(config, "CONTRADICTIONS_PER_ARC", 2)
    random.seed(0)
    out = s2._inject_contradictions(_skeletons(), None, _StubValidator(["a_404"]))
    assert [s for s in out if str(s["event_id"]).startswith("E_contra_")] == []
