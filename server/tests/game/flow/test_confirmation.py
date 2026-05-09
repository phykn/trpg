import tempfile

import pytest

from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.db.store import load_game, save_meta
from src.game.domain.entities import (
    Character,
    CombatBehavior,
    ConsumableEffect,
    Item,
    Location,
    Quest,
    Stats,
)
from src.game.domain.state import GameState
from src.game.flow.turn import run_turn
from src.wire.to_front import to_front_state


def _state() -> GameState:
    state = GameState(game_id="game-1", profile="default", player_id="player_01")
    state.locations["town"] = Location(id="town", name="마을")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="town",
        stats=Stats(),
        max_hp=20,
        hp=20,
    )
    return state


def _state_with_pending_quest() -> GameState:
    state = _state()
    state.characters["giver_01"] = Character(
        id="giver_01",
        name="의뢰인",
        race_id="human",
        location_id="town",
        stats=Stats(),
    )
    state.quests["q1"] = Quest(
        id="q1",
        title="첫 의뢰",
        summary="x",
        giver_id="giver_01",
        difficulty="normal",
        status="pending",
        requires_acceptance=True,
    )
    return state


def _state_with_enemy() -> GameState:
    state = _state()
    state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="town",
        stats=Stats(),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    return state


def _state_with_stealable_npc() -> GameState:
    state = _state()
    state.items["coin_pouch"] = Item(id="coin_pouch", name="동전 주머니")
    state.characters["npc_01"] = Character(
        id="npc_01",
        name="상인",
        race_id="human",
        location_id="town",
        stats=Stats(),
        inventory_ids=["coin_pouch"],
    )
    return state


def _state_with_damage_item() -> GameState:
    state = _state_with_enemy()
    state.items["bomb"] = Item(
        id="bomb",
        name="폭탄",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="damage", amount=3),
    )
    state.characters["player_01"].inventory_ids = ["bomb"]
    return state


def _state_with_heal_item() -> GameState:
    state = _state()
    state.items["potion"] = Item(
        id="potion",
        name="치유 물약",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
    )
    state.characters["player_01"].hp = 5
    state.characters["player_01"].inventory_ids = ["potion"]
    return state


async def _collect(it):
    return [ev async for ev in it]


def test_to_front_state_exposes_confirmation_without_internal_payload():
    state = _state()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "quest_accept",
        "title": "퀘스트를 시작하시겠습니까?",
        "body": "첫 의뢰를 시작합니다.",
        "confirm_label": "시작",
        "cancel_label": "취소",
        "target_label": "첫 의뢰",
        "payload": {"kind": "quest_action", "action": "accept", "quest_id": "q1"},
    }

    pending = to_front_state(state)["pendingConfirmation"]

    assert pending["kind"] == "quest_accept"
    assert pending["target_label"] == "첫 의뢰"
    assert "payload" not in pending


async def test_pending_confirmation_survives_meta_round_trip():
    state = _state()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "quest_accept",
        "title": "퀘스트를 시작하시겠습니까?",
        "body": "첫 의뢰를 시작합니다.",
        "confirm_label": "시작",
        "cancel_label": "취소",
        "target_label": "첫 의뢰",
        "payload": {"kind": "quest_action", "action": "accept", "quest_id": "q1"},
    }

    with tempfile.TemporaryDirectory() as saves_dir:
        await save_meta(state, saves_dir)
        loaded = load_game(saves_dir, state.game_id)

    assert loaded.pending_confirmation["kind"] == "quest_accept"
    assert loaded.pending_confirmation["payload"]["quest_id"] == "q1"


async def test_quest_action_accept_creates_confirmation_without_mutating(tmp_path):
    state = _state_with_pending_quest()

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="",
            quest_action=("accept", "q1"),
            to_front_fn=to_front_state,
        )
    )

    assert state.quests["q1"].status == "pending"
    assert state.pending_confirmation["kind"] == "quest_accept"
    assert any(event["type"] == "confirmation_required" for event in events)
    assert events[-1] == {"type": "done", "data": {}}


async def test_confirm_cancel_clears_pending_without_mutating(tmp_path):
    from src.game.flow.confirmation import run_confirm

    state = _state_with_pending_quest()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "quest_accept",
        "title": "퀘스트를 시작하시겠습니까?",
        "body": "첫 의뢰를 시작합니다.",
        "confirm_label": "시작",
        "cancel_label": "취소",
        "target_label": "첫 의뢰",
        "payload": {"kind": "quest_action", "action": "accept", "quest_id": "q1"},
    }

    await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="cancel",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert state.quests["q1"].status == "pending"


async def test_confirm_accepts_quest_and_clears_pending(tmp_path):
    from src.game.flow.confirmation import run_confirm

    state = _state_with_pending_quest()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "quest_accept",
        "title": "퀘스트를 시작하시겠습니까?",
        "body": "첫 의뢰를 시작합니다.",
        "confirm_label": "시작",
        "cancel_label": "취소",
        "target_label": "첫 의뢰",
        "payload": {"kind": "quest_action", "action": "accept", "quest_id": "q1"},
    }

    await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="confirm",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert state.quests["q1"].status == "active"


async def test_turn_is_blocked_while_confirmation_pending(tmp_path, judge_returns):
    from src.game.domain.errors import PendingConfirmationActive
    from src.llm.calls.classify.schema import Verb

    state = _state_with_pending_quest()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "quest_accept",
        "title": "퀘스트를 시작하시겠습니까?",
        "body": "첫 의뢰를 시작합니다.",
        "confirm_label": "시작",
        "cancel_label": "취소",
        "target_label": "첫 의뢰",
        "payload": {"kind": "quest_action", "action": "accept", "quest_id": "q1"},
    }
    judge_returns(Verb(name="wait"))

    with pytest.raises(PendingConfirmationActive):
        await _collect(
            run_turn(
                client=None,
                state=state,
                scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
                save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
                player_input="다른 일을 한다",
                to_front_fn=to_front_state,
            )
        )


async def test_attack_creates_confirmation_before_combat(tmp_path, judge_returns):
    from src.llm.calls.classify.schema import Verb

    state = _state_with_enemy()
    judge_returns(Verb(name="attack", target_ids=["goblin_01"]))

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="고블린을 공격한다",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation["kind"] == "attack_start"
    assert state.combat_state is None
    assert "combat_start" not in [event["type"] for event in events]
    assert any(event["type"] == "confirmation_required" for event in events)


async def test_confirm_attack_starts_combat(tmp_path):
    from src.game.flow.confirmation import run_confirm
    from src.llm.calls.classify.schema import Verb

    state = _state_with_enemy()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "attack_start",
        "title": "공격하시겠습니까?",
        "body": "고블린을 공격해 전투를 시작합니다.",
        "confirm_label": "공격",
        "cancel_label": "취소",
        "target_label": "고블린",
        "payload": {
            "kind": "verb",
            "verb": Verb(name="attack", target_ids=["goblin_01"]).model_dump(
                mode="json"
            ),
            "player_input": "고블린을 공격한다",
        },
    }

    events = await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="confirm",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert "combat_start" in [event["type"] for event in events]


async def test_steal_creates_confirmation_before_pending_check(tmp_path, judge_returns):
    from src.llm.calls.classify.schema import Verb

    state = _state_with_stealable_npc()
    judge_returns(
        Verb(
            name="transfer",
            modifiers={
                "mode": "steal",
                "from_id": "npc_01",
                "to_id": "player_01",
            },
        )
    )

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="상인의 주머니를 슬쩍한다",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation["kind"] == "steal"
    assert state.pending_check is None
    assert "pending_check" not in [event["type"] for event in events]
    assert any(event["type"] == "confirmation_required" for event in events)


async def test_confirm_steal_creates_pending_check(tmp_path):
    from src.game.flow.confirmation import run_confirm
    from src.llm.calls.classify.schema import Verb

    state = _state_with_stealable_npc()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "steal",
        "title": "훔치시겠습니까?",
        "body": "상인에게서 몰래 훔치려 합니다.",
        "confirm_label": "시도",
        "cancel_label": "취소",
        "target_label": "상인",
        "payload": {
            "kind": "verb",
            "verb": Verb(
                name="transfer",
                modifiers={
                    "mode": "steal",
                    "from_id": "npc_01",
                    "to_id": "player_01",
                },
            ).model_dump(mode="json"),
            "player_input": "상인의 주머니를 슬쩍한다",
        },
    }

    events = await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="confirm",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert state.pending_check.kind == "steal"
    assert any(event["type"] == "pending_check" for event in events)


async def test_dangerous_rest_creates_confirmation_before_rest(
    tmp_path, judge_returns
):
    from src.llm.calls.classify.schema import Verb

    state = _state()
    state.locations["town"].sleep_risk = "dangerous"
    state.characters["player_01"].gold = 100
    state.characters["player_01"].hp = 5
    state.characters["player_01"].max_hp = 20
    judge_returns(Verb(name="rest"))

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="여기서 쉰다",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation["kind"] == "dangerous_rest"
    assert state.characters["player_01"].hp == 5
    assert any(event["type"] == "confirmation_required" for event in events)


async def test_confirm_dangerous_rest_resumes_rest(tmp_path):
    from src.game.flow.confirmation import run_confirm
    from src.llm.calls.classify.schema import Verb

    state = _state()
    state.locations["town"].sleep_risk = "dangerous"
    state.characters["player_01"].gold = 100
    state.characters["player_01"].hp = 5
    state.characters["player_01"].max_hp = 20
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "dangerous_rest",
        "title": "위험한 곳에서 쉬시겠습니까?",
        "body": "쉬는 동안 습격을 받을 수 있습니다.",
        "confirm_label": "쉬기",
        "cancel_label": "취소",
        "target_label": "마을",
        "payload": {
            "kind": "verb",
            "verb": Verb(name="rest").model_dump(mode="json"),
            "player_input": "여기서 쉰다",
        },
    }

    events = await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="confirm",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert events[-1] == {"type": "done", "data": {}}
    assert state.characters["player_01"].hp == 20 or state.combat_state is not None


async def test_dangerous_use_creates_confirmation_before_item_effect(
    tmp_path, judge_returns
):
    from src.llm.calls.classify.schema import Verb

    state = _state_with_damage_item()
    judge_returns(
        Verb(
            name="use",
            modifiers={"item_id": "bomb", "target_id": "goblin_01"},
        )
    )

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="고블린에게 폭탄을 던진다",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation["kind"] == "dangerous_use"
    assert "bomb" in state.characters["player_01"].inventory_ids
    assert state.characters["goblin_01"].hp == 8
    assert any(event["type"] == "confirmation_required" for event in events)


async def test_confirm_dangerous_use_resumes_item_effect(tmp_path):
    from src.game.flow.confirmation import run_confirm
    from src.llm.calls.classify.schema import Verb

    state = _state_with_damage_item()
    state.pending_confirmation = {
        "id": "confirm-1",
        "kind": "dangerous_use",
        "title": "위험한 아이템을 사용하시겠습니까?",
        "body": "고블린에게 폭탄을 사용합니다.",
        "confirm_label": "사용",
        "cancel_label": "취소",
        "target_label": "고블린",
        "payload": {
            "kind": "verb",
            "verb": Verb(
                name="use",
                modifiers={"item_id": "bomb", "target_id": "goblin_01"},
            ).model_dump(mode="json"),
            "player_input": "고블린에게 폭탄을 던진다",
        },
    }

    events = await _collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            confirmation_id="confirm-1",
            decision="confirm",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert "bomb" not in state.characters["player_01"].inventory_ids
    assert state.characters["goblin_01"].hp == 5
    assert events[-1] == {"type": "done", "data": {}}


async def test_heal_use_does_not_create_confirmation(tmp_path, judge_returns):
    from src.llm.calls.classify.schema import Verb

    state = _state_with_heal_item()
    judge_returns(Verb(name="use", modifiers={"item_id": "potion"}))

    events = await _collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_path)),
            player_input="치유 물약을 마신다",
            to_front_fn=to_front_state,
        )
    )

    assert state.pending_confirmation is None
    assert state.characters["player_01"].hp == 13
    assert "potion" not in state.characters["player_01"].inventory_ids
    assert not any(event["type"] == "confirmation_required" for event in events)
