from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.game.domain.entities import Character, Connection, Item, Location, Stats
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import Verb


def _state(fresh_state):
    fresh_state.locations["town"] = Location(
        id="town",
        name="마을",
        connections=[Connection(target_id="east_gate")],
        item_ids=["loose_sword"],
    )
    fresh_state.locations["east_gate"] = Location(id="east_gate", name="동쪽 문")
    fresh_state.items["herb"] = Item(id="herb", name="약초")
    fresh_state.items["loose_sword"] = Item(id="loose_sword", name="낡은 검")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="town",
        stats=Stats(),
        hp=10,
        max_hp=20,
        inventory_ids=["herb"],
    )
    return fresh_state


def _gm_texts(events: list[dict]) -> list[str]:
    return [
        event["data"]["text"]
        for event in events
        if event["type"] == "log_entry" and event["data"].get("kind") == "gm"
    ]


async def test_query_exits_does_not_advance_turn_or_create_pending(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _state(fresh_state)
    judge_returns(Verb(name="query", modifiers={"topic": "exits"}))

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="보이는 출구가 뭐야?",
        )
    )

    assert state.turn_count == 0
    assert state.pending_confirmation is None
    assert state.pending_check is None
    assert any("동쪽 문" in text for text in _gm_texts(events))
    assert events[-1] == {"type": "done", "data": {}}


async def test_query_inventory_only_uses_player_inventory(
    fresh_state, tmp_data, judge_returns, collect
):
    state = _state(fresh_state)
    judge_returns(Verb(name="query", modifiers={"topic": "inventory"}))

    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="내가 가진 게 뭐지?",
        )
    )

    text = "\n".join(_gm_texts(events))
    assert "약초" in text
    assert "낡은 검" not in text
    assert state.turn_count == 0
