import json

from src.game.domain.entities import (
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
from src.game.domain.memory import GMLogEntry, Memory, RollLogEntry
from src.wire.story_graph import to_story_graph
from src.wire.to_front import (
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
        gender="male",
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
        gender="male",
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
        difficulty="hard",
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
        status="pending",
    )
    s.log_entries = [
        GMLogEntry(id=1, kind="gm", text="x"),
        RollLogEntry(
            id=2,
            kind="roll",
            check="x",
            roll=14,
            margin=8,
            result="success",
        ),
    ]
    return s


def test_hero_basic_fields(fresh_state):
    h = to_hero(_full_state(fresh_state))
    assert h["name"] == "주인공" and h["raceJob"] == "인간 · 도적"
    assert h["gender"] == "남성"
    assert h["hp"] == 18 and h["hpMax"] == 20
    assert h["stats"][0] == {"label": "근력", "value": 12}


def test_hero_exp_uses_xp_pool_and_curve(fresh_state):
    """to_hero's exp/expMax are sourced from xp_pool and xp_for_next_level."""
    from src.game.rules import RULES

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
    assert h["inventory"] == [{"name": "금화(0)", "qty": 1}, {"name": "약초", "qty": 2}]


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
    assert s["gender"] == "남성"


def test_subject_inventory_prepends_gold_when_positive(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].gold = 42
    state.characters["guard_01"].inventory_ids = ["herb_01"]
    s = to_subject(state)
    assert s["inventory"] == [
        {"name": "금화(42)", "qty": 1},
        {"name": "약초", "qty": 1},
    ]


def test_subject_inventory_includes_gold_when_zero(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].gold = 0
    state.characters["guard_01"].inventory_ids = ["herb_01"]
    s = to_subject(state)
    assert s["inventory"] == [
        {"name": "금화(0)", "qty": 1},
        {"name": "약초", "qty": 1},
    ]


def test_subject_dead_exposed_via_alive_field(fresh_state):
    """Dead subjects drop the static appearance from `known` (it describes a
    living body and goes stale once equipment is looted) — only player
    memories about the NPC remain."""
    state = _full_state(fresh_state)
    state.characters["guard_01"].alive = False
    state.characters["guard_01"].hp = 0
    s = to_subject(state)
    assert s["alive"] is False
    assert s["known"] == ["뇌물 줘서 통과"]


def test_quest_difficulty_label(fresh_state):
    q = to_quest(_full_state(fresh_state))
    assert q["id"] == "q1"
    assert q["difficulty"] == {"label": "어려움", "tone": "exp"}
    assert q["goals"] == ["처치", "보고"]
    assert q["giver"] == "경비병"


def test_quest_progress_label_partial(fresh_state):
    state = _full_state(fresh_state)
    state.quests["q1"].triggers_met = [True, False]
    q = to_quest(state)
    assert q["progressLabel"] == "1/2"


def test_quest_progress_label_complete(fresh_state):
    state = _full_state(fresh_state)
    state.quests["q1"].triggers_met = [True, True]
    q = to_quest(state)
    assert q["progressLabel"] == "✓"


def test_quest_progress_label_empty_when_no_triggers(fresh_state):
    state = _full_state(fresh_state)
    state.quests["q1"].triggers = []
    state.quests["q1"].triggers_met = []
    q = to_quest(state)
    assert q["progressLabel"] == ""


def test_quest_progress_label_unmet_when_triggers_met_missing(fresh_state):
    """Defensive: if triggers_met is unaligned (e.g. legacy save), treat
    missing slots as unmet rather than crashing."""
    state = _full_state(fresh_state)
    state.quests["q1"].triggers_met = []
    q = to_quest(state)
    assert q["progressLabel"] == "0/2"


def test_quest_none_when_active_id_cleared(fresh_state):
    """After completion clears active_quest_id, the front payload's quest
    slot must be None — not a stale dict."""
    state = _full_state(fresh_state)
    state.active_quest_id = None
    assert to_quest(state) is None
    assert to_front_state(state)["quest"] is None


def test_place_day_phase_default_dawn(fresh_state):
    """turn_count 0 → 새벽 (start of day cycle)."""
    p = to_place(_full_state(fresh_state))
    assert p["dayPhase"] == "새벽"
    assert p["surroundings"] == [
        {
            "name": "성문",
            "blurb": "",
            "difficulty": None,
            "risk": {"label": "안전", "tone": "good"},
        }
    ]


def test_place_day_phase_advances_with_turn_count(fresh_state):
    """4 phases × 10 turns each: 새벽 / 오전 / 오후 / 밤 → repeat."""
    state = _full_state(fresh_state)
    state.turn_count = 15
    assert to_place(state)["dayPhase"] == "오전"
    state.turn_count = 25
    assert to_place(state)["dayPhase"] == "오후"
    state.turn_count = 35
    assert to_place(state)["dayPhase"] == "밤"
    state.turn_count = 40
    assert to_place(state)["dayPhase"] == "새벽"


def test_place_surroundings_carry_blurb_and_difficulty(fresh_state):
    state = _full_state(fresh_state)
    state.locations["gate_01"].description = "닫힌 성문"
    state.locations["plaza_01"].connections = [
        Connection(target_id="gate_01", difficulty="hard")
    ]
    p = to_place(state)
    assert p["surroundings"] == [
        {
            "name": "성문",
            "blurb": "닫힌 성문",
            "difficulty": "어려움",
            "risk": {"label": "안전", "tone": "good"},
        }
    ]


def test_place_targets_carry_meta_blurb_trust(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].location_id = "plaza_01"
    p = to_place(state)
    assert p["targets"] == [
        {
            "name": "경비병",
            "level": 0,
            "raceJob": "인간 · 경비",
            "gender": "남성",
            "blurb": "갑옷의 중년",
            "trust": 30,
        }
    ]


def test_place_targets_dead_blurb_marked_as_death(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].location_id = "plaza_01"
    state.characters["guard_01"].alive = False
    state.characters["guard_01"].hp = 0
    p = to_place(state)
    assert p["targets"] == [
        {
            "name": "경비병",
            "level": 0,
            "raceJob": "인간 · 경비",
            "gender": "남성",
            "blurb": "죽음",
            "trust": 30,
        }
    ]


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


def test_story_graph_projects_current_map_and_actions(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].location_id = "plaza_01"

    out = to_story_graph(state)
    nodes = {node["id"]: node for node in out["nodes"]}
    edges = {(edge["source"], edge["target"], edge["label"]) for edge in out["edges"]}
    edge_kinds = {
        (edge["source"], edge["target"]): edge["kind"] for edge in out["edges"]
    }

    assert nodes["player_01"]["kind"] == "hero"
    assert nodes["player_01"]["status"] is None
    assert nodes["player_01"]["reachable"] is True
    assert isinstance(nodes["player_01"]["level"], int)
    assert nodes["plaza_01"] == {
        "id": "plaza_01",
        "kind": "place",
        "label": "광장",
        "status": "current",
        "reachable": True,
        "description": "",
        "risk": {"label": "안전", "tone": "good"},
        "dayPhase": "새벽",
        "weather": ["맑음"],
    }
    assert nodes["gate_01"]["kind"] == "location"
    assert nodes["gate_01"]["status"] == "reachable_move"
    assert nodes["gate_01"]["reachable"] is True
    assert nodes["gate_01"]["risk"] == {"label": "안전", "tone": "good"}
    assert nodes["guard_01"]["kind"] == "subject"
    assert nodes["guard_01"]["status"] == "engaged"
    assert nodes["guard_01"]["raceJob"]
    assert nodes["q1"]["kind"] == "quest"
    assert nodes["q1"]["status"] is None
    assert nodes["q1"]["questDifficulty"]

    assert ("player_01", "plaza_01", "현재 위치") in edges
    assert ("plaza_01", "gate_01", "이동") in edges
    assert ("guard_01", "plaza_01", "등장") in edges
    assert ("guard_01", "q1", "의뢰") in edges
    assert edge_kinds[("player_01", "plaza_01")] == "current_pin"
    assert edge_kinds[("plaza_01", "gate_01")] == "move"
    assert edge_kinds[("guard_01", "plaza_01")] == "meet"
    assert edge_kinds[("guard_01", "q1")] == "quest_giver"
    assert out["summary"] == "주인공 · 현재 위치 광장 · 퀘스트 t · 등장인물 2 · 장소 2"


def test_story_graph_does_not_leak_unseen_npcs_or_side_quests(fresh_state):
    state = _full_state(fresh_state)
    state.characters["guard_01"].location_id = "plaza_01"
    state.characters["secret_01"] = Character(
        id="secret_01",
        name="숨은 후원자",
        race_id="human",
        role="막후 인물",
        appearance="검은 망토",
        location_id="gate_01",
        stats=Stats(),
    )
    state.quests["q2"] = Quest(
        id="q2",
        title="숨은 의뢰",
        summary="아직 알 수 없는 일",
        giver_id="secret_01",
        difficulty="easy",
        triggers=[
            QuestTrigger(
                id="secret_goal",
                name="비밀 접촉",
                type="location_enter",
                target_id="secret_01",
            )
        ],
        status="active",
    )

    front_json = json.dumps(to_story_graph(state), ensure_ascii=False)

    assert "secret_01" not in front_json
    assert "숨은 후원자" not in front_json
    assert "검은 망토" not in front_json
    assert "숨은 의뢰" not in front_json


def test_to_combat_returns_none_when_no_combat_state(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", stats=Stats()
    )
    from src.wire.to_front import to_combat

    assert to_combat(fresh_state) is None


def test_to_combat_projects_round_actor_enemies(fresh_state):
    from src.game.domain.state import CombatState
    from src.wire.to_front import to_combat

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
    assert out["enemies"] == [{"name": "고블린", "hp": 8, "hpMax": 10, "alive": True}]


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
