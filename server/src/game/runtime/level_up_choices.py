import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph_query import edges_from
from src.game.runtime.state import GameRuntimeState
from src.locale.render import render
from src.llm.calls._runner import get_prompt, run_with_retries
from src.llm.client import LLMClient


SkillAction = Literal["attack", "defend", "flee", "social"]
SkillEffect = Literal[
    "dc_down",
    "extra_heart_damage",
    "prevent_heart_loss",
    "escape_boost",
]


class LevelUpSkillCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=96)
    action: SkillAction
    effect_template: SkillEffect
    support_bonus: int = Field(ge=1, le=3)
    mp_cost: int = Field(ge=1, le=3)
    tags: list[str] = Field(default_factory=list, max_length=4)


class _CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[LevelUpSkillCandidate] = Field(min_length=1, max_length=2)


_CANDIDATE_ADAPTER = TypeAdapter(_CandidateOutput)
_SLUG_RE = re.compile(r"[^a-z0-9_]+")


async def build_level_up_choices(
    runtime: GameRuntimeState,
    *,
    llm: LLMClient | None = None,
) -> list[dict[str, Any]]:
    player = runtime.graph.nodes[runtime.progress.player_id]
    props = player.properties
    locale = runtime.progress.locale
    choices: list[dict[str, Any]] = []

    if _int_prop(props, "max_hp") < 10:
        choices.append(
            {
                "id": "max_hp",
                "label": render("runtime.level_growth.max_hp", locale),
                "description": render("runtime.level_choice.max_hp", locale),
                "growth": {"kind": "max_hp"},
            }
        )
    if _int_prop(props, "max_mp") < 10:
        choices.append(
            {
                "id": "max_mp",
                "label": render("runtime.level_growth.max_mp", locale),
                "description": render("runtime.level_choice.max_mp", locale),
                "growth": {"kind": "max_mp"},
            }
        )

    known_edges = list(edges_from(runtime.graph, runtime.progress.player_id, "knows_skill"))
    for edge in known_edges:
        tier = edge.properties.get("tier", 1)
        if not isinstance(tier, int) or tier >= 3:
            continue
        skill = runtime.graph.nodes.get(edge.to_node_id)
        if skill is None:
            continue
        label = _skill_name(skill.properties, edge.to_node_id)
        choices.append(
            {
                "id": f"upgrade_skill:{edge.to_node_id}",
                "label": render("runtime.level_growth.upgrade_skill", locale, skill=label),
                "description": render(
                    "runtime.level_choice.upgrade_skill",
                    locale,
                    tier=tier,
                    next_tier=tier + 1,
                ),
                "growth": {"kind": "upgrade_skill", "skill_id": edge.to_node_id},
            }
        )

    if len(known_edges) < 3:
        for candidate in await _skill_candidates(runtime, llm=llm):
            skill = _skill_spec(runtime, candidate)
            choices.append(
                {
                    "id": f"learn_skill:{skill['id']}",
                    "label": render(
                        "runtime.level_growth.learn_skill",
                        locale,
                        skill=candidate.name,
                    ),
                    "description": candidate.description,
                    "growth": {
                        "kind": "learn_skill",
                        "skill_id": skill["id"],
                        "skill": skill,
                    },
                }
            )

    return choices


async def _skill_candidates(
    runtime: GameRuntimeState,
    *,
    llm: LLMClient | None,
) -> list[LevelUpSkillCandidate]:
    if llm is None:
        return _fallback_candidates(runtime)
    try:
        prompt = get_prompt("recommend", runtime.progress.locale)
        payload = _candidate_payload(runtime)
        out = await run_with_retries(
            llm,
            system_prompt=prompt,
            user_payload=json.dumps(payload, ensure_ascii=False),
            parse=lambda text: _CANDIDATE_ADAPTER.validate_json(text),
            retry_on=(ValidationError, json.JSONDecodeError),
            retries=3,
            agent="recommend",
            temperature=0.8,
        )
        return out.skills
    except (LLMUnavailable, ValidationError, json.JSONDecodeError, OSError):
        return _fallback_candidates(runtime)


def _candidate_payload(runtime: GameRuntimeState) -> dict[str, Any]:
    player = runtime.graph.nodes[runtime.progress.player_id]
    known = []
    for edge in edges_from(runtime.graph, runtime.progress.player_id, "knows_skill"):
        skill = runtime.graph.nodes.get(edge.to_node_id)
        if skill is not None:
            known.append(_skill_name(skill.properties, edge.to_node_id))
    recent = [entry.text for entry in runtime.log_entries[-8:]]
    return {
        "player": {
            "name": player.properties.get("name", "player"),
            "level": player.properties.get("level", 1),
            "stats": player.properties.get("stats", {}),
            "known_skills": known,
        },
        "recent_log": recent,
        "allowed_actions": ["attack", "defend", "flee", "social"],
        "allowed_effects": [
            "dc_down",
            "extra_heart_damage",
            "prevent_heart_loss",
            "escape_boost",
        ],
    }


def _fallback_candidates(runtime: GameRuntimeState) -> list[LevelUpSkillCandidate]:
    player = runtime.graph.nodes[runtime.progress.player_id]
    locale = runtime.progress.locale
    stats = player.properties.get("stats", {})
    agility = stats.get("agility", 10) if isinstance(stats, dict) else 10
    mind = stats.get("mind", 10) if isinstance(stats, dict) else 10
    if isinstance(agility, int) and agility >= mind:
        return [
            LevelUpSkillCandidate(
                name=render("runtime.level_choice.fallback.agile_attack.name", locale),
                description=render(
                    "runtime.level_choice.fallback.agile_attack.description",
                    locale,
                ),
                action="attack",
                effect_template="dc_down",
                support_bonus=2,
                mp_cost=2,
                tags=["agility", "attack"],
            ),
            LevelUpSkillCandidate(
                name=render("runtime.level_choice.fallback.quick_flee.name", locale),
                description=render(
                    "runtime.level_choice.fallback.quick_flee.description",
                    locale,
                ),
                action="flee",
                effect_template="escape_boost",
                support_bonus=3,
                mp_cost=2,
                tags=["agility", "flee"],
            ),
        ]
    return [
        LevelUpSkillCandidate(
            name=render("runtime.level_choice.fallback.focus_attack.name", locale),
            description=render(
                "runtime.level_choice.fallback.focus_attack.description",
                locale,
            ),
            action="attack",
            effect_template="dc_down",
            support_bonus=2,
            mp_cost=2,
            tags=["mind", "attack"],
        ),
        LevelUpSkillCandidate(
            name=render("runtime.level_choice.fallback.calm_defend.name", locale),
            description=render(
                "runtime.level_choice.fallback.calm_defend.description",
                locale,
            ),
            action="defend",
            effect_template="prevent_heart_loss",
            support_bonus=1,
            mp_cost=3,
            tags=["mind", "defend"],
        ),
    ]


def _skill_spec(
    runtime: GameRuntimeState,
    candidate: LevelUpSkillCandidate,
) -> dict[str, Any]:
    digest = hashlib.sha1(
        json.dumps(
            {
                "game": runtime.progress.game_id,
                "level": runtime.graph.nodes[runtime.progress.player_id].properties.get(
                    "level", 1
                ),
                "name": candidate.name,
                "effect": candidate.effect_template,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:10]
    slug = _SLUG_RE.sub("_", candidate.action.lower()).strip("_") or "skill"
    return {
        "id": f"skill_gen_{slug}_{digest}",
        "name": candidate.name,
        "description": candidate.description,
        "kind": "support",
        "action": candidate.action,
        "mp_cost": candidate.mp_cost,
        "effect_template": candidate.effect_template,
        "support_bonus": candidate.support_bonus,
        "tags": list(candidate.tags[:4]),
    }


def _skill_name(properties: dict[str, Any], fallback: str) -> str:
    name = properties.get("name")
    return name if isinstance(name, str) and name else fallback


def _int_prop(properties: dict[str, Any], key: str) -> int:
    value = properties.get(key, 0)
    return value if isinstance(value, int) else 0
