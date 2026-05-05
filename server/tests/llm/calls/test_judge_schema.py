"""Verb-grammar schema + semantic check 회귀 테스트.

Stage 1 redesign 후 17-action schema 테스트는 verb 표기로 이전:
- Schema 단위 (Verb / RefuseReason / JudgeOutput): test_classify_verb_schema.py
- Modifier whitelist: test_classify_modifier_schemas.py
- validate_judge_output: test_classify_validate_judge_output.py
- Semantic check: test_classify_semantics_verb.py + 본 파일

본 파일은 attack target / pass corpse / roll target 같은 surroundings-driven
semantic 회귀를 verb 모델로 cover."""

import pytest

from src.llm.calls.classify.schema import JudgeOutput, RefuseReason, Verb
from src.llm.calls.classify.semantics import (
    JudgeSemanticError,
    _surroundings_target_ids,
    check_semantics,
)


def _attack(target_id: str) -> JudgeOutput:
    return JudgeOutput(actions=[Verb(name="attack", target_ids=[target_id])])


def _ents(*entries):
    return {"entities": list(entries)}


def test_attack_passes_when_target_is_npc():
    s = _ents({"id": "n1", "type": "npc", "friendly": False})
    s["location"] = {"id": "loc_01"}
    check_semantics(_attack("n1"), s)


def test_attack_rejects_hallucinated_target():
    s = _ents({"id": "n1", "type": "npc", "friendly": False})
    s["location"] = {"id": "loc_01"}
    with pytest.raises(JudgeSemanticError, match="not in surroundings"):
        check_semantics(_attack("ghost"), s)


def test_attack_rejects_friendly_npc():
    s = _ents({"id": "n1", "type": "npc", "friendly": True})
    s["location"] = {"id": "loc_01"}
    with pytest.raises(JudgeSemanticError, match="friendly"):
        check_semantics(_attack("n1"), s)


def test_attack_rejects_location_as_target():
    s = _ents()
    s["location"] = {"id": "loc_01"}
    with pytest.raises(JudgeSemanticError, match="not an NPC"):
        check_semantics(_attack("loc_01"), s)


def test_attack_rejects_item_as_target():
    s = _ents({"id": "item_01", "type": "item"})
    s["location"] = {"id": "loc_01"}
    with pytest.raises(JudgeSemanticError, match="not an NPC|NPCs valid"):
        check_semantics(_attack("item_01"), s)


def test_attack_accepts_neutral_npc():
    s = _ents({"id": "n1", "type": "npc"})  # friendly absent → neutral
    s["location"] = {"id": "loc_01"}
    check_semantics(_attack("n1"), s)


def test_refuse_skips_check():
    output = JudgeOutput(refuse=RefuseReason(category="out_of_game", message_hint="x"))
    check_semantics(output, _ents())


def test_surroundings_target_ids_includes_corpses_when_requested():
    s = {
        "location": {"id": "loc"},
        "entities": [{"id": "n1"}],
        "corpses": [{"id": "corpse_01"}],
    }
    ids = _surroundings_target_ids(s, include_corpses=True)
    assert "corpse_01" in ids and "n1" in ids and "loc" in ids


def test_surroundings_target_ids_excludes_corpses_by_default():
    s = {
        "entities": [{"id": "n1"}],
        "corpses": [{"id": "corpse_01"}],
    }
    ids = _surroundings_target_ids(s)
    assert "corpse_01" not in ids and "n1" in ids


def test_perceive_no_target_passes():
    output = JudgeOutput(actions=[Verb(name="perceive")])
    check_semantics(output, _ents())


def test_attack_skill_id_must_match_skills():
    s = _ents({"id": "n1", "type": "npc", "friendly": False})
    s["location"] = {"id": "loc_01"}
    s["skills"] = [{"id": "skill_01"}]
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["n1"],
                                       modifiers={"skill_id": "skill_01"})])
    check_semantics(output, s)


def test_attack_skill_id_unknown_rejected():
    s = _ents({"id": "n1", "type": "npc", "friendly": False})
    s["location"] = {"id": "loc_01"}
    s["skills"] = [{"id": "skill_01"}]
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["n1"],
                                       modifiers={"skill_id": "ghost_skill"})])
    with pytest.raises(JudgeSemanticError, match="not in skills"):
        check_semantics(output, s)
