"""§2.3 step 4 — skill_recommend agent + build_skill_from_candidate + endpoint flow."""

import pytest
from pydantic import ValidationError

from src.domain.entities import Character, Skill, Stats
from src.domain.memory import DialoguePair, Memory, TurnLogEntry
from src.llm_calls.recommend import (
    SkillCandidate,
    SkillRecommendOutput,
)
from src.engines import skill as skill_eng
from src.flow import skill_recommend as recommend_mod


# --- schema ---------------------------------------------------------------


def test_output_allows_one_to_three_candidates():
    one = {
        "name": "화염구",
        "description": "불꽃을 던진다",
        "type": "attack",
        "target": "single",
        "primary_stat": "INT",
        "special_effect": "갑옷을 녹임",
    }
    with pytest.raises(ValidationError):
        SkillRecommendOutput.model_validate({"candidates": []})
    with pytest.raises(ValidationError):
        SkillRecommendOutput.model_validate({"candidates": [one] * 4})
    out1 = SkillRecommendOutput.model_validate({"candidates": [one]})
    assert len(out1.candidates) == 1
    out3 = SkillRecommendOutput.model_validate({"candidates": [one] * 3})
    assert len(out3.candidates) == 3


def test_candidate_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SkillCandidate.model_validate(
            {
                "name": "x",
                "description": "y",
                "type": "attack",
                "target": "single",
                "primary_stat": "STR",
                "special_effect": "z",
                "power": 99,  # engine-only — must be rejected if LLM provides it
            }
        )


def test_candidate_rejects_invalid_enum():
    with pytest.raises(ValidationError):
        SkillCandidate.model_validate(
            {
                "name": "x",
                "description": "y",
                "type": "magic",  # undefined type
                "target": "single",
                "primary_stat": "STR",
                "special_effect": "z",
            }
        )


# --- build_skill_from_candidate -------------------------------------------


def _candidate(**kw):
    base = {
        "name": "화염구",
        "description": "불꽃을 한 곳에 모아 던지는 마법",
        "type": "attack",
        "target": "single",
        "primary_stat": "INT",
        "special_effect": "갑옷을 녹임",
    }
    base.update(kw)
    return SkillCandidate.model_validate(base)


def test_build_skill_attack_template_scales_with_level():
    c = _candidate(type="attack")
    s0 = skill_eng.build_skill_from_candidate(c, 0, set())
    s5 = skill_eng.build_skill_from_candidate(c, 5, set())
    assert s5.power > s0.power
    assert s5.mp_cost > s0.mp_cost
    assert s5.level == 5


def test_build_skill_carries_llm_fields_verbatim():
    c = _candidate()
    s = skill_eng.build_skill_from_candidate(c, 3, set())
    assert s.name == c.name
    assert s.description == c.description
    assert s.type == c.type
    assert s.target == c.target
    assert s.primary_stat == c.primary_stat
    assert s.special_effect == c.special_effect


def test_build_skill_unique_id_avoids_collision():
    c = _candidate()
    existing = {"skill_l3"}
    s = skill_eng.build_skill_from_candidate(c, 3, existing)
    assert s.id not in existing


def test_build_skill_dedupes_within_batch():
    c1 = _candidate()
    c2 = _candidate()  # same name
    existing: set[str] = set()
    s1 = skill_eng.build_skill_from_candidate(c1, 3, existing)
    existing.add(s1.id)
    s2 = skill_eng.build_skill_from_candidate(c2, 3, existing)
    assert s1.id != s2.id


def test_build_skill_distinct_korean_names_get_distinct_base_ids():
    # Regression: an earlier _slugify dropped all non-ASCII chars and fell back
    # to the literal "skill", so every Korean candidate produced base="skill".
    # Distinct names must yield distinct base ids — the suffix counter is for
    # actual collisions, not a substitute for missing slugification.
    c1 = _candidate(name="화염구")
    c2 = _candidate(name="얼음창")
    existing: set[str] = set()
    s1 = skill_eng.build_skill_from_candidate(c1, 3, existing)
    s2 = skill_eng.build_skill_from_candidate(c2, 3, existing)
    # Strip the level suffix to compare the name-derived part only.
    base1 = s1.id.rsplit("_l", 1)[0]
    base2 = s2.id.rsplit("_l", 1)[0]
    assert base1 != base2


def test_existing_skill_ids_collects_from_all_chars(fresh_state):
    fresh_state.skills["r1"] = Skill(
        id="r1", name="x", type="attack", target="single", primary_stat="STR"
    )
    fresh_state.skills["l1"] = Skill(
        id="l1", name="y", type="heal", target="self", primary_stat="WIS"
    )
    fresh_state.characters["a"] = Character(
        id="a",
        name="A",
        race_id="x",
        stats=Stats(),
        racial_skill_ids=["r1"],
        learned_skill_ids=["l1"],
    )
    ids = skill_eng.existing_skill_ids(fresh_state)
    assert ids == {"r1", "l1"}


# --- input build ----------------------------------------------------------


def _seed_player(fresh_state):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        level=3,
        memories=[
            Memory(content="고블린을 칼로 찔렀음", importance=2, turn=1),
            Memory(content="조용히 다가가는 데 성공", importance=3, turn=2),
        ],
    )
    fresh_state.characters["player_01"] = p
    fresh_state.turn_log = [
        TurnLogEntry(turn=1, target="goblin_01", summary="잠입 후 일격"),
        TurnLogEntry(turn=2, target=None, summary="안전한 곳에서 대기"),
    ]
    fresh_state.recent_dialogue = [
        DialoguePair(turn=1, player="조용히 다가가서 등에 칼을 박는다", narrator="..."),
        DialoguePair(turn=2, player="물러나서 휴식한다", narrator="..."),
    ]
    return fresh_state


def test_build_input_packs_memories_turns_and_inputs(fresh_state):
    state = _seed_player(fresh_state)
    payload = recommend_mod._build_input(state)
    assert payload.character["name"] == "주"
    assert payload.character["level"] == 3
    assert len(payload.character["memories"]) == 2
    assert any("잠입" in t["summary"] for t in payload.recent_turns)
    assert any("조용히" in s for s in payload.recent_inputs)


# --- recommend_skill_candidates (mock LLM) --------------------------------


class _FakeLLM:
    def __init__(self, candidates):
        self.candidates = candidates

    async def chat(
        self, messages, think=False, agent=None, temperature=None, use_fallback=False
    ):
        body = SkillRecommendOutput(candidates=self.candidates).model_dump_json()
        return {"answer": body, "think": ""}


async def test_recommend_returns_three_skills_with_engine_numerics(fresh_state):
    state = _seed_player(fresh_state)
    cands = [
        _candidate(name="그림자 보행", type="attack", primary_stat="DEX"),
        _candidate(name="치유의 손길", type="heal", target="self", primary_stat="WIS"),
        _candidate(name="화염구", type="attack", primary_stat="INT"),
    ]
    fake = _FakeLLM(cands)
    skills = await recommend_mod.recommend_skill_candidates(fake, state)
    assert len(skills) == 3
    # level=3 → attack power = 5+3*2 = 11
    attack = [s for s in skills if s.type == "attack"]
    assert all(s.level == 3 for s in skills)
    assert all(s.power > 0 for s in attack)
    # no id collisions
    ids = {s.id for s in skills}
    assert len(ids) == 3
