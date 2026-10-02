"""Resolve one choice, apply its consequences, and advance the harbor clock."""

from random import Random

from .combat import plan_combat_exchange, plan_combat_start
from .combat_types import CombatAction
from .dice import compute_grade, compute_required_roll
from .graph import (
    AddEdgeChange,
    GraphEdge,
    RemoveEdgeChange,
    SetEdgePropertyChange,
    SetNodePropertyChange,
)
from .graph.apply import apply_graph_changes
from .graph.query import (
    edges_from,
    edges_to,
    inventory_of,
    known_skills_of,
    location_of,
)
from .models import (
    Choice,
    Condition,
    Effect,
    GameState,
    JournalEntry,
    Result,
    Story,
    chapter,
)
from .move import plan_character_move


def new_game(story: Story, name: str, role: str, *, seed: int) -> GameState:
    if role not in story.roles:
        raise ValueError("unknown role")
    state = GameState(
        game_id="",
        profile=story.id,
        content_version=story.version,
        role=role,
        graph=story.graph.model_copy(deep=True),
        rng_seed=seed,
    )
    _set_property(state, "player", "name", name)
    _set_property(state, "player", f"stats.{story.roles[role].stat}", 14)
    _connect(state, "knows_skill", "player", story.roles[role].skill)
    if story.roles[role].item:
        apply_effects(state, [Effect(kind="give", target=story.roles[role].item)])
    _record(state, text=story.intro)
    return state


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
    if state.combat and option.id in {"combat.attack", "combat.defend", "combat.flee"}:
        action = CombatAction(kind=option.id.split(".")[1])
        return plan_combat_exchange(
            state.graph, state.combat, "player", action, dice=20
        ).state.last_dc
    if state.combat and option.id.startswith("combat.skill:"):
        return plan_combat_exchange(
            state.graph,
            state.combat,
            "player",
            _skill_action(state, option.target),
            dice=20,
        ).state.last_dc
    return None


def choose(story: Story, original: GameState, action_id: str) -> GameState:
    option = next(
        (choice for choice in list_choices(story, original) if choice.id == action_id),
        None,
    )
    if option is None or not can_choose(original, option):
        raise ValueError("action is not available")
    required = required_roll(original, option) if option.check else None
    state = original.model_copy(deep=True)
    state.revision += 1
    _set_property(
        state,
        "player",
        "gold",
        state.graph.nodes["player"].properties["gold"] - option.gold,
    )
    if option.system:
        _apply_system_choice(story, state, option)
    else:
        _set_property(
            state,
            "player",
            "mp",
            state.graph.nodes["player"].properties["mp"] - option.mp,
        )
        _record(state, text=option.label, kind="action")
        result = option.success
        if option.check:
            dice = _roll(state)
            assert required is not None
            success = compute_grade(dice, dice, required) in {
                "success",
                "critical_success",
            }
            _record(
                state,
                key="roll",
                kind="roll",
                dice=dice,
                required=required,
                result="success" if success else "failure",
            )
            if not success:
                result = option.failure
        apply_effects(state, result.effects)
        _record(state, text=result.text)
        if option.enemy:
            state.combat = plan_combat_start(state.graph, "player", option.enemy).state
            _record(state, key="battle_start")
        if option.once:
            _set_property(
                state, "chapter", "done", [*chapter(state).get("done", []), option.id]
            )
    _set_property(
        state,
        "chapter",
        "elapsed_ticks",
        chapter(state)["elapsed_ticks"] + option.ticks,
    )
    _advance_world(story, state)
    return state


def _apply_system_choice(story: Story, state: GameState, option: Choice) -> None:
    action = option.id
    if action.startswith("move:"):
        state.graph = apply_graph_changes(
            state.graph,
            plan_character_move(
                state.graph, "player", option.target, require_connection=True
            ).changes,
        )
        desc = story.descriptions[option.target]
        _record(state, key="arrive", name=desc.name, text_value=desc.text)
    elif action.startswith("combat."):
        _apply_combat_choice(state, option)
    elif action == "item:bandage":
        for edge in edges_from(state.graph, "player", "carries"):
            if edge.to_node_id == "bandage":
                state.graph = apply_graph_changes(
                    state.graph, [RemoveEdgeChange(type="remove_edge", edge_id=edge.id)]
                )
        player = state.graph.nodes["player"].properties
        _set_property(state, "player", "hp", min(player["max_hp"], player["hp"] + 3))
        if state.combat:
            state.combat.player_hearts = min(3, state.combat.player_hearts + 1)
        _record(state, key="healed")
    elif action.startswith("growth:"):
        _connect(state, "knows_skill", "player", option.target)
        _set_property(state, "chapter", "grew", True)
        _set_property(
            state, "player", "mp", state.graph.nodes["player"].properties["max_mp"]
        )
        _record(state, key="grew", name=story.descriptions[option.target].name)


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


def _apply_combat_choice(state: GameState, option: Choice) -> None:
    battle = state.combat
    assert battle is not None
    if option.id == "combat.listen":
        battle.enemy_pressure = 1
        battle.round += 1
        _connect(state, "has_knowledge", "player", "guard_fear")
        _record(state, key="listen_text")
        return
    if option.id == "combat.reassure":
        battle.enemy_pressure = 2
        battle.round += 1
        _record(state, key="reassure_text")
        return
    if option.id == "combat.mercy":
        _set_property(state, "chapter", "gate_open", True)
        _set_property(state, "chapter", "merciful", True)
        _connect(state, "relation", "guard", "player", {"affinity": 20})
        state.combat = None
        _record(state, key="mercy_text")
        return
    action = (
        _skill_action(state, option.target)
        if option.id.startswith("combat.skill:")
        else CombatAction(kind=option.id.split(".")[1])
    )
    dice = _roll(state)
    result = plan_combat_exchange(state.graph, battle, "player", action, dice=dice)
    state.graph = apply_graph_changes(state.graph, result.changes)
    state.combat = result.state
    success = dice >= result.state.last_dc
    _record(
        state,
        key="roll",
        kind="roll",
        dice=dice,
        required=result.state.last_dc,
        result="success" if success else "failure",
    )
    outcome = result.state.outcome
    if outcome == "ongoing":
        _record(state, key=f"battle_{action.kind}" if success else "battle_failure")
        return
    state.combat = None
    _record(
        state,
        key={"victory": "victory", "defeat": "defeat", "escaped": "fled"}[outcome],
    )
    if outcome == "victory":
        _set_property(state, "chapter", "gate_open", True)
        _set_property(state, "chapter", "violence", chapter(state)["violence"] + 1)
        _set_property(state, "chapter", "alert", min(6, chapter(state)["alert"] + 2))
    else:
        if outcome == "defeat":
            player = state.graph.nodes["player"].properties
            _set_property(state, "player", "hp", max(1, player["hp"]))
            _set_property(state, "player", "gold", max(0, player["gold"] - 3))
        state.graph = apply_graph_changes(
            state.graph, plan_character_move(state.graph, "player", "square").changes
        )


def _skill_action(state: GameState, skill_id: str) -> CombatAction:
    return CombatAction(
        kind=state.graph.nodes[skill_id].properties["action"],
        support_id=skill_id,
        support_kind="skill",
    )


def _advance_world(story: Story, state: GameState) -> None:
    props = chapter(state)
    if props.get("ending") == "escape":
        ending = {"inspector": "public", "keeper": "bargain"}.get(
            props["ledger_to"], "quiet"
        )
        _set_property(state, "chapter", "ending", ending)
        return
    for milestone in sorted(story.milestones, key=lambda event: (event.tick, event.id)):
        props = chapter(state)
        if props["elapsed_ticks"] >= milestone.tick and milestone.id not in props.get(
            "milestones", []
        ):
            apply_effects(state, milestone.result.effects)
            _set_property(
                state,
                "chapter",
                "milestones",
                [*chapter(state).get("milestones", []), milestone.id],
            )
            _record(state, text=milestone.result.text, kind="world")
    if chapter(state)["elapsed_ticks"] >= story.deadline:
        _set_property(
            state,
            "chapter",
            "ending",
            "stranded" if chapter(state)["rescued"] else "departed",
        )
        state.combat = None


def apply_effects(state: GameState, effects: list[Effect]) -> None:
    for effect in effects:
        if effect.kind == "set":
            _set_property(state, effect.target, effect.key, effect.value)
        elif effect.kind == "add":
            value = (
                state.graph.nodes[effect.target].properties[effect.key] + effect.value
            )
            _set_property(state, effect.target, effect.key, value)
        elif effect.kind == "learn":
            _connect(state, "has_knowledge", effect.source, effect.target)
        elif effect.kind == "companion":
            _connect(state, "has_companion", effect.source, effect.target)
        elif effect.kind == "relation":
            _connect(
                state,
                "relation",
                effect.source,
                effect.target,
                {effect.key: effect.value},
            )
        elif effect.kind == "move":
            state.graph = apply_graph_changes(
                state.graph,
                plan_character_move(state.graph, effect.source, effect.target).changes,
            )
        elif effect.kind == "give":
            removals = [
                RemoveEdgeChange(type="remove_edge", edge_id=edge.id)
                for edge in [
                    *edges_from(state.graph, effect.target),
                    *edges_to(state.graph, effect.target),
                ]
                if edge.type
                in {"carries", "equips", "located_at", "hidden_at", "reward_of"}
            ]
            edge = GraphEdge(
                id=f"carries:{effect.source}:{effect.target}",
                type="carries",
                **{"from": effect.source, "to": effect.target},
            )
            state.graph = apply_graph_changes(
                state.graph, [*removals, AddEdgeChange(type="add_edge", edge=edge)]
            )


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


def _set_property(state: GameState, target: str, key: str, value: object) -> None:
    state.graph = apply_graph_changes(
        state.graph,
        [
            SetNodePropertyChange(
                type="set_node_property", node_id=target, path=key, value=value
            )
        ],
    )


def _connect(
    state: GameState,
    kind: str,
    source: str,
    target: str,
    properties: dict | None = None,
) -> None:
    existing = next(
        (
            edge
            for edge in edges_from(state.graph, source, kind)
            if edge.to_node_id == target
        ),
        None,
    )
    if existing:
        changes = [
            SetEdgePropertyChange(
                type="set_edge_property", edge_id=existing.id, path=key, value=value
            )
            for key, value in (properties or {}).items()
        ]
        state.graph = apply_graph_changes(state.graph, changes)
        return
    edge = GraphEdge(
        id=f"{kind}:{source}:{target}",
        type=kind,
        **{"from": source, "to": target},
        properties=properties or {},
    )
    state.graph = apply_graph_changes(
        state.graph, [AddEdgeChange(type="add_edge", edge=edge)]
    )


def _roll(state: GameState) -> int:
    dice = Random(f"{state.rng_seed}:{state.rng_step}").randint(1, 20)
    state.rng_step += 1
    return dice


def _record(
    state: GameState, text: str = "", *, key: str = "", kind: str = "story", **values
) -> None:
    state.journal.append(
        JournalEntry(turn=state.revision, kind=kind, text=text, key=key, values=values)
    )
