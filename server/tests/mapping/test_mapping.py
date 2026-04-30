import json

from src.domain.entities import (
    Character,
    Connection,
    Equipment,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Stats,
    WeaponEffect,
)
from src.domain.memory import GMLogEntry, Memory, RollLogEntry
from src.mapping.to_front import (
    _period,
    to_front_state,
    to_hero,
    to_place,
    to_quest,
    to_subject,
)


def _full_state(fresh_state):
    s = fresh_state
    s.active_subject_id = "guard_01"
    s.active_quest_id = "q1"
    s.world_time = "0812-04-28T14:30:00"
    s.races["human"] = Race(id="human", name="인간", description="x")
    s.races["goblin"] = Race(id="goblin", name="고블린", description="x")
    s.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        tags=["outdoor"],
        weather=["맑음"],
        connections=[Connection(target_id="gate_01")],
    )
    s.locations["gate_01"] = Location(id="gate_01", name="성문")
    s.items["sword_01"] = Item(
        id="sword_01", name="검", effects=WeaponEffect(type="weapon", weapon_dice="1d8")
    )
    s.items["herb_01"] = Item(id="herb_01", name="약초")
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        job="도적",
        level=2,
        stats=Stats(STR=12, DEX=14, CON=10, INT=10, WIS=11, CHA=13),
        hp=18,
        max_hp=20,
        mp=15,
        max_mp=15,
        location_id="plaza_01",
        equipment=Equipment(weapon="sword_01"),
        inventory_ids=["herb_01", "herb_01"],
        status=["굶주림"],
        memories=[
            Memory(
                content="뇌물 줘서 통과", importance=2, turn=1, target_id="guard_01"
            ),
            Memory(
                content="광장 노래 들음", importance=1, turn=2, target_id="plaza_01"
            ),
        ],
        companions=["companion_01"],
    )
    s.characters["guard_01"] = Character(
        id="guard_01",
        name="경비병",
        race_id="human",
        job="경비",
        role="마을 경비병",
        appearance="갑옷의 중년",
        stats=Stats(),
        hp=20,
        max_hp=20,
        relations={"player_01": 30},
    )
    s.characters["companion_01"] = Character(
        id="companion_01",
        name="펭",
        race_id="goblin",
        job="",
        stats=Stats(),
    )
    s.quests["q1"] = Quest(
        id="q1",
        title="t",
        summary="진행 중",
        giver_id="guard_01",
        difficulty="어려움",
        triggers=[
            QuestTrigger(
                id="a", name="처치", type="character_death", target_id="goblin_01"
            ),
            QuestTrigger(
                id="b", name="보고", type="location_enter", target_id="plaza_01"
            ),
        ],
        conditions=["민간인 피해 최소화"],
        rewards=QuestRewards(gold=50, exp=100),
    )
    s.log_entries = [
        GMLogEntry(id=1, kind="gm", text="x"),
        RollLogEntry(
            id=2, kind="roll", check="x", dc=10, roll=14, mod=2, result="success"
        ),
    ]
    return s


def test_hero_basic_fields(fresh_state):
    h = to_hero(_full_state(fresh_state))
    assert h["name"] == "주인공" and h["raceJob"] == "인간 도적"
    assert h["hp"] == 18 and h["hpMax"] == 20
    assert h["stats"]["STR"] == 12


def test_hero_exp_uses_xp_pool_and_curve(fresh_state):
    """to_hero's exp/expMax are sourced from xp_pool and xp_for_next_level."""
    from src.rules import RULES

    state = _full_state(fresh_state)
    state.characters["player_01"].xp_pool = 80
    h = to_hero(state)
    assert h["exp"] == 80
    # level=2 → cost = base_xp × 2
    assert h["expMax"] == RULES.growth.base_xp * 2


def test_hero_equipment_three_slots_with_names(fresh_state):
    h = to_hero(_full_state(fresh_state))
    assert set(h["equipment"].keys()) == {"weapon", "armor", "accessory"}
    assert h["equipment"]["weapon"] == {"name": "검"}
    assert h["equipment"]["armor"] is None


def test_hero_inventory_grouped(fresh_state):
    h = to_hero(_full_state(fresh_state))
    assert h["inventory"] == [{"name": "약초", "qty": 2}]


def test_hero_companion_label_when_job_empty(fresh_state):
    h = to_hero(_full_state(fresh_state))
    assert h["companions"] == ["펭 (고블린)"]


def test_hero_companion_skips_missing_id(fresh_state):
    state = _full_state(fresh_state)
    state.characters[state.player_id].companions.append("ghost_id")
    h = to_hero(state)
    # Missing companion ids must not leak into the Korean UI as raw ids.
    assert all("ghost_id" not in label for label in h["companions"])
    assert h["companions"] == ["펭 (고블린)"]


def test_subject_known_filters_by_target_id(fresh_state):
    s = to_subject(_full_state(fresh_state))
    # appearance + only memories targeting this NPC
    assert s["known"] == ["갑옷의 중년", "뇌물 줘서 통과"]
    assert s["trust"] == 30  # subject → player


def test_quest_difficulty_object(fresh_state):
    q = to_quest(_full_state(fresh_state))
    assert q["difficulty"] == {"value": 4, "max": 7, "label": "어려움"}
    assert q["goals"] == ["처치", "보고"]
    assert q["giver"] == "경비병"


def test_place_korean_date_and_period(fresh_state):
    p = to_place(_full_state(fresh_state))
    assert p["date"] == "812년 4월 28일"
    assert p["hour"] == 14
    assert p["period"] == "오후"
    assert p["surroundings"] == ["성문"]


def test_period_boundaries():
    assert _period(5) == "새벽" and _period(7) == "오전"
    assert _period(12) == "오후" and _period(18) == "저녁"
    assert _period(21) == "밤" and _period(0) == "밤" and _period(4) == "밤"


def test_inactive_slots_return_none(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="x",
        race_id="human",
        stats=Stats(),
    )
    assert to_subject(fresh_state) is None
    assert to_quest(fresh_state) is None
    assert to_place(fresh_state) is None  # location_id None


def test_no_internal_field_leakage(fresh_state):
    s = _full_state(fresh_state)
    front_json = json.dumps(to_front_state(s), ensure_ascii=False)
    forbidden = [
        "disposition",
        "tone_hint",
        "memories",
        "location_id",
        "relations",
        "combat_behavior",
        "triggers",
        "inventory_ids",
        "racial_skills",
        "learned_skills",
        "active_buffs",
        "xp_pool",
        "death_saves",
        "race_id",
        "giver_id",
        "is_player",
        "fail_triggers",
    ]
    for f in forbidden:
        assert f not in front_json, f"내부 필드 누출: {f}"


def test_to_combat_returns_none_when_no_combat_state(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", stats=Stats()
    )
    from src.mapping.to_front import to_combat
    assert to_combat(fresh_state) is None


def test_to_combat_projects_round_actor_enemies(fresh_state):
    from src.domain.state import CombatState
    from src.mapping.to_front import to_combat

    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", is_player=True, stats=Stats()
    )
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01", name="고블린", race_id="goblin", hp=8, max_hp=10, stats=Stats()
    )
    fresh_state.combat_state = CombatState(
        turn_order=["player_01", "goblin_01"],
        current_turn=1,
        round=2,
        enemy_ids=["goblin_01"],
    )
    out = to_combat(fresh_state)
    assert out is not None
    assert out["round"] == 2
    assert out["turnLabel"] == "고블린 차례"
    assert out["enemies"] == [
        {"name": "고블린", "hp": 8, "hpMax": 10, "alive": True}
    ]


def test_unknown_race_id_falls_back_to_id(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="x",
        race_id="unknown_race",
        stats=Stats(),
    )
    h = to_hero(fresh_state)
    assert h["raceJob"] == "unknown_race"


def test_hero_race_job_drops_trailing_space_when_job_empty(fresh_state):
    fresh_state.races["human"] = Race(id="human", name="인간", description="x")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="x",
        race_id="human",
        job="",
        stats=Stats(),
    )
    h = to_hero(fresh_state)
    assert h["raceJob"] == "인간"
