"""§2.3 4단계 — LLM 으로 스킬 학습 후보 3개 산출.

level_up 직후 호출. 컨텍스트는 character.memories + 최근 N 턴 turn_log + 최근 N 턴
플레이어 입력 원문. LLM 이 서사 부분 (name/description/type/target/primary_stat/
special_effect) 을 정하고, 엔진이 id/level/template 수치를 채워 Skill 객체 생성.
"""
from __future__ import annotations

from ..domain.entities import Skill
from ..agents.skill_recommend import (
    SkillRecommendInput,
    skill_recommend,
)
from ..llm.client import LLMClient
from ..rules import RULES
from ..domain.state import GameState
from ..engines.skill import build_skill_from_candidate, existing_skill_ids


_RECENT_TURNS_FOR_RECOMMEND = 10
_RECENT_INPUTS_FOR_RECOMMEND = 5


def _recent_inputs(state: GameState, n: int) -> list[str]:
    """recent_dialogue 의 player 발화를 최근 N 개. (이미 cap 이 RULES.memory.recent_dialogue_turns)."""
    items = state.recent_dialogue[-n:] if n else []
    return [d.player for d in items if d.player]


def _recent_turn_summaries(state: GameState, n: int) -> list[dict]:
    items = state.turn_log[-n:] if n else []
    return [{"turn": e.turn, "summary": e.summary} for e in items]


def _race_name(state: GameState, race_id: str) -> str:
    race = state.races.get(race_id)
    return race.name if race else race_id


def _build_input(state: GameState) -> SkillRecommendInput:
    p = state.characters[state.player_id]
    return SkillRecommendInput(
        character={
            "name": p.name,
            "race": _race_name(state, p.race_id),
            "job": p.job,
            "level": p.level,
            "memories": [
                {
                    "content": m.content,
                    "importance": m.importance,
                    "turn": m.turn,
                }
                for m in p.memories
            ],
        },
        recent_turns=_recent_turn_summaries(state, _RECENT_TURNS_FOR_RECOMMEND),
        recent_inputs=_recent_inputs(state, _RECENT_INPUTS_FOR_RECOMMEND),
    )


async def recommend_skill_candidates(
    client: LLMClient,
    state: GameState,
) -> list[Skill]:
    """LLM 호출 → Skill 객체 3개. 호출 실패는 예외 그대로 raise (호출자가 silent fallback 결정).

    부산물 없음 — state 를 직접 만지지 않는다 (호출자가 pending_skill_candidates 박음).
    """
    payload = _build_input(state)
    output = await skill_recommend(client, payload)
    level = state.characters[state.player_id].level
    existing = existing_skill_ids(state)
    skills: list[Skill] = []
    for c in output.candidates:
        s = build_skill_from_candidate(c, level, existing)
        existing.add(s.id)  # 같은 산출 묶음 안 중복 방지
        skills.append(s)
    return skills
