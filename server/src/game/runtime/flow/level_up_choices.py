import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from src.game.domain.content import node_label
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph.query import edges_from
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.story_context import current_story_payload
from src.llm.calls.runner import get_prompt, run_with_retries
from src.llm.client import LLMClient
from src.llm.diag import engine_diag
from src.locale.render import render


SkillAction = Literal["attack", "defend", "flee", "talk"]


class LevelUpSkillCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=96)
    action: SkillAction
    bonus: int = Field(ge=1, le=3)
    mp_cost: int = Field(ge=1, le=3)


class LevelUpSkillFlavor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=96)


class _CandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[LevelUpSkillFlavor] = Field(min_length=1, max_length=2)


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
    for stat in ("body", "agility", "mind", "presence"):
        choices.append(
            {
                "id": f"stat:{stat}",
                "label": render(
                    "runtime.level_growth.stat",
                    locale,
                    stat=render(f"stat.{stat}", locale),
                ),
                "description": render(
                    "runtime.level_choice.stat",
                    locale,
                    stat=render(f"stat.{stat}", locale),
                ),
                "growth": {"kind": "stat", "stat": stat},
            }
        )

    known_edges = list(
        edges_from(runtime.graph, runtime.progress.player_id, "knows_skill")
    )
    for edge in known_edges:
        tier = edge.properties.get("tier", 1)
        if not isinstance(tier, int) or tier >= 3:
            continue
        skill = runtime.graph.nodes.get(edge.to_node_id)
        if skill is None:
            continue
        label = _skill_name(runtime, skill)
        choices.append(
            {
                "id": f"upgrade_skill:{edge.to_node_id}",
                "label": render(
                    "runtime.level_growth.upgrade_skill", locale, skill=label
                ),
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
    else:
        engine_diag(
            "levelup:choices_llm_skip",
            reason="known_skill_limit",
            known_skills=len(known_edges),
        )

    return choices


async def _skill_candidates(
    runtime: GameRuntimeState,
    *,
    llm: LLMClient | None,
) -> list[LevelUpSkillCandidate]:
    templates = _candidate_templates(runtime)
    if llm is None:
        engine_diag("levelup:choices_llm_skip", reason="no_llm")
        return templates
    try:
        engine_diag("levelup:choices_llm_start", templates=len(templates))
        prompt = get_prompt("recommend", runtime.progress.locale)
        payload = _candidate_payload(runtime, templates)
        out = await run_with_retries(
            llm,
            system_prompt=prompt,
            user_payload=json.dumps(payload, ensure_ascii=False),
            parse=lambda text: _CANDIDATE_ADAPTER.validate_json(text),
            retry_on=(ValidationError, json.JSONDecodeError),
            retries=3,
            agent="recommend",
        )
        candidates = _apply_flavors(templates, out.skills)
        engine_diag("levelup:choices_llm_ok", candidates=len(candidates))
        return candidates
    except (LLMUnavailable, ValidationError, json.JSONDecodeError, OSError) as exc:
        engine_diag("levelup:choices_llm_fallback", err=type(exc).__name__)
        return templates


def _candidate_payload(
    runtime: GameRuntimeState,
    templates: list[LevelUpSkillCandidate],
) -> dict[str, Any]:
    player = runtime.graph.nodes[runtime.progress.player_id]
    known = []
    for edge in edges_from(runtime.graph, runtime.progress.player_id, "knows_skill"):
        skill = runtime.graph.nodes.get(edge.to_node_id)
        if skill is not None:
            known.append(_skill_name(runtime, skill))
    recent = _recent_log_texts(runtime)
    return {
        "current_story": current_story_payload(runtime, include_status=False),
        "player": {
            "name": player.properties.get("name", "player"),
            "level": player.properties.get("level", 1),
            "stats": player.properties.get("stats", {}),
            "known_skills": known,
        },
        "skills": [
            {
                "index": index,
                "action": template.action,
                "description_hint": template.description,
            }
            for index, template in enumerate(templates)
        ],
        "recent_log": recent,
    }


def _recent_log_texts(runtime: GameRuntimeState) -> list[str]:
    texts: list[str] = []
    for entry in runtime.log_entries[-8:]:
        text = getattr(entry, "text", None)
        if isinstance(text, str) and text:
            texts.append(text)
    return texts


def _candidate_templates(runtime: GameRuntimeState) -> list[LevelUpSkillCandidate]:
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
                bonus=2,
                mp_cost=2,
            ),
            LevelUpSkillCandidate(
                name=render("runtime.level_choice.fallback.quick_distance.name", locale),
                description=render(
                    "runtime.level_choice.fallback.quick_distance.description",
                    locale,
                ),
                action="flee",
                bonus=3,
                mp_cost=2,
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
            bonus=2,
            mp_cost=2,
        ),
        LevelUpSkillCandidate(
            name=render("runtime.level_choice.fallback.calm_defend.name", locale),
            description=render(
                "runtime.level_choice.fallback.calm_defend.description",
                locale,
            ),
            action="defend",
            bonus=1,
            mp_cost=3,
        ),
    ]


def _apply_flavors(
    templates: list[LevelUpSkillCandidate],
    flavors: list[LevelUpSkillFlavor],
) -> list[LevelUpSkillCandidate]:
    out: list[LevelUpSkillCandidate] = []
    for template, flavor in zip(templates, flavors, strict=False):
        out.append(
            template.model_copy(
                update={
                    "name": flavor.name,
                    "description": flavor.description,
                }
            )
        )
    return out or templates


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
                "action": candidate.action,
                "bonus": candidate.bonus,
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
        "action": candidate.action,
        "bonus": candidate.bonus,
        "mp_cost": candidate.mp_cost,
    }


def _skill_name(runtime: GameRuntimeState, skill) -> str:
    return node_label(runtime.content, skill)


def _int_prop(properties: dict[str, Any], key: str) -> int:
    value = properties.get(key, 0)
    return value if isinstance(value, int) else 0
