"""§flee/level_up/learn_skill/buy/sell — 자연어 통합. judge mock 으로 분기 검증."""
import random
import tempfile

import pytest

from src.domain.entities import (
    ArmorEffect,
    Character,
    Item,
    Location,
    Skill,
    Stats,
    WeaponEffect,
)
from src.agents.dc_judge.schema import (
    BuyAction,
    FleeAction,
    LearnSkillAction,
    LevelUpAction,
    SellAction,
)
from src.engines import combat as combat_engine
from src.flow import judge as judge_mod
from src.flow import combat_phase as combat_phase_mod
from src.flow import turn as turn_mod
from src.context import build_surroundings
from src.flow.turn import run_turn


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _judge_returns(monkeypatch, action_obj):
    async def fake_judge(client, state, player_input):
        return action_obj
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    monkeypatch.setattr(combat_phase_mod, "run_judge", fake_judge)


async def _collect(it):
    return [ev async for ev in it]


def _seed_player(fresh_state, **overrides):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="plaza_01",
        hp=20, max_hp=20, mp=15, max_mp=15,
        gold=overrides.get("gold", 100),
        xp_pool=overrides.get("xp_pool", 0),
        level=overrides.get("level", 0),
    )
    if "inventory_ids" in overrides:
        p.inventory_ids = list(overrides["inventory_ids"])
    fresh_state.characters["player_01"] = p
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- flee 자연어 ----------------------------------------------------------


async def test_flee_in_combat_succeeds_ends_combat(fresh_state, tmp_data, monkeypatch):
    """flee 성공 시 combat_end (outcome=fled) + combat_state 정리."""
    state = _seed_player(fresh_state)
    enemy = Character(
        id="goblin_01", name="고블린", race_id="human", stats=Stats(),
        location_id="plaza_01", hp=8, max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    # try_flee 가 항상 성공하도록 RULES.combat.flee.base_dc 보다 무조건 큰 굴림.
    monkeypatch.setattr(combat_engine, "try_flee", lambda actor, rng=None: (True, 30))
    _judge_returns(monkeypatch, FleeAction(action="flee"))

    events = await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="도망친다")
    )
    types = [e["type"] for e in events]
    assert "combat_end" in types
    end_ev = next(e for e in events if e["type"] == "combat_end")
    assert end_ev["data"]["outcome"] == "fled"
    assert state.combat_state is None


async def test_flee_in_combat_fails_npc_phase_runs(fresh_state, tmp_data, monkeypatch):
    """flee 실패 시 turn 소비 + NPC 차례 진행 + combat 유지."""
    state = _seed_player(fresh_state)
    enemy = Character(
        id="goblin_01", name="고블린", race_id="human", stats=Stats(),
        location_id="plaza_01", hp=8, max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    state.combat_state.turn_order = ["player_01", "goblin_01"]

    monkeypatch.setattr(combat_engine, "try_flee", lambda actor, rng=None: (False, 5))
    _judge_returns(monkeypatch, FleeAction(action="flee"))

    events = await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="도망친다",
                 rng=random.Random(0))
    )
    flee_evs = [
        e for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "flee"
    ]
    assert flee_evs and flee_evs[0]["data"]["grade"] == "failure"
    assert state.combat_state is not None  # 전투 안 끝남


async def test_flee_outside_combat_no_op(fresh_state, tmp_data, monkeypatch):
    """평시 flee → 짧은 act log + turn 안 늘림."""
    state = _seed_player(fresh_state)
    _judge_returns(monkeypatch, FleeAction(action="flee"))

    events = await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="도망친다")
    )
    assert state.turn_count == 0
    act_evs = [
        e for e in events
        if e["type"] == "log_entry" and e["data"].get("kind") == "act"
    ]
    assert any("전투" in e["data"]["text"] for e in act_evs)


# --- level_up 자연어 ------------------------------------------------------


async def test_level_up_natural_language_applies_pair_trade(fresh_state, tmp_data, monkeypatch):
    state = _seed_player(fresh_state, xp_pool=100, level=0)
    _judge_returns(monkeypatch, LevelUpAction(action="level_up", stat_up="STR", stat_down="CHA"))

    events = await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="근육을 단련해 한 단계 오른다")
    )
    p = state.characters["player_01"]
    assert p.level == 1
    assert p.stats.STR == 11
    assert p.stats.CHA == 9
    log_texts = [
        e["data"]["text"] for e in events
        if e["type"] == "log_entry" and e["data"].get("kind") == "gm"
    ]
    assert any("레벨 1" in t for t in log_texts)


async def test_level_up_invalid_pair_logs_error(fresh_state, tmp_data, monkeypatch):
    """xp 모자라면 level_up 실패 로그 + turn 소비. 캐릭터 stat 그대로."""
    state = _seed_player(fresh_state, xp_pool=0, level=0)
    _judge_returns(monkeypatch, LevelUpAction(action="level_up", stat_up="STR", stat_down="CHA"))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="성장한다")
    )
    p = state.characters["player_01"]
    assert p.level == 0
    assert p.stats.STR == 10


# --- learn_skill 자연어 ---------------------------------------------------


async def test_learn_skill_appends_to_learned(fresh_state, tmp_data, monkeypatch):
    state = _seed_player(fresh_state)
    candidate = Skill(
        id="fireball_l1", name="화염구",
        description="불꽃을 던진다",
        type="attack", target="single", primary_stat="INT",
        special_effect="화염", level=1, power=10, mp_cost=4,
    )
    state.pending_skill_candidates = [candidate]
    _judge_returns(monkeypatch, LearnSkillAction(action="learn_skill", index=0))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="화염 쪽을 익힌다")
    )
    p = state.characters["player_01"]
    assert any(s.id == "fireball_l1" for s in p.learned_skills)
    assert state.pending_skill_candidates == []


async def test_learn_skill_invalid_index_logs_error(fresh_state, tmp_data, monkeypatch):
    """후보 비어 있는데 learn_skill 입력 → 짧은 거절."""
    state = _seed_player(fresh_state)
    state.pending_skill_candidates = []
    _judge_returns(monkeypatch, LearnSkillAction(action="learn_skill", index=0))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="첫 번째를 익힌다")
    )
    p = state.characters["player_01"]
    assert p.learned_skills == []


# --- buy/sell 자연어 ------------------------------------------------------


def _seed_merchant(state, merchant_inv=None):
    items = {
        "shield_01": Item(
            id="shield_01", name="방패", price=30,
            effects=ArmorEffect(type="armor", defense=2),
        ),
        "ore_01": Item(id="ore_01", name="철광석", price=10),
    }
    state.items.update(items)
    smith = Character(
        id="smith_01", name="대장장이", race_id="human",
        stats=Stats(), location_id="plaza_01",
        hp=20, max_hp=20,
        inventory_ids=list(merchant_inv or ["shield_01"]),
        gold=200,
        relations={"player_01": 50},  # trade_threshold 통과
    )
    state.characters["smith_01"] = smith
    return state


async def test_buy_natural_language(fresh_state, tmp_data, monkeypatch):
    state = _seed_player(fresh_state, gold=100)
    _seed_merchant(state)
    _judge_returns(monkeypatch, BuyAction(action="buy", npc_id="smith_01", item_id="shield_01"))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="방패를 산다")
    )
    p = state.characters["player_01"]
    smith = state.characters["smith_01"]
    assert "shield_01" in p.inventory_ids
    assert "shield_01" not in smith.inventory_ids
    assert p.gold < 100  # 골드 차감


async def test_sell_natural_language(fresh_state, tmp_data, monkeypatch):
    state = _seed_player(fresh_state, gold=50, inventory_ids=["ore_01"])
    _seed_merchant(state, merchant_inv=[])
    _judge_returns(monkeypatch, SellAction(action="sell", npc_id="smith_01", item_id="ore_01"))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="철광석을 판다")
    )
    p = state.characters["player_01"]
    smith = state.characters["smith_01"]
    assert "ore_01" not in p.inventory_ids
    assert "ore_01" in smith.inventory_ids
    assert p.gold > 50  # 골드 입금


async def test_buy_low_affinity_rejected(fresh_state, tmp_data, monkeypatch):
    """affinity < trade_threshold → 거래 실패 로그. 인벤 변동 없음."""
    state = _seed_player(fresh_state, gold=100)
    _seed_merchant(state)
    state.characters["smith_01"].relations = {"player_01": -20}  # threshold 미달
    _judge_returns(monkeypatch, BuyAction(action="buy", npc_id="smith_01", item_id="shield_01"))

    await _collect(
        run_turn(client=None, state=state, profile_dir="<unused>",
                 saves_dir=tmp_data, player_input="방패를 산다")
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


# --- growth payload (surroundings) -----------------------------------------


def test_surroundings_growth_can_level_up(fresh_state):
    state = _seed_player(fresh_state, xp_pool=100, level=0)
    s = build_surroundings(state, "player_01")
    assert s["growth"]["can_level_up"] is True
    assert s["growth"]["level"] == 0


def test_surroundings_growth_cannot_level_up(fresh_state):
    state = _seed_player(fresh_state, xp_pool=0, level=0)
    s = build_surroundings(state, "player_01")
    assert s["growth"]["can_level_up"] is False


def test_surroundings_skill_candidates_visible_when_pending(fresh_state):
    state = _seed_player(fresh_state)
    state.pending_skill_candidates = [
        Skill(id="x_l1", name="화염", type="attack", target="single",
              primary_stat="INT", level=1, mp_cost=2, power=5, special_effect="x",
              description="x"),
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
        id="goblin_01", name="고블린", race_id="human", stats=Stats(),
        location_id="plaza_01", hp=8, max_hp=8,
    )
    state.characters["goblin_01"] = enemy
    combat_engine.start_combat(state, ["goblin_01"])
    s = build_surroundings(state, "player_01")
    assert s["in_combat"] is True
