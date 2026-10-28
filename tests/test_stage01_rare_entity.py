"""Piece 5 (Bundle 21, item B2): RARE_ENTITY_COUNT adds a distinctive-names
directive to the stage_01 prompt; default 0 leaves the prompt unchanged."""
import config
import stage_01_world_state as s1
from prompts import STAGE_01_WORLD_STATE


def _baseline_prompt():
    return (
        STAGE_01_WORLD_STATE
        .replace("<<MIN_ENTITIES>>", str(config.MIN_ENTITIES))
        .replace("<<MAX_ENTITIES>>", str(config.MAX_ENTITIES))
        .replace("<<MIN_STORY_ARCS>>", str(config.MIN_STORY_ARCS))
    )


def test_default_zero_leaves_prompt_unchanged(monkeypatch):
    monkeypatch.setattr(config, "RARE_ENTITY_COUNT", 0)
    prompt = s1.build_prompt()
    assert "ADDITIONAL REQUIREMENT" not in prompt
    assert prompt == _baseline_prompt()


def test_positive_count_adds_rare_name_directive(monkeypatch):
    monkeypatch.setattr(config, "RARE_ENTITY_COUNT", 4)
    prompt = s1.build_prompt()
    assert "ADDITIONAL REQUIREMENT" in prompt
    assert "4" in prompt
    assert "RARE" in prompt
    # Guard: it's strictly the baseline plus the directive, nothing else moved.
    assert prompt.startswith(_baseline_prompt())
