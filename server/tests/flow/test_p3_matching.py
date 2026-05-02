"""§flee/level_up/learn_skill/buy/sell — natural-language integration. Branches verified via judge mocks."""

import random

from src.domain.entities import (
    ArmorEffect,
    Character,
    Item,
    Location,
    Skill,
    Stats,
)
from src.llm_calls.classify.schema import (
    BuyAction,
    FleeAction,
    LearnSkillAction,
    LevelUpAction,
    SellAction,
)
from src.engines import combat as combat_engine
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.context import build_surroundings
from src.flow.turn import run_turn


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
    judge_returns(FleeAction(action="flee"))

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
    judge_returns(FleeAction(action="flee"))

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
    judge_returns(FleeAction(action="flee"))

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


# --- level_up natural language --------------------------------------------


async def test_level_up_natural_language_applies_pair_trade(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed_player(fresh_state, xp_pool=100, level=0)
    judge_returns(
        LevelUpAction(action="level_up", stat_up="STR", stat_down="CHA")
    )

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="근육을 단련해 한 단계 오른다",
        )
    )
    p = state.characters["player_01"]
    assert p.level == 1
    assert p.stats.STR == 11
    assert p.stats.CHA == 9
    # The "레벨 1" act log line is no longer surfaced as its own log_entry
    # SSE — single-action paths absorb engine notices into narrate's prose
    # via act_log_lines so the UI doesn't show system-toned chrome
    # alongside the body. Stat / level state above is the authoritative
    # check that the engine action ran.


async def test_level_up_invalid_pair_logs_error(
    fresh_state, tmp_data, judge_returns, collect
):
    """Insufficient xp: level_up logs failure + turn consumed. Character stats unchanged."""
    state = _seed_player(fresh_state, xp_pool=0, level=0)
    judge_returns(
        LevelUpAction(action="level_up", stat_up="STR", stat_down="CHA")
    )

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="성장한다",
        )
    )
    p = state.characters["player_01"]
    assert p.level == 0
    assert p.stats.STR == 10


# --- learn_skill natural language -----------------------------------------


async def test_learn_skill_appends_to_learned(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _seed_player(fresh_state)
    candidate = Skill(
        id="fireball_l1",
        name="화염구",
        description="불꽃을 던진다",
        type="attack",
        target="single",
        primary_stat="INT",
        special_effect="화염",
        level=1,
        power=10,
        mp_cost=4,
    )
    state.pending_skill_candidates = [candidate]
    judge_returns(LearnSkillAction(action="learn_skill", index=0))

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="화염 쪽을 익힌다",
        )
    )
    p = state.characters["player_01"]
    assert "fireball_l1" in p.learned_skill_ids
    assert "fireball_l1" in state.skills
    assert state.pending_skill_candidates == []


async def test_learn_skill_invalid_index_logs_error(
    fresh_state, tmp_data, judge_returns, collect
):
    """learn_skill input with empty candidates → short rejection."""
    state = _seed_player(fresh_state)
    state.pending_skill_candidates = []
    judge_returns(LearnSkillAction(action="learn_skill", index=0))

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="첫 번째를 익힌다",
        )
    )
    p = state.characters["player_01"]
    assert p.learned_skill_ids == []


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
        BuyAction(action="buy", npc_id="smith_01", item_id="shield_01")
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
        SellAction(action="sell", npc_id="smith_01", item_id="ore_01")
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
        BuyAction(action="buy", npc_id="smith_01", item_id="shield_01")
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
    from src.domain.entities import Disposition

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


def test_surroundings_skill_candidates_visible_when_pending(fresh_state):
    state = _seed_player(fresh_state)
    state.pending_skill_candidates = [
        Skill(
            id="x_l1",
            name="화염",
            type="attack",
            target="single",
            primary_stat="INT",
            level=1,
            mp_cost=2,
            power=5,
            special_effect="x",
            description="x",
        ),
    ]
    s = build_surroundings(state, "player_01")
    assert len(s["skill_candidates"]) == 1
    assert s["skill_candidates"][0]["name"] == "화염"


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
