# Heart Combat Skill Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct HP-damage combat with heart combat, one-support combat actions, capped skill growth, and 10-scale HP/MP/level progression.

**Architecture:** Keep the server authoritative. First replace pure engine rules and tests, then wire runtime dispatch, migration, front-state payloads, client rendering, and docs. Keep legacy graph concepts (`skill` nodes, `knows_skill` edges, graph changes, action cards) but change their combat meaning from HP damage to roll support.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI graph runtime, pytest, Expo React Native, TypeScript, Jest.

---

## Design Reference

Spec: `docs/superpowers/specs/2026-05-12-heart-combat-skill-growth-design.md`

Core rules to preserve:

- Level cap 10.
- Level 1 starts at HP 5 / MP 5.
- HP and MP cap at 10.
- Combat starts at player hearts 3 and enemy hearts 3.
- Only the player rolls a d20.
- `DC = 11 + (enemy_level - player_level) - support_bonus + situation_modifier`, clamped to 6..18.
- Stats do not affect combat DC.
- One turn has one basic action plus at most one support.
- Support is either one skill or one item, never both.
- No forced combat round limit.
- Skills cap at three known skills and tier 3 per skill.
- LLM can personalize skill name/description/tags, but the engine owns effects and numbers.

## File Structure

- `server/src/game/domain/combat.py` owns combat action/state models and should expose heart fields and support metadata.
- `server/src/game/engines/graph_combat.py` owns heart combat rules, DC calculation, support validation, MP spend, consumable item spend, and defeat/victory graph changes.
- `server/src/game/runtime/combat.py` maps `Action` into `GraphCombatAction`, applies combat graph changes, and preserves quest progress/reward handling after victory.
- `server/src/game/runtime/dispatch.py` routes in-combat `speak`, `pass`, `move`, `attack`, and `cast` actions into combat.
- `server/src/game/engines/growth.py` owns level/HP/MP formulas.
- `server/src/game/rules/config.py` owns level cap and base XP constants.
- `server/src/game/engines/graph_growth.py` owns HP/MP growth choices, skill learn limits, and skill upgrade changes.
- `server/src/game/runtime/level_up.py` persists one selected growth choice and writes the level-up card.
- `server/src/game/seed/graph_seed.py` should seed level 1 HP/MP as 5 and preserve one starting skill from race/template data.
- `server/src/db/graph_progress_rows.py` should clear old-format active combat state during progress load.
- `server/src/wire/models/graph.py`, `server/src/wire/graph_combat.py`, and `server/src/llm/context/graph_combat.py` expose heart combat to the client and narration payload.
- `client/services/wire.ts`, `client/services/graphAdapter.ts`, `client/logic/combat/types.ts`, `client/logic/combat/actions.ts`, and `client/components/combat/CombatStrip.tsx` show heart combat and build heart-combat actions.
- `docs/04-gameplay.md` should be updated after implementation to match the accepted rules.

## Task 1: Combat Domain Model And DC Helpers

**Files:**
- Modify: `server/src/game/domain/combat.py`
- Modify: `server/src/game/engines/graph_combat.py`
- Test: `server/tests/game/engines/test_graph_combat.py`

- [ ] **Step 1: Replace the combat engine tests with heart/DC expectations**

In `server/tests/game/engines/test_graph_combat.py`, update the fixture helpers so characters use level 1, HP/MP 5, and support-style skills/items:

```python
def _character(
    character_id: str,
    *,
    hp: int = 5,
    max_hp: int = 5,
    mp: int = 5,
    max_mp: int = 5,
    level: int = 1,
    alive: bool = True,
    status: list[str] | None = None,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "level": level,
            "hp": hp,
            "max_hp": max_hp,
            "mp": mp,
            "max_mp": max_mp,
            "alive": alive,
            "stats": {"body": 20, "agility": 1, "mind": 1, "presence": 1},
            "status": status or [],
        },
    )


def _skill(
    skill_id: str,
    *,
    action: str = "attack",
    template: str = "dc_down",
    mp_cost: int = 2,
    support_bonus: int = 2,
    tier: int = 1,
) -> GraphNode:
    return GraphNode(
        id=skill_id,
        type="skill",
        properties={
            "name": skill_id,
            "kind": "support",
            "action": action,
            "effect_template": template,
            "mp_cost": mp_cost,
            "support_bonus": support_bonus,
            "tier": tier,
        },
    )


def _item(
    item_id: str,
    *,
    action: str = "attack",
    template: str = "dc_down",
    support_bonus: int = 3,
    consumed: bool = True,
) -> GraphNode:
    return GraphNode(
        id=item_id,
        type="item",
        properties={
            "name": item_id,
            "support_action": action,
            "effect_template": template,
            "support_bonus": support_bonus,
            "consumable": consumed,
        },
    )
```

Replace the old HP-damage tests with these tests:

```python
def test_combat_start_uses_three_hearts_without_graph_changes():
    result = plan_combat_start(_graph(), "player_01", "goblin_01")

    assert result.changes == []
    assert result.state.location_id == "town_gate"
    assert result.state.player_id == "player_01"
    assert result.state.enemy_ids == ["goblin_01"]
    assert result.state.active_enemy_id == "goblin_01"
    assert result.state.player_hearts == 3
    assert result.state.enemy_hearts == 3
    assert result.state.round == 1
    assert result.state.outcome == "ongoing"
    assert result.state.trace[-1].kind == "combat_started"


def test_attack_success_reduces_enemy_hearts_without_hp_loss():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack", target_id="goblin_01"),
        dice=11,
    )

    assert result.changes == []
    assert result.state.enemy_hearts == 2
    assert result.state.player_hearts == 3
    assert result.state.round == 2
    assert result.state.outcome == "ongoing"
    assert result.state.trace[-1].kind == "player_attack_success"


def test_attack_failure_reduces_player_hearts_and_ignores_stats():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack", target_id="goblin_01"),
        dice=10,
    )

    assert result.state.enemy_hearts == 3
    assert result.state.player_hearts == 2
    assert result.state.trace[-1].kind == "player_attack_failure"


def test_defend_success_restores_heart_only_to_cap():
    graph = _graph()
    state = _started(graph).model_copy(update={"player_hearts": 2})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
        dice=11,
    )

    assert result.state.player_hearts == 3
    assert result.state.enemy_hearts == 3


def test_defend_failure_reduces_player_hearts():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
        dice=10,
    )

    assert result.state.player_hearts == 2
    assert result.state.enemy_hearts == 3


def test_flee_success_ends_without_hp_loss():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="flee"),
        dice=11,
    )

    assert result.changes == []
    assert result.state.outcome == "fled"
    assert result.state.player_hearts == 3


def test_flee_failure_reduces_player_hearts():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="flee"),
        dice=10,
    )

    assert result.state.outcome == "ongoing"
    assert result.state.player_hearts == 2


def test_social_success_and_failure_match_heart_rules():
    graph = _graph()
    state = _started(graph)

    success = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="social", target_id="goblin_01"),
        dice=11,
    )
    failure = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="social", target_id="goblin_01"),
        dice=10,
    )

    assert success.state.enemy_hearts == 2
    assert failure.state.player_hearts == 2


def test_victory_marks_enemy_defeated_without_forced_round_limit():
    graph = _graph()
    state = _started(graph).model_copy(update={"enemy_hearts": 1, "round": 12})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack", target_id="goblin_01"),
        dice=11,
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.round == 13
    assert result.state.outcome == "victory"
    assert changed.nodes["goblin_01"].properties["defeat_mode"] == "unconscious"
    assert "defeated" in changed.nodes["goblin_01"].properties["status"]


def test_defeat_reduces_real_hp_by_enemy_remaining_hearts():
    graph = _graph()
    state = _started(graph).model_copy(update={"player_hearts": 1, "enemy_hearts": 2})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack", target_id="goblin_01"),
        dice=10,
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.outcome == "defeat"
    assert changed.nodes["player_01"].properties["hp"] == 3
    assert changed.nodes["player_01"].properties["defeat_mode"] == "downed"
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/engines/test_graph_combat.py -q
```

Expected: failures mentioning missing `active_enemy_id`, missing `player_hearts`, invalid action kind `social`, and `plan_combat_exchange()` not accepting `dice`.

- [ ] **Step 3: Update combat domain models**

In `server/src/game/domain/combat.py`, replace the model definitions with:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CombatActionKind = Literal["attack", "defend", "flee", "social"]
CombatOutcome = Literal["ongoing", "victory", "defeat", "fled"]
CombatSide = Literal["player", "enemy"]
CombatSupportKind = Literal["skill", "item"]


class GraphCombatTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    actor_id: str | None = None
    target_id: str | None = None
    state: str | None = None


class GraphCombatAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CombatActionKind
    target_id: str | None = None
    support_id: str | None = None
    support_kind: CombatSupportKind | None = None


class GraphCombatState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    player_id: str
    enemy_ids: list[str]
    active_enemy_id: str
    participant_ids: list[str]
    sides: dict[str, CombatSide]
    round: int = Field(default=1, ge=1)
    player_hearts: int = Field(default=3, ge=0, le=3)
    enemy_hearts: int = Field(default=3, ge=0, le=3)
    last_action: CombatActionKind | None = None
    last_support_id: str | None = None
    last_support_kind: CombatSupportKind | None = None
    trace: list[GraphCombatTraceEvent] = Field(default_factory=list)
    outcome: CombatOutcome = "ongoing"
```

- [ ] **Step 4: Implement heart start, DC helpers, and action outcome**

In `server/src/game/engines/graph_combat.py`, keep existing imports for graph changes and add `RemoveEdgeChange`. Replace `plan_combat_start`, `plan_combat_exchange`, and add these helpers:

```python
import random
from dataclasses import dataclass
from typing import Literal

from src.game.domain.combat import GraphCombatAction, GraphCombatState, GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphChange, GraphNode, RemoveEdgeChange, SetNodePropertyChange
from src.game.domain.graph_query import edges_from, location_of

BASE_COMBAT_DC = 11
MIN_COMBAT_DC = 6
MAX_COMBAT_DC = 18
STARTING_HEARTS = 3

SupportTemplate = Literal["dc_down", "extra_heart_damage", "prevent_heart_loss", "escape_boost"]


@dataclass(frozen=True)
class _Support:
    node_id: str
    kind: str
    template: SupportTemplate
    bonus: int
    mp_cost: int = 0
    consumed_edge_id: str | None = None


def _combat_dc(player: GraphNode, enemy: GraphNode, support: _Support | None) -> int:
    dc = BASE_COMBAT_DC + _level(enemy) - _level(player)
    if support is not None and support.template in {"dc_down", "escape_boost"}:
        dc -= support.bonus
    return max(MIN_COMBAT_DC, min(MAX_COMBAT_DC, dc))


def _roll_success(dice: int, dc: int) -> bool:
    if dice < 1 or dice > 20:
        raise GraphCombatError("dice must be between 1 and 20")
    return dice >= dc


def _level(node: GraphNode) -> int:
    value = node.properties.get("level", 1)
    if not isinstance(value, int):
        raise GraphCombatError(f"missing numeric property {node.id}.level")
    return max(1, value)
```

`plan_combat_start()` should build `active_enemy_id=enemy_id`, `player_hearts=3`, and `enemy_hearts=3`.

`plan_combat_exchange()` should:

```python
def plan_combat_exchange(
    graph: Graph,
    state: GraphCombatState,
    actor_id: str,
    action: GraphCombatAction,
    *,
    dice: int | None = None,
) -> GraphCombatResult:
    if state.outcome != "ongoing":
        raise GraphCombatError(f"combat is already resolved: {state.outcome}")
    if actor_id != state.player_id:
        raise GraphCombatError("only the player actor can drive this combat slice")

    player = _require_character(graph, state.player_id)
    _require_can_fight(player)
    target_id = action.target_id or state.active_enemy_id
    enemy = _require_enemy(graph, state, target_id)
    _require_can_fight(enemy)

    support = _resolve_support(graph, player.id, action)
    changes: list[GraphChange] = []
    if support is not None and support.mp_cost:
        mp = _int_prop(player, "mp")
        if mp < support.mp_cost:
            raise GraphCombatError(f"not enough mp: {mp} < {support.mp_cost}")
        changes.append(_set(player.id, "mp", mp - support.mp_cost))
    if support is not None and support.consumed_edge_id is not None:
        changes.append(RemoveEdgeChange(type="remove_edge", edge_id=support.consumed_edge_id))

    rolled = dice if dice is not None else random.randint(1, 20)
    success = _roll_success(rolled, _combat_dc(player, enemy, support))
    next_state = state.model_copy(deep=True)
    next_state.last_action = action.kind
    next_state.last_support_id = action.support_id
    next_state.last_support_kind = action.support_kind
    next_state.round = state.round + 1

    _apply_heart_result(next_state, action, success, support, actor_id, enemy.id)
    _apply_terminal_changes(changes, next_state, player, enemy)
    return GraphCombatResult(changes=changes, state=next_state)
```

Implement `_apply_heart_result()` so:

- attack/social success: `enemy_hearts -= 1`
- attack/social failure: `player_hearts -= 1`
- defend success: `player_hearts += 1`, capped at 3
- defend failure: `player_hearts -= 1`
- flee success: outcome `fled`
- flee failure: `player_hearts -= 1`
- `extra_heart_damage` adds one additional enemy heart loss only after attack success
- `prevent_heart_loss` restores one failed player heart loss only after an action failure

Implement `_apply_terminal_changes()` so:

- enemy hearts 0 marks enemy `defeat_mode="unconscious"` and status includes `defeated`
- player hearts 0 subtracts `enemy_hearts` from real HP, floors at 0, sets `defeat_mode="downed"`, and status includes `downed`
- no forced round terminal logic remains

- [ ] **Step 5: Implement support resolution**

In `server/src/game/engines/graph_combat.py`, add:

```python
def _resolve_support(
    graph: Graph,
    player_id: str,
    action: GraphCombatAction,
) -> _Support | None:
    if action.support_id is None and action.support_kind is None:
        return None
    if action.support_id is None or action.support_kind is None:
        raise GraphCombatError("support_id and support_kind must be set together")
    if action.support_kind == "skill":
        return _resolve_skill_support(graph, player_id, action)
    return _resolve_item_support(graph, player_id, action)


def _resolve_skill_support(
    graph: Graph,
    player_id: str,
    action: GraphCombatAction,
) -> _Support:
    skill = graph.nodes.get(action.support_id or "")
    if skill is None:
        raise GraphCombatError(f"missing skill: {action.support_id}")
    if skill.type != "skill":
        raise GraphCombatError(f"node is not a skill: {action.support_id}")
    if not any(edge.to_node_id == skill.id for edge in edges_from(graph, player_id, "knows_skill")):
        raise GraphCombatError(f"{player_id} does not know skill: {skill.id}")
    _require_support_action(skill.properties, "action", action.kind, skill.id)
    template = _support_template(skill.properties.get("effect_template"), skill.id)
    return _Support(
        node_id=skill.id,
        kind="skill",
        template=template,
        bonus=_bounded_bonus(skill.properties.get("support_bonus"), skill.id),
        mp_cost=_int_value(skill.properties.get("mp_cost"), default=0),
    )


def _resolve_item_support(
    graph: Graph,
    player_id: str,
    action: GraphCombatAction,
) -> _Support:
    item = graph.nodes.get(action.support_id or "")
    if item is None:
        raise GraphCombatError(f"missing item: {action.support_id}")
    if item.type != "item":
        raise GraphCombatError(f"node is not an item: {action.support_id}")
    carry_edge = None
    for edge in edges_from(graph, player_id, "carries"):
        if edge.to_node_id == item.id:
            carry_edge = edge
            break
    equipped = any(edge.to_node_id == item.id for edge in edges_from(graph, player_id, "equips"))
    if carry_edge is None and not equipped:
        raise GraphCombatError(f"item is not available to {player_id}: {item.id}")
    _require_support_action(item.properties, "support_action", action.kind, item.id)
    template = _support_template(item.properties.get("effect_template"), item.id)
    consumed_edge_id = carry_edge.id if item.properties.get("consumable") is True and carry_edge is not None else None
    return _Support(
        node_id=item.id,
        kind="item",
        template=template,
        bonus=_bounded_bonus(item.properties.get("support_bonus"), item.id),
        consumed_edge_id=consumed_edge_id,
    )
```

Add helper validation:

```python
def _require_support_action(props: dict, key: str, expected: str, node_id: str) -> None:
    value = props.get(key)
    if value != expected:
        raise GraphCombatError(f"support {node_id} does not support {expected}")


def _support_template(value: object, node_id: str) -> SupportTemplate:
    if value in {"dc_down", "extra_heart_damage", "prevent_heart_loss", "escape_boost"}:
        return value
    raise GraphCombatError(f"unsupported support template for {node_id}: {value}")


def _bounded_bonus(value: object, node_id: str) -> int:
    if not isinstance(value, int):
        raise GraphCombatError(f"missing support_bonus: {node_id}")
    if value < 0 or value > 4:
        raise GraphCombatError(f"support_bonus out of range for {node_id}: {value}")
    return value
```

- [ ] **Step 6: Add support tests**

Add these tests to `server/tests/game/engines/test_graph_combat.py`:

```python
def test_dc_uses_level_difference_support_bonus_and_clamp():
    high_enemy = _character("goblin_01", level=20)
    graph = _graph(enemy=high_enemy, include_skill=True)
    state = _started(graph)

    fail_without_support = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack", target_id="goblin_01"),
        dice=17,
    )
    success_with_support = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            target_id="goblin_01",
            support_id="fireball",
            support_kind="skill",
        ),
        dice=18,
    )

    assert fail_without_support.state.player_hearts == 2
    assert success_with_support.state.enemy_hearts == 2


def test_skill_support_spends_mp_and_requires_matching_action():
    graph = _graph(include_skill=True)
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            target_id="goblin_01",
            support_id="fireball",
            support_kind="skill",
        ),
        dice=9,
    )
    changed = _apply_all(graph, result.changes)

    assert changed.nodes["player_01"].properties["mp"] == 3
    assert result.state.enemy_hearts == 2

    with pytest.raises(GraphCombatError, match="does not support defend"):
        plan_combat_exchange(
            graph,
            state,
            "player_01",
            GraphCombatAction(kind="defend", support_id="fireball", support_kind="skill"),
            dice=20,
        )


def test_item_support_consumes_consumable_and_cannot_stack_with_skill():
    graph = _graph(include_item=True)
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            target_id="goblin_01",
            support_id="throwing_knife",
            support_kind="item",
        ),
        dice=8,
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.enemy_hearts == 2
    assert "carries:player_01:throwing_knife" not in changed.edges


def test_extra_heart_damage_and_prevent_heart_loss_are_post_roll_effects():
    burst_graph = _graph(include_burst_skill=True)
    state = _started(burst_graph)

    burst = plan_combat_exchange(
        burst_graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            target_id="goblin_01",
            support_id="burst",
            support_kind="skill",
        ),
        dice=11,
    )
    burst_fail = plan_combat_exchange(
        burst_graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            target_id="goblin_01",
            support_id="burst",
            support_kind="skill",
        ),
        dice=10,
    )

    guard_graph = _graph(include_guard_skill=True)
    guard = plan_combat_exchange(
        guard_graph,
        _started(guard_graph),
        "player_01",
        GraphCombatAction(kind="defend", support_id="guard", support_kind="skill"),
        dice=10,
    )

    assert burst.state.enemy_hearts == 1
    assert burst_fail.state.enemy_hearts == 3
    assert guard.state.player_hearts == 3
```

Extend `_graph()` in the test file with `include_item`, `include_burst_skill`, and `include_guard_skill` branches that add the corresponding node plus `carries` or `knows_skill` edge.

- [ ] **Step 7: Verify combat engine tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/engines/test_graph_combat.py -q
```

Expected: all tests in `test_graph_combat.py` pass.

- [ ] **Step 8: Commit combat engine**

Run:

```powershell
git add server/src/game/domain/combat.py server/src/game/engines/graph_combat.py server/tests/game/engines/test_graph_combat.py
git commit -m "Implement heart combat engine"
```

Expected: commit succeeds.

## Task 2: Runtime Combat Dispatch And Migration

**Files:**
- Modify: `server/src/game/runtime/combat.py`
- Modify: `server/src/game/runtime/dispatch.py`
- Modify: `server/src/db/graph_progress_rows.py`
- Test: `server/tests/game/runtime/test_graph_combat_dispatch.py`
- Test: `server/tests/db/test_graph_progress_rows.py`

- [ ] **Step 1: Rewrite runtime combat dispatch tests for heart outcomes**

In `server/tests/game/runtime/test_graph_combat_dispatch.py`, update `_character()` and `_skill()` to match Task 1 fixtures. Replace HP-damage assertions with heart assertions:

```python
def test_attack_starts_combat_applies_exchange_and_stores_progress():
    runtime = _runtime()

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
        dice=11,
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    state = result.runtime.progress.graph_combat_state
    assert state is not None
    assert state.enemy_hearts == 2
    assert state.player_hearts == 3
    assert result.runtime.graph.nodes["goblin_01"].properties["hp"] == 5
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 5


def test_attack_with_skill_support_starts_combat_and_deducts_mp():
    runtime = _runtime(include_skill=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="fireball"),
        dice=9,
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 3
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 2


def test_attack_with_item_support_consumes_item():
    runtime = _runtime(include_item=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="throwing_knife"),
        dice=8,
    )

    assert result.runtime.progress.graph_combat_state.enemy_hearts == 2
    assert "carries:player_01:throwing_knife" not in result.runtime.graph.edges


def test_defend_and_social_actions_in_existing_combat():
    runtime = _runtime(graph_combat_state=_ongoing_state(player_hearts=2))

    defend = dispatch_graph_combat_action(runtime, Action(verb="pass"), dice=11)
    social = dispatch_graph_combat_action(runtime, Action(verb="speak", what="goblin_01", how="hostile"), dice=11)

    assert defend.runtime.progress.graph_combat_state.player_hearts == 3
    assert social.runtime.progress.graph_combat_state.enemy_hearts == 2


def test_player_defeat_clears_combat_and_applies_hp_loss():
    runtime = _runtime(graph_combat_state=_ongoing_state(player_hearts=1, enemy_hearts=2))

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
        dice=10,
    )

    assert result.outcome == "defeat"
    assert result.runtime.progress.graph_combat_state is None
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 3
```

- [ ] **Step 2: Run runtime dispatch tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/runtime/test_graph_combat_dispatch.py -q
```

Expected: failures because `dispatch_graph_combat_action()` has no `dice` parameter and `_combat_action_from_action()` does not produce support metadata or social actions.

- [ ] **Step 3: Add dice injection and support mapping**

In `server/src/game/runtime/combat.py`, change the dispatch signature:

```python
def dispatch_graph_combat_action(
    runtime: GameRuntimeState,
    action: Action,
    *,
    dice: int | None = None,
) -> GraphCombatDispatchResult:
```

Pass `dice=dice` into `plan_combat_exchange()`.

Replace `_combat_action_from_action()` with:

```python
def _combat_action_from_action(
    graph: Graph,
    action: Action,
    *,
    in_combat: bool,
) -> GraphCombatAction:
    if action.verb == "attack":
        support_id, support_kind = _support_from_id(graph, _single(action.with_))
        return GraphCombatAction(
            kind="attack",
            target_id=_single(action.what),
            support_id=support_id,
            support_kind=support_kind,
        )
    if action.verb == "cast":
        skill_id = _single(action.with_) or _single(action.what)
        return GraphCombatAction(
            kind="attack",
            target_id=_single(action.to),
            support_id=skill_id,
            support_kind="skill" if skill_id is not None else None,
        )
    if in_combat and action.verb == "move" and action.how in ("flee", "hasty"):
        support_id, support_kind = _support_from_id(graph, _single(action.with_))
        return GraphCombatAction(kind="flee", support_id=support_id, support_kind=support_kind)
    if in_combat and action.verb == "pass":
        support_id, support_kind = _support_from_id(graph, _single(action.with_))
        return GraphCombatAction(kind="defend", support_id=support_id, support_kind=support_kind)
    if in_combat and action.verb == "speak":
        support_id, support_kind = _support_from_id(graph, _single(action.with_))
        return GraphCombatAction(
            kind="social",
            target_id=_single(action.to) or _single(action.what),
            support_id=support_id,
            support_kind=support_kind,
        )
    raise GraphCombatDispatchError(f"unsupported graph combat action: {action.verb}")
```

Add:

```python
def _support_from_id(graph: Graph, node_id: str | None) -> tuple[str | None, str | None]:
    if node_id is None:
        return None, None
    node = graph.nodes.get(node_id)
    if node is None:
        return node_id, None
    if node.type == "skill":
        return node_id, "skill"
    if node.type == "item":
        return node_id, "item"
    return node_id, None
```

- [ ] **Step 4: Route in-combat speak through combat**

In `server/src/game/runtime/dispatch.py`, keep the existing broad in-combat route and update `_dispatch_combat()` to accept no dice in production:

```python
def _dispatch_combat(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphActionDispatchResult:
    try:
        combat = dispatch_graph_combat_action(runtime, action)
    except GraphCombatDispatchError as exc:
        raise GraphActionDispatchError(str(exc)) from exc
    ...
```

No code change is needed for normal production dice in this file. Add a regression test in `server/tests/game/runtime/test_graph_action_dispatch.py` if there is no existing coverage:

```python
def test_dispatch_routes_speak_to_combat_when_combat_is_active():
    runtime = _runtime_with_combat()
    result = dispatch_graph_action(runtime, Action(verb="speak", what="goblin_01", how="hostile"))

    assert result.kind == "combat"
```

- [ ] **Step 5: Add old combat progress migration test**

Create `server/tests/db/test_graph_progress_rows.py`:

```python
from src.db.graph_progress_rows import GameProgressRow, progress_from_row


def test_progress_from_row_clears_old_format_graph_combat_state():
    row = GameProgressRow(
        game_id="game-1",
        progress={
            "player_id": "player_01",
            "graph_combat_state": {
                "location_id": "town_gate",
                "player_id": "player_01",
                "enemy_ids": ["goblin_01"],
                "participant_ids": ["player_01", "goblin_01"],
                "sides": {"player_01": "player", "goblin_01": "enemy"},
                "round": 2,
                "outcome": "ongoing",
            },
        },
    )

    progress = progress_from_row(row)

    assert progress.graph_combat_state is None
```

- [ ] **Step 6: Implement old combat progress clearing**

In `server/src/db/graph_progress_rows.py`, update `progress_from_row()`:

```python
def progress_from_row(row: GameProgressRow) -> GameProgress:
    payload = dict(row.progress)
    state = payload.get("graph_combat_state")
    if isinstance(state, dict) and (
        "player_hearts" not in state
        or "enemy_hearts" not in state
        or "active_enemy_id" not in state
    ):
        payload["graph_combat_state"] = None
    return GameProgress(game_id=row.game_id, **payload)
```

- [ ] **Step 7: Verify runtime dispatch and migration tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/runtime/test_graph_combat_dispatch.py server/tests/db/test_graph_progress_rows.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit runtime dispatch**

Run:

```powershell
git add server/src/game/runtime/combat.py server/src/game/runtime/dispatch.py server/src/db/graph_progress_rows.py server/tests/game/runtime/test_graph_combat_dispatch.py server/tests/db/test_graph_progress_rows.py
git commit -m "Wire heart combat runtime dispatch"
```

Expected: commit succeeds.

## Task 3: Growth Scale, Skill Limits, And Level-Up Choices

**Files:**
- Modify: `server/src/game/rules/config.py`
- Modify: `server/src/game/engines/growth.py`
- Modify: `server/src/game/engines/graph_growth.py`
- Modify: `server/src/game/runtime/level_up.py`
- Modify: `server/src/game/runtime/cards.py`
- Modify: `server/src/wire/graph_hero.py`
- Test: `server/tests/game/engines/test_graph_growth.py`
- Test: `server/tests/game/runtime/test_graph_level_up.py`

- [ ] **Step 1: Update growth tests for the 10-scale**

In `server/tests/game/engines/test_graph_growth.py`, replace the level/stat assumptions with HP/MP/skill choice tests:

```python
def _character(**properties) -> GraphNode:
    base = {
        "level": 1,
        "xp_pool": 1,
        "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
        "hp": 5,
        "max_hp": 5,
        "mp": 5,
        "max_mp": 5,
        "status": [],
    }
    base.update(properties)
    return GraphNode(id="player_01", type="character", properties=base)


def test_level_up_can_raise_max_hp_to_cap_10():
    graph = _graph()
    result = plan_level_up(graph, "player_01", growth={"kind": "max_hp"})
    changed = _apply_all(graph, result.changes)
    player = changed.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["max_hp"] == 6
    assert player["hp"] == 6
    assert player["max_mp"] == 5


def test_level_up_can_raise_max_mp_to_cap_10():
    graph = _graph()
    result = plan_level_up(graph, "player_01", growth={"kind": "max_mp"})
    changed = _apply_all(graph, result.changes)
    player = changed.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["max_hp"] == 5
    assert player["max_mp"] == 6
    assert player["mp"] == 6


def test_level_up_rejects_resource_cap_and_max_level():
    with pytest.raises(GraphGrowthError, match="max_hp already at cap"):
        plan_level_up(_graph(_character(max_hp=10)), "player_01", growth={"kind": "max_hp"})

    with pytest.raises(GraphGrowthError, match="already at max level 10"):
        plan_level_up(_graph(_character(level=10, xp_pool=10)), "player_01", growth={"kind": "max_mp"})
```

Add skill learn and upgrade tests:

```python
def test_skill_learn_rejects_more_than_three_known_skills():
    graph = _graph()
    for index in range(3):
        skill_id = f"skill_{index}"
        graph.nodes[skill_id] = GraphNode(id=skill_id, type="skill", properties={})
        graph.edges[f"knows_skill:learned:player_01:{skill_id}"] = GraphEdge(
            id=f"knows_skill:learned:player_01:{skill_id}",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id=skill_id,
            properties={"source": "learned"},
        )

    with pytest.raises(GraphGrowthError, match="skill slots full"):
        plan_skill_learn(graph, "player_01", "fireball")


def test_skill_upgrade_increments_tier_to_cap_3():
    graph = _graph()
    graph.edges["knows_skill:learned:player_01:fireball"] = GraphEdge(
        id="knows_skill:learned:player_01:fireball",
        type="knows_skill",
        from_node_id="player_01",
        to_node_id="fireball",
        properties={"source": "learned", "tier": 1},
    )

    result = plan_skill_upgrade(graph, "player_01", "fireball")
    changed = _apply_all(graph, result.changes)

    assert changed.edges["knows_skill:learned:player_01:fireball"].properties["tier"] == 2

    changed.edges["knows_skill:learned:player_01:fireball"].properties["tier"] = 3
    with pytest.raises(GraphGrowthError, match="already at tier 3"):
        plan_skill_upgrade(changed, "player_01", "fireball")
```

- [ ] **Step 2: Run growth tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/engines/test_graph_growth.py -q
```

Expected: failures because `plan_level_up()` still requires `stat_up`, max level is 20, and `plan_skill_upgrade()` does not exist.

- [ ] **Step 3: Change rules and shared growth formulas**

In `server/src/game/rules/config.py`, set:

```python
class GrowthConfig(_F):
    base_xp: int = 1
    max_level: int = 10
    ...
```

In `server/src/game/engines/growth.py`, replace HP/MP formulas:

```python
def xp_for_next_level(level: int) -> int:
    if level >= RULES.growth.max_level:
        return 0
    return max(level, 1)


def calc_max_hp(level: int, con: int | None = None) -> int:
    return min(10, 4 + max(level, 1))


def calc_max_mp(level: int, int_: int | None = None) -> int:
    return min(10, 4 + max(level, 1))
```

- [ ] **Step 4: Implement growth choices and skill upgrade**

In `server/src/game/engines/graph_growth.py`, add:

```python
from typing import Literal, TypedDict


class LevelGrowthChoice(TypedDict):
    kind: Literal["max_hp", "max_mp"]
```

Change `plan_level_up()` signature:

```python
def plan_level_up(
    graph: Graph,
    character_id: str,
    growth: LevelGrowthChoice,
) -> GraphGrowthResult:
```

Add a shared level progression helper:

```python
def _plan_level_progression(graph: Graph, character_id: str) -> tuple[GraphNode, list[GraphChange]]:
    character = _require_character(graph, character_id)
    level = _int_prop(character, "level")
    if level >= RULES.growth.max_level:
        raise GraphGrowthError(f"already at max level {RULES.growth.max_level}")
    cost = xp_for_next_level(level)
    xp_pool = _int_prop(character, "xp_pool")
    if xp_pool < cost:
        raise GraphGrowthError(f"not enough xp: have {xp_pool}, need {cost}")
    return character, [
        _set(character_id, "xp_pool", xp_pool - cost),
        _set(character_id, "level", level + 1),
    ]
```

Implementation body:

```python
character, changes = _plan_level_progression(graph, character_id)
if growth["kind"] == "max_hp":
    max_hp = _int_prop(character, "max_hp")
    if max_hp >= 10:
        raise GraphGrowthError("max_hp already at cap 10")
    changes.extend([
        _set(character_id, "max_hp", max_hp + 1),
        _set(character_id, "hp", min(10, _int_prop(character, "hp") + 1)),
    ])
elif growth["kind"] == "max_mp":
    max_mp = _int_prop(character, "max_mp")
    if max_mp >= 10:
        raise GraphGrowthError("max_mp already at cap 10")
    changes.extend([
        _set(character_id, "max_mp", max_mp + 1),
        _set(character_id, "mp", min(10, _int_prop(character, "mp") + 1)),
    ])
else:
    raise GraphGrowthError(f"unknown growth kind: {growth['kind']}")
return GraphGrowthResult(changes=changes, character_id=character_id, kind="level_up")
```

Import `SetEdgePropertyChange` from `src.game.domain.graph`. Then add:

```python
def plan_skill_upgrade(
    graph: Graph,
    character_id: str,
    skill_id: str,
) -> GraphGrowthResult:
    _require_character(graph, character_id)
    edge = None
    for candidate in edges_from(graph, character_id, "knows_skill"):
        if candidate.to_node_id == skill_id:
            edge = candidate
            break
    if edge is None:
        raise GraphGrowthError(f"character does not know skill: {skill_id}")
    tier = edge.properties.get("tier", 1)
    if not isinstance(tier, int):
        raise GraphGrowthError(f"invalid skill tier: {skill_id}")
    if tier >= 3:
        raise GraphGrowthError(f"skill already at tier 3: {skill_id}")
    return GraphGrowthResult(
        changes=[
            SetEdgePropertyChange(
                type="set_edge_property",
                edge_id=edge.id,
                path="tier",
                value=tier + 1,
            )
        ],
        character_id=character_id,
        kind="skill_upgrade",
    )
```

Update `GrowthKind` to include `"skill_upgrade"`.

Add `plan_skill_level_up()` so skill learn/upgrade choices also consume XP and increase level exactly once:

```python
def plan_skill_level_up(
    graph: Graph,
    character_id: str,
    *,
    learn_skill_id: str | None = None,
    upgrade_skill_id: str | None = None,
) -> GraphGrowthResult:
    if (learn_skill_id is None) == (upgrade_skill_id is None):
        raise GraphGrowthError("exactly one skill level-up choice is required")
    _, level_changes = _plan_level_progression(graph, character_id)
    progressed = graph
    for change in level_changes:
        progressed = apply_graph_change(progressed, change)
    if learn_skill_id is not None:
        skill_result = plan_skill_learn(progressed, character_id, learn_skill_id)
    else:
        skill_result = plan_skill_upgrade(progressed, character_id, upgrade_skill_id or "")
    return GraphGrowthResult(
        changes=[*level_changes, *skill_result.changes],
        character_id=character_id,
        kind=skill_result.kind,
    )
```

Import `apply_graph_change` from `src.game.domain.graph` for the temporary validation copy.

In `plan_skill_learn()`, count `knows_skill` edges and reject `>= 3`. Add `tier: 1` to learned edge properties:

```python
known = edges_from(graph, character_id, "knows_skill")
if len(known) >= 3:
    raise GraphGrowthError("skill slots full")
...
properties={"source": "learned", "tier": 1}
```

- [ ] **Step 5: Update runtime level-up API**

In `server/src/game/runtime/level_up.py`, replace `stat_up`/`skill_id` with a single growth request:

```python
async def run_graph_level_up(
    repo: GraphRepo,
    game_id: str,
    *,
    growth: dict[str, str],
    scenario_repo: ScenarioRepo | None = None,
) -> GraphLevelUpResult:
```

Map:

```python
kind = growth.get("kind")
if kind in {"max_hp", "max_mp"}:
    result = plan_level_up(runtime.graph, runtime.progress.player_id, {"kind": kind})
    changes = result.changes
    skill_id = None
elif kind == "learn_skill":
    skill_id = growth.get("skill_id")
    if not isinstance(skill_id, str) or not skill_id:
        raise GraphLevelUpError("skill_id is required")
    result = plan_skill_level_up(
        runtime.graph,
        runtime.progress.player_id,
        learn_skill_id=skill_id,
    )
    changes = result.changes
elif kind == "upgrade_skill":
    skill_id = growth.get("skill_id")
    if not isinstance(skill_id, str) or not skill_id:
        raise GraphLevelUpError("skill_id is required")
    result = plan_skill_level_up(
        runtime.graph,
        runtime.progress.player_id,
        upgrade_skill_id=skill_id,
    )
    changes = result.changes
else:
    raise GraphLevelUpError(f"unknown growth kind: {kind}")
```

In `server/src/game/runtime/cards.py`, replace `build_graph_level_up_card()` with a growth-kind card helper that does not mention stat labels. Use concrete card texts:

```python
def build_graph_level_up_card(
    runtime: GameRuntimeState,
    growth_label: str,
    log_id: int,
) -> ActLogEntry:
    player = runtime.graph.nodes[runtime.progress.player_id]
    return ActLogEntry(
        id=log_id,
        kind="act",
        text=render(
            "runtime.card.level_up",
            runtime.progress.locale,
            actor=node_label(runtime.content, player),
            level=_int_property(player, "level"),
            growth=growth_label,
            max_hp=_int_property(player, "max_hp"),
            max_mp=_int_property(player, "max_mp"),
        ),
    )
```

Update `server/src/locale/catalog/runtime.toml` level-up string to accept `{growth}`.

- [ ] **Step 6: Update runtime level-up tests**

In `server/tests/game/runtime/test_graph_level_up.py`, replace `stat_up` calls:

```python
result = await run_graph_level_up(repo, "game-1", growth={"kind": "max_hp"})
```

Add tests:

```python
async def test_run_graph_level_up_consumes_current_level_xp_and_raises_hp(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_level_up(repo, "game-1", growth={"kind": "max_hp"})
    saved_graph = await repo.load_graph("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["max_hp"] == 6
    assert result.front_state.hero.level == 2


async def test_run_graph_level_up_can_upgrade_known_skill(tmp_path):
    repo = await _repo(tmp_path, known_skill=True)

    await run_graph_level_up(repo, "game-1", growth={"kind": "upgrade_skill", "skill_id": "fireball"})
    saved_graph = await repo.load_graph("game-1")

    edge = saved_graph.edges["knows_skill:learned:player_01:fireball"]
    assert edge.properties["tier"] == 2
```

- [ ] **Step 7: Update hero payload level-up availability**

In `server/src/wire/graph_hero.py`, `xp_for_next_level(10)` returns 0. Set:

```python
can_level_up=exp_max > 0 and exp >= exp_max,
```

Keep `exp_max=0` at cap so the client progress bar can show capped state.

- [ ] **Step 8: Verify growth and level-up tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/engines/test_graph_growth.py server/tests/game/runtime/test_graph_level_up.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit growth changes**

Run:

```powershell
git add server/src/game/rules/config.py server/src/game/engines/growth.py server/src/game/engines/graph_growth.py server/src/game/runtime/level_up.py server/src/game/runtime/cards.py server/src/wire/graph_hero.py server/src/locale/catalog/runtime.toml server/tests/game/engines/test_graph_growth.py server/tests/game/runtime/test_graph_level_up.py
git commit -m "Implement ten-scale skill growth"
```

Expected: commit succeeds.

## Task 4: Seed Defaults And Starting Skill Migration

**Files:**
- Modify: `server/src/game/seed/graph_seed.py`
- Modify: scenario seed files under `scenarios/`
- Test: `server/tests/game/seed/test_graph_seed.py`

- [ ] **Step 1: Add seed tests for HP/MP 5 and starting skill**

In `server/tests/game/seed/test_graph_seed.py`, add:

```python
def test_player_starts_with_five_hp_mp_and_one_racial_skill():
    bundle = build_seed_graph(
        profile_name="dev",
        player=PlayerInput(name="테스터", race_id="human", gender="male"),
        races={"human": {"id": "human", "racial_skill_ids": ["starter_slash"]}},
        locations={"town_gate": {"id": "town_gate"}},
        items={},
        skills={"starter_slash": {"id": "starter_slash", "kind": "support", "action": "attack", "effect_template": "dc_down", "mp_cost": 1, "support_bonus": 1}},
        npcs={},
        quests={},
        chapters={},
        start={"start_location_id": "town_gate"},
        template={"id": "player_01", "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10}},
        game_id="game-1",
    )

    player = bundle.graph.nodes["player_01"].properties
    assert player["level"] == 1
    assert player["hp"] == 5
    assert player["max_hp"] == 5
    assert player["mp"] == 5
    assert player["max_mp"] == 5
    assert "knows_skill:racial:player_01:starter_slash" in bundle.graph.edges
```

- [ ] **Step 2: Run seed test and confirm failure**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/seed/test_graph_seed.py::test_player_starts_with_five_hp_mp_and_one_racial_skill -q
```

Expected: failure if current formulas still produce large HP/MP or if test helper imports need updating.

- [ ] **Step 3: Update `_build_player()` seed defaults**

In `server/src/game/seed/graph_seed.py`, after Task 3 formulas are changed, keep:

```python
max_hp = calc_max_hp(level, stats["body"])
max_mp = calc_max_mp(level, stats["mind"])
```

This now returns 5 at level 1. Confirm `_build_player()` preserves `racial_skill_ids` from the selected race. No extra starting-skill logic is needed if every playable race/profile supplies one racial skill.

- [ ] **Step 4: Update scenario skills to support templates**

For each skill record in `scenarios/**/skills.*` or `scenarios/**/skills/*.json`, convert attack damage fields into support fields:

```json
{
  "id": "starter_slash",
  "name": "훈련 일격",
  "kind": "support",
  "action": "attack",
  "effect_template": "dc_down",
  "mp_cost": 1,
  "support_bonus": 1,
  "tier": 1,
  "tags": ["starter", "melee"]
}
```

Use `rg -n "\"power\"|mp_cost|effect_template|racial_skill_ids" scenarios server/src/game/seed` to find records. Remove `power` from converted combat support skills.

- [ ] **Step 5: Verify seed suite**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/seed/test_graph_seed.py server/tests/game/seed/test_init_graph.py -q
```

Expected: selected seed tests pass.

- [ ] **Step 6: Commit seed changes**

Run:

```powershell
git add server/src/game/seed/graph_seed.py server/tests/game/seed/test_graph_seed.py scenarios
git commit -m "Seed ten-scale starting skills"
```

Expected: commit succeeds.

## Task 5: Wire Payloads, Narration Context, And Client Hearts

**Files:**
- Modify: `server/src/wire/models/graph.py`
- Modify: `server/src/wire/graph_combat.py`
- Modify: `server/src/llm/context/graph_combat.py`
- Modify: `client/services/wire.ts`
- Modify: `client/services/graphAdapter.ts`
- Modify: `client/logic/combat/types.ts`
- Modify: `client/logic/combat/actions.ts`
- Modify: `client/components/combat/CombatStrip.tsx`
- Test: `server/tests/wire/test_graph_to_front.py`
- Test: `server/tests/llm/context/test_graph_combat_context.py`
- Test: `client/services/__tests__/graphAdapter.test.ts`
- Test: `client/logic/combat/__tests__/actions.test.ts`

- [ ] **Step 1: Add server wire/context tests**

In `server/tests/wire/test_graph_to_front.py`, add:

```python
def test_combat_payload_exposes_hearts():
    runtime = _runtime_with_combat_state(player_hearts=2, enemy_hearts=1)

    front = graph_to_front_state(runtime)

    assert front.combat is not None
    assert front.combat.player_hearts.current == 2
    assert front.combat.player_hearts.maximum == 3
    assert front.combat.enemy_hearts.current == 1
    assert front.combat.enemy_hearts.maximum == 3
```

In `server/tests/llm/context/test_graph_combat_context.py`, add:

```python
def test_combat_context_exposes_hearts_not_damage_numbers():
    context = build_graph_combat_context(_graph(), _state(player_hearts=2, enemy_hearts=1))

    assert context.player_hearts == 2
    assert context.enemy_hearts == 1
    assert context.round >= 1
```

- [ ] **Step 2: Update server wire models**

In `server/src/wire/models/graph.py`, add:

```python
class GraphHeartPayload(_CamelModel):
    current: int
    maximum: int
```

Change `GraphCombatPayload`:

```python
class GraphCombatPayload(_CamelModel):
    round: int
    outcome: Literal["ongoing", "victory", "defeat", "fled"]
    player_hearts: GraphHeartPayload
    enemy_hearts: GraphHeartPayload
    active_enemy_id: str
    participants: list[GraphCombatParticipantPayload]
```

In `server/src/wire/graph_combat.py`, return:

```python
return GraphCombatPayload(
    round=state.round,
    outcome=state.outcome,
    player_hearts=GraphHeartPayload(current=state.player_hearts, maximum=3),
    enemy_hearts=GraphHeartPayload(current=state.enemy_hearts, maximum=3),
    active_enemy_id=state.active_enemy_id,
    participants=participants,
)
```

- [ ] **Step 3: Update LLM combat context**

In `server/src/llm/context/graph_combat.py`, change the field constraint:

```python
round: int = Field(ge=1)
player_hearts: int = Field(ge=0, le=3)
enemy_hearts: int = Field(ge=0, le=3)
```

And return those fields from `build_graph_combat_context()`.

- [ ] **Step 4: Update client wire and adapter tests**

In `client/services/__tests__/graphAdapter.test.ts`, add:

```ts
test('adapts combat hearts from graph payload', () => {
  const state = adaptGraphState({
    ...baseGraphState,
    combat: {
      round: 2,
      outcome: 'ongoing',
      playerHearts: { current: 2, maximum: 3 },
      enemyHearts: { current: 1, maximum: 3 },
      activeEnemyId: 'goblin_01',
      participants: [
        { id: 'player_01', name: '테스터', side: 'player', hp: resource(5, 5), mp: resource(3, 5) },
        { id: 'goblin_01', name: '고블린', side: 'enemy', hp: resource(5, 5), mp: null },
      ],
    },
  });

  expect(state.combat?.playerHearts.current).toBe(2);
  expect(state.combat?.enemyHearts.current).toBe(1);
  expect(state.combat?.enemies[0].name).toBe('고블린');
});
```

- [ ] **Step 5: Update client types and adapter**

In `client/services/wire.ts`, add:

```ts
export type GraphHeart = {
  current: number;
  maximum: number;
};
```

Update `GraphCombatState`:

```ts
export type GraphCombatState = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'fled';
  playerHearts: GraphHeart;
  enemyHearts: GraphHeart;
  activeEnemyId: string;
  participants: GraphCombatParticipant[];
};
```

In `client/logic/combat/types.ts`, replace the badge type:

```ts
export type CombatHeart = {
  current: number;
  maximum: number;
};

export type CombatEnemy = {
  id?: string;
  name: string;
  alive: boolean;
};

export type CombatBadge = {
  round: number;
  turnLabel: string;
  playerHearts: CombatHeart;
  enemyHearts: CombatHeart;
  enemies: CombatEnemy[];
};
```

In `client/services/graphAdapter.ts`, update `adaptCombat()`:

```ts
function adaptCombat(combat: GraphCombatState | null): FrontState['combat'] {
  if (combat === null) return null;
  return {
    round: combat.round,
    turnLabel: ko.combat.label,
    playerHearts: combat.playerHearts,
    enemyHearts: combat.enemyHearts,
    enemies: combat.participants
      .filter((participant) => participant.side === 'enemy')
      .map((enemy) => ({
        id: enemy.id,
        name: enemy.name,
        alive: enemy.id === combat.activeEnemyId && combat.enemyHearts.current > 0,
      })),
  };
}
```

- [ ] **Step 6: Update combat actions and strip**

In `client/logic/combat/actions.ts`, keep attack/defend/flee/social actions but make defend explicit:

```ts
{
  kind: 'graph_action',
  label: ko.combat.defend,
  graphAction: { verb: 'pass', how: 'defend' },
  textFallback: compose.defend(),
}
```

In `client/components/combat/CombatStrip.tsx`, replace the HP bar block with two heart counters:

```tsx
<View className="flex-row gap-3">
  <Text className="font-sans-semibold text-caption text-fg-default">
    내 하트 {combat.playerHearts.current}/{combat.playerHearts.maximum}
  </Text>
  <Text className="font-sans-semibold text-caption text-fg-default">
    적 하트 {combat.enemyHearts.current}/{combat.enemyHearts.maximum}
  </Text>
</View>
```

Remove `Bar` and `toneColor` imports if unused.

- [ ] **Step 7: Verify wire and client tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/wire/test_graph_to_front.py server/tests/llm/context/test_graph_combat_context.py -q
cd client
npm test -- --runInBand services/__tests__/graphAdapter.test.ts logic/combat/__tests__/actions.test.ts
```

Expected: selected server and client tests pass.

- [ ] **Step 8: Commit wire/client changes**

Run:

```powershell
git add server/src/wire/models/graph.py server/src/wire/graph_combat.py server/src/llm/context/graph_combat.py server/tests/wire/test_graph_to_front.py server/tests/llm/context/test_graph_combat_context.py client/services/wire.ts client/services/graphAdapter.ts client/logic/combat/types.ts client/logic/combat/actions.ts client/components/combat/CombatStrip.tsx client/services/__tests__/graphAdapter.test.ts client/logic/combat/__tests__/actions.test.ts
git commit -m "Expose heart combat to client"
```

Expected: commit succeeds.

## Task 6: API Contract And Level-Up Client Request

**Files:**
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/routes/session_graph.py`
- Modify: `client/services/wire.ts`
- Modify: `client/services/api.ts`
- Modify: `client/logic/game/useGame.ts`
- Modify: `client/components/composer/LevelUpPrompt.tsx`
- Test: `server/tests/test_run_api.py`
- Test: `client/logic/game/__tests__/requestRunner.test.ts`

- [ ] **Step 1: Add API schema tests for growth request**

Add a route-level test that posts:

```json
{
  "growth": {"kind": "max_hp"},
  "think": false
}
```

Expected status: `200` when enough XP exists.

Also test invalid kind:

```json
{
  "growth": {"kind": "stat", "stat_up": "body"},
  "think": false
}
```

Expected status: `422` or route error with a clear message.

- [ ] **Step 2: Update server API schema**

In `server/src/api/schema.py`, replace level-up request fields with:

```python
class GraphLevelUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    growth: dict[str, str]
    think: bool = False
```

In `server/src/api/routes/session_graph.py`, change the level-up call to:

```python
result = await run_graph_level_up(
    repo,
    game_id,
    growth=body.growth,
    scenario_repo=scenario_repo,
)
```

- [ ] **Step 3: Update client request types**

In `client/services/wire.ts`, replace `GraphLevelUpRequest` with:

```ts
export type GraphLevelUpGrowth =
  | { kind: 'max_hp' }
  | { kind: 'max_mp' }
  | { kind: 'learn_skill'; skill_id: string }
  | { kind: 'upgrade_skill'; skill_id: string };

export type GraphLevelUpRequest = {
  growth: GraphLevelUpGrowth;
  think: boolean;
};
```

In `client/logic/game/useGame.ts`, change:

```ts
sendGraphLevelUp(id, { growth, think: false }, { signal })
```

and update `commitLevelUp` to receive `GraphLevelUpGrowth`.

- [ ] **Step 4: Update LevelUpPrompt first version**

In `client/components/composer/LevelUpPrompt.tsx`, replace stat buttons with two resource buttons for the first implementation:

```tsx
const choices = [
  { id: 'max_hp', label: '최대 HP +1', growth: { kind: 'max_hp' } as const },
  { id: 'max_mp', label: '최대 MP +1', growth: { kind: 'max_mp' } as const },
];
```

Keep the existing confirm/cancel `testID`s. Set selected choice to `max_hp` by default.

- [ ] **Step 5: Verify API/client tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/test_run_api.py -q
cd client
npm test -- --runInBand logic/game/__tests__/requestRunner.test.ts components/composer/__tests__/LevelUpPrompt.test.ts
```

Expected: selected tests pass.

- [ ] **Step 6: Commit API/client level-up changes**

Run:

```powershell
git add server/src/api/schema.py server/src/api/routes/session_graph.py server/tests/test_run_api.py client/services/wire.ts client/services/api.ts client/logic/game/useGame.ts client/components/composer/LevelUpPrompt.tsx client/logic/game/__tests__/requestRunner.test.ts client/components/composer/__tests__/LevelUpPrompt.test.ts
git commit -m "Update level-up growth API"
```

Expected: commit succeeds.

## Task 7: Documentation And Full Regression

**Files:**
- Modify: `docs/04-gameplay.md`
- Modify: `docs/05-interfaces.md`

- [ ] **Step 1: Update gameplay docs**

In `docs/04-gameplay.md`, replace the old combat sections with the accepted rules from `docs/superpowers/specs/2026-05-12-heart-combat-skill-growth-design.md`:

```markdown
## 전투

전투는 임시 하트로 해결한다.

- 전투 시작 시 플레이어 하트 3, 적 하트 3을 둔다.
- 플레이어만 d20을 굴린다.
- 성공하면 행동별 성공 효과를 적용한다.
- 실패하면 행동별 실패 효과를 적용한다.
- 적 하트가 0이면 승리한다.
- 플레이어 하트가 0이면 패배하고, 남은 적 하트만큼 실제 HP를 잃는다.
- 4번째 교환 강제 종료 규칙은 쓰지 않는다.
```

Also update skill, item, level-up, and stat sections:

```markdown
스탯은 전투 DC에 직접 들어가지 않는다. 스탯은 비전투 판정, 캐릭터 성향, 개인화 스킬 후보 생성에 사용한다.
```

- [ ] **Step 2: Run docs self-review**

Read `docs/04-gameplay.md` once after editing. Remove old references to:

- direct per-exchange HP damage
- forced fourth exchange
- skill `power` as damage
- stat-up as the default level-up choice

Run:

```powershell
rg -n "4번째|power|피해량|stat_up|round" docs/04-gameplay.md docs/05-interfaces.md
```

Expected: no stale rule references remain except where explaining removed legacy behavior.

- [ ] **Step 3: Run full server regression**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests -q
```

Expected: all server tests pass.

- [ ] **Step 4: Run client regression**

Run:

```powershell
cd client
npm test -- --runInBand
```

Expected: all client tests pass.

- [ ] **Step 5: Run smoke scripts**

Run:

```powershell
.\.venv\Scripts\python server\scripts\smoke_move.py
.\.venv\Scripts\python server\scripts\smoke_classify.py
```

Expected: scripts complete without uncaught exceptions.

- [ ] **Step 6: Commit docs and final fixes**

Run:

```powershell
git add docs/04-gameplay.md docs/05-interfaces.md
git commit -m "Document heart combat gameplay"
```

Expected: commit succeeds.

## Self-Review

Spec coverage:

- Heart combat start, attack, defend, flee, social pressure, victory, defeat, and no forced round limit are covered in Tasks 1 and 2.
- DC formula, clamp, level difference, one support, and no stat contribution are covered in Task 1.
- Skill support, item support, MP spend, consumable spend, post-roll effects, and no stacking are covered in Tasks 1 and 2.
- Level cap 10, HP/MP 5 to 10 scale, skill slots, skill tier, and level-up XP consumption are covered in Task 3.
- Starting skill and scenario migration are covered in Task 4.
- Front-state and client heart display are covered in Task 5.
- API request shape and level-up UI are covered in Task 6.
- Gameplay docs and regression verification are covered in Task 7.

Placeholder scan:

- No `TBD`, `TODO`, or "similar to" placeholders remain.
- Each task has concrete files, test snippets, implementation snippets, commands, and expected results.

Type consistency:

- Combat action uses `support_id` and `support_kind` consistently.
- Combat state uses `player_hearts`, `enemy_hearts`, and `active_enemy_id` consistently.
- Client wire uses camelCase `playerHearts`, `enemyHearts`, and `activeEnemyId`.
- Level-up API uses `growth` consistently after Task 6.
