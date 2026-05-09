import json

from src.game.domain.entities import Character, Race
from src.game.domain.memory import Memory
from src.game.domain.state import GameState
from src.wire.to_front import _build_subject_payload
from src.wire.models import Equipment as WireEquipment
from src.wire.models import InventoryItem, SubjectPayload


def _state(
    *,
    alive: bool = True,
    appearance: str = "",
    hints: list[str] | None = None,
    memories: list[Memory] | None = None,
    trust: int = 0,
    gold: int = 0,
    role: str = "상인",
) -> GameState:
    state = GameState(game_id="game_dev", profile="dev", player_id="p1")
    state.races["human"] = Race(id="human", name="인간", description="")
    player = Character(
        id="p1",
        name="레오",
        race_id="human",
        gender="male",
        level=1,
        hp=20,
        max_hp=20,
        memories=memories or [],
    )
    state.characters["p1"] = player
    subject = Character(
        id="s1",
        name="아라",
        race_id="human",
        gender="female",
        level=3,
        hp=15,
        max_hp=15,
        role=role,
        appearance=appearance,
        hints=hints or [],
        alive=alive,
        gold=gold,
        relations={"p1": trust},
    )
    state.characters["s1"] = subject
    state.active_subject_id = "s1"
    state.invalidate_graph()
    return state


def test_returns_none_when_no_subject():
    state = _state()
    state.active_subject_id = None
    assert _build_subject_payload(state, state.graph()) is None


def test_returns_none_when_subject_id_missing():
    state = _state()
    state.active_subject_id = "ghost"
    assert _build_subject_payload(state, state.graph()) is None


def test_payload_top_level_shape():
    state = _state()
    payload = _build_subject_payload(state, state.graph())
    assert isinstance(payload, SubjectPayload)
    assert payload.name == "아라"
    assert payload.role == "상인"
    assert payload.hp == 15
    assert payload.hp_max == 15
    assert isinstance(payload.equipment, WireEquipment)


def test_camel_case_serialization():
    state = _state()
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    d = payload.model_dump()
    assert "raceJob" in d
    assert "hpMax" in d
    assert "race_job" not in d
    assert "hp_max" not in d
    assert "mp" not in d
    assert "mpMax" not in d


def test_known_combines_appearance_hints_memories():
    mem = Memory(
        content="처음 만났을 때 친절했다", importance=1, turn=1, target_id="s1"
    )
    state = _state(
        appearance="긴 갈색 머리카락",
        hints=["상인 조합 소속"],
        memories=[mem],
    )
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    assert payload.known == [
        "긴 갈색 머리카락",
        "상인 조합 소속",
        "처음 만났을 때 친절했다",
    ]


def test_known_drops_appearance_when_dead():
    mem = Memory(content="전투 중 쓰러졌다", importance=2, turn=5, target_id="s1")
    state = _state(
        alive=False,
        appearance="붉은 망토",
        hints=["용병 출신"],
        memories=[mem],
    )
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    assert "붉은 망토" not in payload.known
    assert "용병 출신" in payload.known
    assert "전투 중 쓰러졌다" in payload.known


def test_inventory_gold_row_is_first():
    state = _state(gold=7)
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    assert payload.inventory[0] == InventoryItem(name="금화(7)", qty=1)


def test_trust_reads_relations_against_player():
    state = _state(trust=42)
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    assert payload.trust == 42


def test_trust_default_zero_when_no_relation():
    state = _state()
    state.characters["s1"].relations = {}
    state.invalidate_graph()
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    assert payload.trust == 0


def test_serializable_to_json():
    state = _state(appearance="갈색 눈동자")
    payload = _build_subject_payload(state, state.graph())
    assert payload is not None
    raw = json.dumps(payload.model_dump(), ensure_ascii=False)
    assert "아라" in raw
    assert "raceJob" in raw
