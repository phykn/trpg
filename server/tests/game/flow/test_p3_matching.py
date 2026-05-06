"""§flee/buy/sell — natural-language integration. Branches verified via judge mocks."""

import random

from src.game.domain.entities import (
    ArmorEffect,
    Character,
    Item,
    Location,
    Stats,
)
from src.llm.calls.classify.schema import Verb
from src.game.engines import combat as combat_engine
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.llm.context import build_surroundings
from src.game.flow.turn import run_turn


def _seed_player(fresh_state, **overrides):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="plaza_01",
        hp=20,
        max_hp=20,
        mp=15,
        max_mp=15,
        gold=overrides.get("gold", 100),
        xp_pool=overrides.get("xp_pool", 0),
        level=overrides.get("level", 0),
    )
    if "inventory_ids" in overrides:
        p.inventory_ids = list(overrides["inventory_ids"])
    fresh_state.characters["player_01"] = p
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- flee natural language ------------------------------------------------


async def test_flee_in_combat_succeeds_ends_combat(
    fresh_state, tmp_data, monkeypatch, judge_returns, collect
):
    """On flee success: combat_end (outcome=fled) + combat_state cleared."""
    state = _seed_player(fresh_state)
    enemy = Character(
        id="goblin_01",
        name="고블린",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        hp=8,
        max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    # Force try_flee to always pass with a roll above RULES.combat.flee.base_dc.
    monkeypatch.setattr(combat_engine, "try_flee", lambda actor, rng=None: (True, 30))
    judge_returns(Verb(name="move", modifiers={"manner": "hasty"}))

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="도망친다",
        )
    )
    types = [e["type"] for e in events]
    assert "combat_end" in types
    end_ev = next(e for e in events if e["type"] == "combat_end")
    assert end_ev["data"]["outcome"] == "fled"
    assert state.combat_state is None


async def test_flee_in_combat_fails_npc_phase_runs(
    fresh_state, tmp_data, monkeypatch, judge_returns, collect
):
    """On flee failure: turn consumed, the auto-sim continues with the player
    falling back to basic attacks, and a flee combat_turn event is recorded."""
    state = _seed_player(fresh_state)
    enemy = Character(
        id="goblin_01",
        name="고블린",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        hp=8,
        max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    state.combat_state.turn_order = ["player_01", "goblin_01"]

    monkeypatch.setattr(combat_engine, "try_flee", lambda actor, rng=None: (False, 5))
    judge_returns(Verb(name="move", modifiers={"manner": "hasty"}))

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="도망친다",
            rng=random.Random(0),
        )
    )
    flee_evs = [
        e
        for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "flee"
    ]
    assert flee_evs and flee_evs[0]["data"]["grade"] == "failure"
    # NPC took at least one turn — at minimum a non-flee combat_turn event from
    # the goblin should appear in the trace.
    npc_evs = [
        e
        for e in events
        if e["type"] == "combat_turn" and e["data"].get("actor") == "goblin_01"
    ]
    assert npc_evs


async def test_flee_outside_combat_no_op(fresh_state, tmp_data, judge_returns, collect):
    """Out-of-combat flee → short act log + turn not advanced."""
    state = _seed_player(fresh_state)
    judge_returns(Verb(name="move", modifiers={"manner": "hasty"}))

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="도망친다",
        )
    )
    assert state.turn_count == 0
    act_evs = [
        e for e in events if e["type"] == "log_entry" and e["data"].get("kind") == "act"
    ]
    assert any("전투" in e["data"]["text"] for e in act_evs)


# --- buy/sell natural language --------------------------------------------


def _seed_merchant(state, merchant_inv=None):
    items = {
        "shield_01": Item(
            id="shield_01",
            name="방패",
            price=30,
            effects=ArmorEffect(type="armor", defense=2),
        ),
        "ore_01": Item(id="ore_01", name="철광석", price=10),
    }
    state.items.update(items)
    smith = Character(
        id="smith_01",
        name="대장장이",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        hp=20,
        max_hp=20,
        inventory_ids=list(merchant_inv or ["shield_01"]),
        gold=200,
        relations={"player_01": 50},  # passes trade_threshold
    )
    state.characters["smith_01"] = smith
    return state


async def test_buy_natural_language(fresh_state, tmp_data, judge_returns, collect):
    state = _seed_player(fresh_state, gold=100)
    _seed_merchant(state)
    judge_returns(
        Verb(
            name="transfer",
            modifiers={
                "from_id": "smith_01",
                "to_id": "player_01",
                "mode": "trade",
                "item_id": "shield_01",
            },
        )
    )

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="방패를 산다",
        )
    )
    p = state.characters["player_01"]
    smith = state.characters["smith_01"]
    assert "shield_01" in p.inventory_ids
    assert "shield_01" not in smith.inventory_ids
    assert p.gold < 100  # gold deducted


async def test_sell_natural_language(fresh_state, tmp_data, judge_returns, collect):
    state = _seed_player(fresh_state, gold=50, inventory_ids=["ore_01"])
    _seed_merchant(state, merchant_inv=[])
    judge_returns(
        Verb(
            name="transfer",
            modifiers={
                "from_id": "player_01",
                "to_id": "smith_01",
                "mode": "trade",
                "item_id": "ore_01",
            },
        )
    )

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="철광석을 판다",
        )
    )
    p = state.characters["player_01"]
    smith = state.characters["smith_01"]
    assert "ore_01" not in p.inventory_ids
    assert "ore_01" in smith.inventory_ids
    assert p.gold > 50  # gold received


async def test_buy_low_affinity_rejected(fresh_state, tmp_data, judge_returns, collect):
    """affinity < trade_threshold → trade-failure log; inventory unchanged."""
    state = _seed_player(fresh_state, gold=100)
    _seed_merchant(state)
    state.characters["smith_01"].relations = {"player_01": -20}  # below threshold
    judge_returns(
        Verb(
            name="transfer",
            modifiers={
                "from_id": "smith_01",
                "to_id": "player_01",
                "mode": "trade",
                "item_id": "shield_01",
            },
        )
    )

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="방패를 산다",
        )
    )
    p = state.characters["player_01"]
    assert "shield_01" not in p.inventory_ids


# --- merchants payload (surroundings) -------------------------------------


def test_surroundings_exposes_merchants_above_threshold(fresh_state):
    state = _seed_player(fresh_state)
    _seed_merchant(state)
    s = build_surroundings(state, "player_01")
    merchants = s["merchants"]
    assert len(merchants) == 1
    assert merchants[0]["id"] == "smith_01"
    stock_ids = [it["id"] for it in merchants[0]["stock"]]
    assert "shield_01" in stock_ids


def test_surroundings_hides_merchants_below_threshold(fresh_state):
    state = _seed_player(fresh_state)
    _seed_merchant(state)
    state.characters["smith_01"].relations = {"player_01": -20}
    s = build_surroundings(state, "player_01")
    assert s["merchants"] == []


def test_surroundings_hides_hostile_npcs_with_inventory(fresh_state):
    """Hostile seeds (bandits, beasts) must not surface as merchants on first
    sight. Without the disposition.aggressive gate, the empty-dict default of
    relations[player]=0 satisfies the trade_threshold and the bandit's
    weapons would be listed for sale."""
    from src.game.domain.entities import Disposition

    state = _seed_player(fresh_state)
    _seed_merchant(state)
    state.characters["smith_01"].disposition = Disposition(
        lawful=30, moral=25, aggressive=85
    )
    s = build_surroundings(state, "player_01")
    assert s["merchants"] == []


# --- growth payload (surroundings) -----------------------------------------


def test_surroundings_growth_can_level_up(fresh_state):
    state = _seed_player(fresh_state, xp_pool=100, level=0)
    s = build_surroundings(state, "player_01")
    assert s["growth"]["can_level_up"] is True


def test_surroundings_growth_cannot_level_up(fresh_state):
    state = _seed_player(fresh_state, xp_pool=0, level=0)
    s = build_surroundings(state, "player_01")
    assert s["growth"]["can_level_up"] is False


# --- in_combat flag --------------------------------------------------------


def test_surroundings_in_combat_flag(fresh_state):
    state = _seed_player(fresh_state)
    s = build_surroundings(state, "player_01")
    assert s["in_combat"] is False

    enemy = Character(
        id="goblin_01",
        name="고블린",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        hp=8,
        max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    s = build_surroundings(state, "player_01")
    assert s["in_combat"] is True
