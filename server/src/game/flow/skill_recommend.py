"""§2.3 step 4 — produce 3 LLM-suggested skill learn-candidates.

Called right after level_up. Context = character.memories + recent N turns of turn_log +
recent N turns of raw player input. The LLM decides the narrative fields
(name/description/type/target/primary_stat/special_effect) and the engine fills in
id/level and template numerics to build the Skill object.
"""

from __future__ import annotations

from ..domain.entities import Skill
from src.llm.calls.recommend import (
    SkillRecommendInput,
    recommend,
)
from src.llm.client import LLMClient
from ..ontology.queries import known_skills_of, race_of
from ..rules import RULES
from ..domain.state import GameState
from ..engines.skill import build_skill_from_candidate, existing_skill_ids


def _recent_inputs(state: GameState, n: int) -> list[str]:
    """Latest N player utterances from recent_dialogue (already capped at RULES.memory.recent_dialogue_turns)."""
    items = state.recent_dialogue[-n:] if n else []
    return [d.player for d in items if d.player]


def _recent_turn_summaries(state: GameState, n: int) -> list[dict]:
    items = state.turn_log[-n:] if n else []
    return [{"turn": e.turn, "summary": e.summary} for e in items]


def _build_input(state: GameState) -> SkillRecommendInput:
    p = state.characters[state.player_id]
    graph = state.graph()
    # Race name via graph relation; fall back to raw race id when no Race
    # entity is registered for the player's race_id.
    race_id = race_of(graph, p.id)
    race_name = p.race_id
    if race_id is not None:
        race = state.races.get(race_id)
        race_name = race.name if race is not None else race_id
    learned_skills: list[dict] = []
    for edge in known_skills_of(graph, p.id):
        if (edge.attrs or {}).get("source") != "learned":
            continue
        s = state.skills.get(edge.to_id)
        if s is None:
            continue
        learned_skills.append(
            {
                "name": s.name,
                "type": s.type,
                "target": s.target,
                "primary_stat": s.primary_stat,
                "description": s.description,
            }
        )
    return SkillRecommendInput(
        character={
            "name": p.name,
            "race": race_name,
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
        existing_skills=learned_skills,
        recent_turns=_recent_turn_summaries(state, RULES.skill.recommend_recent_turns),
        recent_inputs=_recent_inputs(state, RULES.skill.recommend_recent_inputs),
    )


async def recommend_skill_candidates(
    client: LLMClient,
    state: GameState,
) -> list[Skill]:
    """LLM call → 3 Skill objects. Re-raises call failures (the caller decides any silent fallback).

    No side effects — does not touch state directly (the caller wires the candidates into its own flow).
    """
    payload = _build_input(state)
    output = await recommend(client, payload, state.locale)
    level = state.characters[state.player_id].level
    existing = existing_skill_ids(state)
    skills: list[Skill] = []
    for c in output.candidates:
        s = build_skill_from_candidate(c, level, existing)
        existing.add(s.id)  # prevent duplicates within the same recommendation batch
        skills.append(s)
    return skills
