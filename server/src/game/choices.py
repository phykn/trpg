"""Read-only choice availability, conditions, and roll previews."""

from .combat import plan_combat_exchange
from .combat_types import CombatAction
from .dice import compute_required_roll
from .graph.query import edges_from, inventory_of, known_skills_of, location_of
from .models import Choice, Condition, GameState, Result, Story, chapter


def matches_condition(state: GameState, condition: Condition) -> bool:
    graph = state.graph
    if condition.kind == "at":
        result = location_of(graph, condition.source) == condition.target
    elif condition.kind in {"knows", "carries"}:
        edge_type = "has_knowledge" if condition.kind == "knows" else "carries"
        result = any(
            e.to_node_id == condition.target
            for e in edges_from(graph, condition.source, edge_type)
        )
    elif condition.kind == "relation":
        result = any(
            e.to_node_id == condition.target
            and e.properties.get(condition.key) == condition.value
            for e in edges_from(graph, condition.source, "relation")
        )
    else:
        value = graph.nodes[condition.target].properties.get(condition.key)
        if condition.op == "eq":
            result = value == condition.value
        else:
            result = type(value) is int and type(condition.value) is int
            if result:
                result = (
                    value >= condition.value
                    if condition.op == "gte"
                    else value < condition.value
                )
    return not result if condition.negate else result


def list_choices(story: Story, state: GameState) -> list[Choice]:
    if chapter(state).get("ending"):
        return []
    if state.combat:
        return _combat_choices(state)
    done = chapter(state).get("done", [])
    available = [
        choice
        for choice in story.choices
        if (not choice.once or choice.id not in done)
        and all(matches_condition(state, c) for c in choice.show)
    ]
    place = location_of(state.graph, "player")
    for edge in edges_from(state.graph, place, "connects_to"):
        available.append(
            _system_choice(f"move:{edge.to_node_id}", edge.to_node_id, "move")
        )
    player = state.graph.nodes["player"].properties
    if (
        "bandage" in inventory_of(state.graph, "player")
        and player["hp"] < player["max_hp"]
    ):
        available.append(
            _system_choice("item:bandage", "bandage", "item", description="heal_hint")
        )
    if chapter(state).get("rescued") and not chapter(state).get("grew"):
        known = {edge.to_node_id for edge in known_skills_of(state.graph, "player")}
        for role in story.roles.values():
            if role.skill not in known:
                available.append(
                    _system_choice(
                        f"growth:{role.skill}",
                        role.skill,
                        "growth",
                        ticks=0,
                        description="growth_hint",
                    )
                )
    return available


def can_choose(state: GameState, option: Choice) -> bool:
    player = state.graph.nodes["player"].properties
    return (
        player["gold"] >= option.gold
        and player["mp"] >= option.mp
        and all(matches_condition(state, c) for c in option.requires)
    )


def required_roll(state: GameState, option: Choice) -> int | None:
    if not can_choose(state, option):
        return None
    if option.check:
        stat = state.graph.nodes["player"].properties["stats"][option.check.stat]
        alert_penalty = (
            chapter(state)["alert"] // 2 if option.check.stat == "agility" else 0
        )
        return compute_required_roll(option.check.dc + alert_penalty, stat)
    if state.combat and (
        option.id in {"combat.attack", "combat.defend", "combat.flee"}
        or option.id.startswith("combat.skill:")
    ):
        return plan_combat_exchange(
            state.graph, state.combat, "player", combat_action(state, option), dice=20
        ).state.last_dc
    return None


def _combat_choices(state: GameState) -> list[Choice]:
    battle = state.combat
    assert battle is not None
    result = [
        _system_choice(
            "combat.attack", battle.active_enemy_id, "attack", description="combat_risk"
        ),
        _system_choice("combat.defend", "player", "defend", description="combat_risk"),
    ]
    if battle.enemy_pressure == 0:
        result.append(
            _system_choice(
                "combat.listen",
                battle.active_enemy_id,
                "listen",
                description="listen_hint",
            )
        )
    elif battle.enemy_pressure == 1:
        result.append(
            _system_choice(
                "combat.reassure",
                battle.active_enemy_id,
                "reassure",
                description="reassure_hint",
            )
        )
    else:
        result.append(
            _system_choice(
                "combat.mercy",
                battle.active_enemy_id,
                "mercy",
                description="mercy_hint",
            )
        )
    for edge in known_skills_of(state.graph, "player"):
        skill = state.graph.nodes[edge.to_node_id]
        if skill.properties["action"] in {"attack", "defend", "flee"}:
            result.append(
                _system_choice(
                    f"combat.skill:{skill.id}",
                    skill.id,
                    "skill",
                    mp=skill.properties["mp_cost"],
                    description="skill_hint",
                )
            )
    player = state.graph.nodes["player"].properties
    if "bandage" in inventory_of(state.graph, "player") and (
        player["hp"] < player["max_hp"] or battle.player_hearts < 3
    ):
        result.append(
            _system_choice("item:bandage", "bandage", "item", description="heal_hint")
        )
    result.append(
        _system_choice("combat.flee", "square", "flee", description="combat_risk")
    )
    return result


def _system_choice(action_id: str, target: str, label: str, **kwargs) -> Choice:
    return Choice(
        id=action_id,
        target=target,
        label=label,
        system=True,
        success=Result(text=""),
        once=False,
        **{"description": "", **kwargs},
    )


def combat_action(state: GameState, option: Choice) -> CombatAction:
    if option.id.startswith("combat.skill:"):
        return CombatAction(
            kind=state.graph.nodes[option.target].properties["action"],
            support_id=option.target,
            support_kind="skill",
        )
    return CombatAction(kind=option.id.split(".")[1])
