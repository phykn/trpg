"""subject.refresh_active_subject — list[Verb] 입력 path 검증.

Stage 1b Task 2: subject.py 호환 layer가 verb 직접 입력에 대해
NPC subject 추적이 정상 동작하는지 검증."""

from src.game.domain.entities import Character, Stats
from src.game.flow.subject import refresh_active_subject
from src.llm.calls.classify.schema import Verb


def _make_state(fresh_state, npc_id: str = "npc.tarem"):
    fresh_state.player_id = "player_01"
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="P",
        race_id="human",
        gender="male",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=10,
        mp=5,
        max_mp=5,
        location_id="loc_01",
        is_player=True,
    )
    fresh_state.characters[npc_id] = Character(
        id=npc_id,
        name="Tarem",
        race_id="human",
        gender="male",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=10,
        mp=5,
        max_mp=5,
        location_id="loc_01",
        is_player=False,
    )
    return fresh_state


def test_refresh_with_speak_verb_pins_target(fresh_state):
    s = _make_state(fresh_state)
    verb = Verb(name="speak", modifiers={"intent": "friendly", "target": "npc.tarem"})
    refresh_active_subject(s, [verb])
    assert s.active_subject_id == "npc.tarem"


def test_refresh_with_attack_verb_pins_target(fresh_state):
    s = _make_state(fresh_state)
    verb = Verb(name="attack", target_ids=["npc.tarem"])
    refresh_active_subject(s, [verb])
    assert s.active_subject_id == "npc.tarem"


def test_refresh_with_transfer_verb_pins_npc(fresh_state):
    """transfer (buy)에서 from_id가 NPC면 active subject로."""
    s = _make_state(fresh_state)
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "npc.tarem",
            "to_id": "player_01",
            "mode": "trade",
            "item_id": "potion_01",
        },
    )
    refresh_active_subject(s, [verb])
    assert s.active_subject_id == "npc.tarem"


def test_refresh_with_use_verb_pins_target(fresh_state):
    s = _make_state(fresh_state)
    verb = Verb(
        name="use", modifiers={"item_id": "potion_01", "target_id": "npc.tarem"}
    )
    refresh_active_subject(s, [verb])
    assert s.active_subject_id == "npc.tarem"


def test_refresh_with_wait_verb_no_npc_engagement(fresh_state):
    """wait/perceive/rest는 NPC engagement 없음 — recent_npc fallback."""
    s = _make_state(fresh_state)
    s.active_subject_id = None
    verb = Verb(name="wait")
    refresh_active_subject(s, [verb])
    # recent_npc fallback이 None이면 active_subject_id도 None 유지
    # 본 fixture는 recent_npc 없음 → None
    assert s.active_subject_id is None


def test_refresh_walks_list_in_reverse(fresh_state):
    """list[Verb] 순회는 reverse order — 마지막 verb의 target 우선."""
    s = _make_state(fresh_state, npc_id="npc.first")
    s.characters["npc.last"] = Character(
        id="npc.last",
        name="Last",
        race_id="human",
        gender="male",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=10,
        mp=5,
        max_mp=5,
        location_id="loc_01",
        is_player=False,
    )
    verbs = [
        Verb(name="speak", modifiers={"intent": "friendly", "target": "npc.first"}),
        Verb(name="attack", target_ids=["npc.last"]),
    ]
    refresh_active_subject(s, verbs)
    assert s.active_subject_id == "npc.last"


def test_refresh_with_rest_no_engagement(fresh_state):
    s = _make_state(fresh_state)
    s.active_subject_id = "npc.tarem"  # pre-existing pin
    verb = Verb(name="rest")
    refresh_active_subject(s, [verb])
    # rest에는 engagement 없음 — recent_npc fallback (현 fixture에선 없음)
    # 기존 pin은 character가 살아있는 한 유지 (defensive)
    assert s.active_subject_id == "npc.tarem"
