import json

from src.domain.entities import Character, Location, Stats
from src.domain.state import GameState
from src.wire.emit import _build_place_payload
from src.wire.models import PlacePayload, RiskBadge


def _state(*, player_id="p1", loc_id="loc_town") -> GameState:
    state = GameState(game_id="game_dev", profile="dev", player_id=player_id)
    stats = Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10)
    state.characters[player_id] = Character(
        id=player_id, name="레오", race_id="race_human", stats=stats,
        location_id=loc_id,
    )
    state.locations[loc_id] = Location(
        id=loc_id, name="작은 마을", description="평화로운 마을입니다.",
        weather=["맑음"], tags=["주거"],
    )
    return state


def test_returns_none_when_player_has_no_location():
    state = _state()
    state.characters["p1"].location_id = None
    state.invalidate_graph()
    assert _build_place_payload(state, state.graph()) is None


def test_returns_none_when_location_id_missing():
    state = _state()
    state.characters["p1"].location_id = "ghost_loc"
    state.invalidate_graph()
    assert _build_place_payload(state, state.graph()) is None


def test_payload_top_level_shape():
    state = _state()
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert isinstance(payload, PlacePayload)
    assert payload.name == "작은 마을"
    assert payload.description == "평화로운 마을입니다."
    assert payload.weather == ["맑음"]
    assert payload.features == ["주거"]
    assert isinstance(payload.risk, RiskBadge)


def test_camel_case_serialization():
    state = _state()
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    d = payload.model_dump()
    assert "dayPhase" in d
    assert "day_phase" not in d


def test_risk_badge_for_safe_default():
    state = _state()
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    assert payload.risk.tone == "good"


def test_risk_badge_dangerous_tone_bad():
    state = _state()
    state.locations["loc_town"].sleep_risk = "dangerous"
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    assert payload.risk.tone == "bad"


def test_targets_excludes_player():
    state = _state()
    stats = Stats()
    state.characters["npc1"] = Character(
        id="npc1", name="상인", race_id="race_human", stats=stats,
        location_id="loc_town",
    )
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    names = [t.name for t in payload.targets]
    assert "상인" in names
    assert "레오" not in names


def test_target_blurb_uses_appearance_or_description():
    state = _state()
    stats = Stats()
    state.characters["npc_a"] = Character(
        id="npc_a", name="기사", race_id="race_human", stats=stats,
        location_id="loc_town", appearance="갑옷을 입은 기사", description="설명",
    )
    state.characters["npc_b"] = Character(
        id="npc_b", name="농부", race_id="race_human", stats=stats,
        location_id="loc_town", appearance="", description="늙은 농부",
    )
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    blurbs = {t.name: t.blurb for t in payload.targets}
    assert blurbs["기사"] == "갑옷을 입은 기사"
    assert blurbs["농부"] == "늙은 농부"


def test_target_blurb_dead_is_죽음():
    state = _state()
    stats = Stats()
    state.characters["npc_dead"] = Character(
        id="npc_dead", name="망자", race_id="race_human", stats=stats,
        location_id="loc_town", appearance="비석", alive=False,
    )
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    blurbs = {t.name: t.blurb for t in payload.targets}
    assert blurbs["망자"] == "죽음"


def test_serializable_to_json():
    state = _state()
    state.invalidate_graph()
    payload = _build_place_payload(state, state.graph())
    assert payload is not None
    raw = json.dumps(payload.model_dump(), ensure_ascii=False)
    assert "작은 마을" in raw
    assert "dayPhase" in raw
