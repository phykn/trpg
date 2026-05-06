import json

from src.game.domain.entities import Character, Quest, QuestRewards, QuestTrigger, Race
from src.game.domain.state import GameState
from src.wire.to_front import _build_quest_payload
from src.wire.models import DifficultyBadge, QuestPayload


def _state(**quest_overrides) -> GameState:
    state = GameState(game_id="game_dev", profile="dev", player_id="p1")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.characters["p1"] = Character(
        id="p1",
        name="레오",
        race_id="human",
        gender="male",
        level=1,
        hp=20,
        max_hp=20,
    )
    q = _quest(**quest_overrides)
    state.quests[q.id] = q
    state.active_quest_id = q.id
    state.invalidate_graph()
    return state


def _quest(**overrides) -> Quest:
    defaults = dict(
        id="q1",
        title="잃어버린 반지",
        summary="강가에서 반지를 찾아 주십시오.",
        giver_id="npc_elder",
        difficulty="normal",
        triggers=[
            QuestTrigger(id="t1", name="반지 회수", type="collect", target_id="ring"),
        ],
        conditions=["일몰 전 완료"],
        rewards=QuestRewards(gold=50, exp=20, items=["potion"]),
        status="pending",
        triggers_met=[False],
    )
    defaults.update(overrides)
    return Quest(**defaults)


def test_returns_none_when_no_active_quest():
    state = _state()
    state.active_quest_id = None
    assert _build_quest_payload(state, state.graph()) is None


def test_returns_none_when_quest_id_missing():
    state = _state()
    state.active_quest_id = "ghost"
    assert _build_quest_payload(state, state.graph()) is None


def test_payload_top_level_shape():
    state = _state()
    payload = _build_quest_payload(state, state.graph())
    assert isinstance(payload, QuestPayload)
    assert payload.id == "q1"
    assert payload.title == "잃어버린 반지"
    assert payload.summary == "강가에서 반지를 찾아 주십시오."
    assert payload.status == "pending"
    assert payload.actions == ["accept"]


def test_camel_case_serialization():
    state = _state()
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    d = payload.model_dump()
    assert "progressLabel" in d
    assert "progress_label" not in d


def test_difficulty_badge_sub_model():
    state = _state(difficulty="hard")
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.difficulty == DifficultyBadge(label="어려움", tone="exp")


def test_difficulty_tone_none_for_normal():
    state = _state(difficulty="normal")
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.difficulty.tone is None


def test_rewards_sub_model_drops_items():
    state = _state(rewards=QuestRewards(gold=100, exp=50, items=["sword", "potion"]))
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.rewards.gold == 100
    assert payload.rewards.exp == 50
    assert "items" not in payload.model_dump()["rewards"]


def test_progress_label_partial():
    state = _state(
        triggers=[
            QuestTrigger(id="t1", name="목표 1", type="collect", target_id="i1"),
            QuestTrigger(id="t2", name="목표 2", type="collect", target_id="i2"),
            QuestTrigger(id="t3", name="목표 3", type="collect", target_id="i3"),
        ],
        triggers_met=[True, False, False],
    )
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.progress_label == "1/3"


def test_progress_label_complete():
    state = _state(
        triggers=[
            QuestTrigger(id="t1", name="목표 1", type="collect", target_id="i1"),
            QuestTrigger(id="t2", name="목표 2", type="collect", target_id="i2"),
        ],
        triggers_met=[True, True],
    )
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.progress_label == "✓"


def test_progress_label_empty_when_no_triggers():
    state = _state(triggers=[], triggers_met=[])
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.progress_label == ""


def test_actions_for_active_quest_offers_abandon():
    state = _state(status="active")
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.actions == ["abandon"]


def test_actions_empty_for_completed_quest():
    state = _state(status="completed")
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.actions == []


def test_giver_falls_back_to_qid_when_giver_missing():
    state = _state(giver_id="")
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    assert payload.giver == "q1"


def test_serializable_to_json():
    state = _state()
    payload = _build_quest_payload(state, state.graph())
    assert payload is not None
    raw = json.dumps(payload.model_dump(), ensure_ascii=False)
    assert "잃어버린 반지" in raw
    assert "progressLabel" in raw
