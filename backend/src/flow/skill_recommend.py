"""§2.3 step 4 — produce 3 LLM-suggested skill learn-candidates.

Called right after level_up. Context = character.memories + recent N turns of turn_log +
recent N turns of raw player input. The LLM decides the narrative fields
(name/description/type/target/primary_stat/special_effect) and the engine fills in
id/level and template numerics to build the Skill object.
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
    """Latest N player utterances from recent_dialogue (already capped at RULES.memory.recent_dialogue_turns)."""
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
        existing_skills=[
            {
                "name": s.name,
                "type": s.type,
                "description": s.description,
                "special_effect": s.special_effect,
            }
            for s in p.learned_skills
        ],
        recent_turns=_recent_turn_summaries(state, _RECENT_TURNS_FOR_RECOMMEND),
        recent_inputs=_recent_inputs(state, _RECENT_INPUTS_FOR_RECOMMEND),
    )


async def recommend_skill_candidates(
    client: LLMClient,
    state: GameState,
) -> list[Skill]:
    """LLM call → 3 Skill objects. Re-raises call failures (the caller decides any silent fallback).

    No side effects — does not touch state directly (the caller writes pending_skill_candidates).
    """
    payload = _build_input(state)
    output = await skill_recommend(client, payload)
    level = state.characters[state.player_id].level
    existing = existing_skill_ids(state)
    skills: list[Skill] = []
    for c in output.candidates:
        s = build_skill_from_candidate(c, level, existing)
        existing.add(s.id)  # prevent duplicates within the same recommendation batch
        skills.append(s)
    return skills
