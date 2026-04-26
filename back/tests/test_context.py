import tempfile
from pathlib import Path

from src.domain.entities import (
    Chapter,
    Character,
    Connection,
    Location,
    Quest,
    QuestTrigger,
    Stats,
)
from src.domain.memory import DialoguePair, TurnLogEntry
from src.pipeline.context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
)


def test_surroundings_includes_player_and_filters_dead_or_far(fresh_state):
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01", name="광장", tags=["t"],
        connections=[Connection(target_id="gate_01", difficulty="어려움")],
    )
    fresh_state.locations["gate_01"] = Location(id="gate_01", name="성문")
    fresh_state.characters["player_01"] = Character(
        id="player_01", name="주", race_id="human", stats=Stats(),
        location_id="plaza_01",
        relations={"friend": 70, "foe": -60},
    )
    fresh_state.characters["friend"] = Character(
        id="friend", name="친구", race_id="human", stats=Stats(),
        location_id="plaza_01", max_hp=20, hp=20,
    )
    fresh_state.characters["foe"] = Character(
        id="foe", name="적", race_id="human", stats=Stats(),
        location_id="plaza_01", max_hp=20, hp=8,
    )
    fresh_state.characters["far"] = Character(
        id="far", name="먼사람", race_id="human", stats=Stats(),
        location_id="gate_01",
    )
    fresh_state.characters["dead"] = Character(
        id="dead", name="시체", race_id="human", stats=Stats(),
        location_id="plaza_01", alive=False,
    )

    sur = build_surroundings(fresh_state, "player_01")
    ids = {e["id"]: e for e in sur["entities"]}
    assert "player_01" in ids and ids["player_01"]["type"] == "player"
    assert "friend" in ids and "foe" in ids
    assert "far" not in ids and "dead" not in ids
    assert ids["friend"]["state_tags"] == ["우호적(affinity 70)"]
    assert "경계중(affinity -60)" in ids["foe"]["state_tags"]
    assert "부상" in ids["foe"]["state_tags"][1]
    # 인접 connection
    assert ids["gate_01"]["type"] == "connection" and ids["gate_01"]["difficulty"] == "어려움"


def test_session_layer_active_only_pending_goals(fresh_state):
    fresh_state.chapters["ch1"] = Chapter(
        id="ch1", title="ch", summary="s", quest_ids=["q1", "q2"], status="active",
    )
    fresh_state.quests["q1"] = Quest(
        id="q1", title="t", giver_id="g", difficulty="보통",
        triggers=[
            QuestTrigger(id="a", name="A", type="character_death", target_id="x"),
            QuestTrigger(id="b", name="B", type="location_enter", target_id="y"),
        ],
        triggers_met=[True, False],
        conditions=["c"],
        status="active",
    )
    fresh_state.quests["q2"] = Quest(
        id="q2", title="done", giver_id="g", difficulty="쉬움", status="completed",
    )
    fresh_state.characters["g"] = Character(id="g", name="장로", race_id="human", stats=Stats())

    out = build_session_layer(fresh_state)
    assert out["chapter"]["title"] == "ch"
    assert len(out["chapter"]["quests"]) == 1  # 완료 제외
    q = out["chapter"]["quests"][0]
    assert q["goals"] == ["B"]  # pending only
    assert q["giver"] == "장로"


def test_history_layer_dedupes_dialogue_turns(fresh_state):
    fresh_state.turn_log = [
        TurnLogEntry(turn=1, summary="첫"),
        TurnLogEntry(turn=2, summary="둘"),
        TurnLogEntry(turn=3, summary="셋"),  # 중복 (recent_dialogue 에 있음)
    ]
    fresh_state.recent_dialogue = [
        DialoguePair(turn=3, player="p", narrator="n"),
    ]
    h = build_history_layer(fresh_state)
    assert "[턴 1] — 첫" in h
    assert "[턴 2] — 둘" in h
    assert "[턴 3] — 셋" not in h  # dedup
    assert "플레이어: p" in h


def test_world_layer_reads_md():
    with tempfile.TemporaryDirectory() as tmp:
        pdir = Path(tmp) / "default"
        pdir.mkdir()
        (pdir / "world.md").write_text("# world\n중세", encoding="utf-8")
        text = build_world_layer(tmp, "default")
        assert "중세" in text
