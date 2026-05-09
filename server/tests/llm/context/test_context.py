import tempfile
from pathlib import Path

from src.game.domain.entities import (
    Chapter,
    Character,
    Connection,
    Location,
    Quest,
    Stats,
)
from src.game.domain.memory import DialoguePair, TurnLogEntry
from src.llm.context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
)
from src.db.local_fs import LocalFsScenarioRepo


def test_surroundings_includes_player_and_filters_dead_or_far(fresh_state):
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        tags=["t"],
        connections=[Connection(target_id="gate_01", difficulty="hard")],
    )
    fresh_state.locations["gate_01"] = Location(id="gate_01", name="성문")
    from src.game.domain.entities import Race

    fresh_state.races["human"] = Race(id="human", name="인간", description="")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    # Affinity is now read NPC→player (how each NPC views the player), so
    # the relations dict lives on the NPCs, not the player.
    fresh_state.characters["friend"] = Character(
        id="friend",
        name="친구",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        max_hp=20,
        hp=20,
        relations={"player_01": 70},
    )
    fresh_state.characters["foe"] = Character(
        id="foe",
        name="적",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        max_hp=20,
        hp=8,
        relations={"player_01": -60},
    )
    fresh_state.characters["far"] = Character(
        id="far",
        name="먼사람",
        race_id="human",
        stats=Stats(),
        location_id="gate_01",
    )
    fresh_state.characters["dead"] = Character(
        id="dead",
        name="시체",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        alive=False,
    )

    sur = build_surroundings(fresh_state, "player_01")
    ids = {e["id"]: e for e in sur["entities"]}
    assert "player_01" in ids and ids["player_01"]["type"] == "player"
    assert "friend" in ids and "foe" in ids
    assert "far" not in ids and "dead" not in ids
    # NPC entries now carry gender/race/role instead of state_tags
    assert ids["friend"]["race"] == "인간"
    assert "state_tags" not in ids["friend"]
    assert ids["foe"]["race"] == "인간"
    assert "state_tags" not in ids["foe"]
    # adjacent connection
    assert (
        ids["gate_01"]["type"] == "connection"
        and ids["gate_01"]["difficulty"] == "hard"
    )


def test_entities_carry_role_tags(fresh_state):
    """Each NPC entry carries `roles` listing what the player can/can't do
    with them. Without this the LLM has no positive signal that an NPC is
    *not* trade-eligible (the existing `merchants` slot only carries the
    positives — silence isn't a signal). Verifies merchant + quest_giver."""
    from src.game.domain.entities import Item, Quest, QuestRewards

    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.items["bread"] = Item(id="bread", name="빵", price=2)
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        relations={},
    )
    # merchant: trade-eligible NPC carrying stock.
    fresh_state.characters["seller"] = Character(
        id="seller",
        name="상인",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        inventory_ids=["bread"],
        relations={"player_01": 0},  # >= trade_threshold default 0
    )
    # quest_giver: gives a quest, no stock.
    fresh_state.characters["chief"] = Character(
        id="chief",
        name="촌장",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        relations={"player_01": 0},
    )
    fresh_state.quests["q1"] = Quest(
        id="q1",
        title="t",
        giver_id="chief",
        difficulty="normal",
        rewards=QuestRewards(),
    )
    # plain villager: no merchant role, no quest. roles must be absent
    # (key omitted, not empty list — keeps payload tight).
    fresh_state.characters["villager"] = Character(
        id="villager",
        name="주민",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )

    sur = build_surroundings(fresh_state, "player_01")
    ids = {e["id"]: e for e in sur["entities"]}
    assert ids["seller"].get("roles") == ["merchant"]
    assert ids["chief"].get("roles") == ["quest_giver"]
    assert "roles" not in ids["villager"]


def test_entities_surface_protected_flag(fresh_state):
    """`protected=true` Character → entities entry carries `protected: true`
    so the classify LLM can override the friendly-attack→combat default and
    pass instead. Default `protected=false` NPCs omit the field (no payload bloat)."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    child = Character(
        id="mira",
        name="미라",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        max_hp=8,
        hp=8,
    )
    child.protected = True
    fresh_state.characters["mira"] = child
    fresh_state.characters["bandit"] = Character(
        id="bandit",
        name="산적",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        max_hp=20,
        hp=20,
    )

    sur = build_surroundings(fresh_state, "player_01")
    ids = {e["id"]: e for e in sur["entities"]}
    assert ids["mira"].get("protected") is True
    assert "protected" not in ids["bandit"]


def test_corpses_same_location_and_history_referenced(fresh_state):
    """Corpses payload covers two cases:
    - same-location dead NPC (no off_screen flag)
    - dead NPC referenced in turn_log from elsewhere (off_screen=true)
    """
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.locations["gate_01"] = Location(id="gate_01", name="성문")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="gate_01",  # player walked away from plaza
    )
    fresh_state.characters["here_corpse"] = Character(
        id="here_corpse",
        name="여기시체",
        race_id="human",
        stats=Stats(),
        location_id="gate_01",
        alive=False,
    )
    fresh_state.characters["plaza_corpse"] = Character(
        id="plaza_corpse",
        name="광장노파",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        alive=False,
    )
    fresh_state.characters["plaza_alive"] = Character(
        id="plaza_alive",
        name="광장상인",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    fresh_state.turn_log = [
        TurnLogEntry(turn=1, target="plaza_corpse", summary="노파와 대화"),
        TurnLogEntry(turn=2, target="plaza_alive", summary="상인과 대화"),
        TurnLogEntry(turn=3, target="plaza_corpse", summary="노파 사망"),
    ]

    sur = build_surroundings(fresh_state, "player_01")
    by_id = {c["id"]: c for c in sur["corpses"]}
    # same-location corpse — no off_screen flag
    assert "here_corpse" in by_id
    assert "off_screen" not in by_id["here_corpse"]
    # history-referenced dead NPC at different location — off_screen=true
    assert "plaza_corpse" in by_id and by_id["plaza_corpse"]["off_screen"] is True
    # alive NPC in turn_log must NOT be in corpses
    assert "plaza_alive" not in by_id


def test_corpses_dedupes_same_location_with_history(fresh_state):
    """A dead NPC at the same location as the player and also in turn_log
    should appear once, without the off_screen flag (same-location wins)."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    fresh_state.characters["here_corpse"] = Character(
        id="here_corpse",
        name="시체",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
        alive=False,
    )
    fresh_state.turn_log = [
        TurnLogEntry(turn=1, target="here_corpse", summary="대화"),
    ]

    sur = build_surroundings(fresh_state, "player_01")
    matches = [c for c in sur["corpses"] if c["id"] == "here_corpse"]
    assert len(matches) == 1
    assert "off_screen" not in matches[0]


def test_session_layer_active_only(fresh_state):
    fresh_state.chapters["ch1"] = Chapter(
        id="ch1",
        title="ch",
        summary="s",
        quest_ids=["q1", "q2"],
        status="active",
    )
    fresh_state.quests["q1"] = Quest(
        id="q1",
        title="t",
        summary="quest summary",
        giver_id="g",
        difficulty="normal",
        status="active",
    )
    fresh_state.quests["q2"] = Quest(
        id="q2",
        title="done",
        giver_id="g",
        difficulty="easy",
        status="completed",
    )

    out = build_session_layer(fresh_state)
    assert out["chapter"]["title"] == "ch"
    assert len(out["chapter"]["quests"]) == 1  # excludes completed
    q = out["chapter"]["quests"][0]
    assert q["title"] == "t"
    assert q["summary"] == "quest summary"


def test_history_layer_dedupes_dialogue_turns(fresh_state):
    fresh_state.turn_log = [
        TurnLogEntry(turn=1, summary="첫"),
        TurnLogEntry(turn=2, summary="둘"),
        TurnLogEntry(turn=3, summary="셋"),  # duplicate of recent_dialogue entry
    ]
    fresh_state.recent_dialogue = [
        DialoguePair(turn=3, player="p", narrator="n"),
    ]
    h = build_history_layer(fresh_state)
    assert "[턴 1] — 첫" in h
    assert "[턴 2] — 둘" in h
    assert "[턴 3] — 셋" not in h  # dedup
    assert "플레이어: p" in h


def test_history_layer_prepends_corpse_block_before_dialogue(fresh_state):
    """Dead NPCs whose name still appears in recent_dialogue prose must be
    flagged as dead in a block that the model reads before the dialogue
    excerpts — otherwise rich live-speech context drowns the death signal."""
    fresh_state.recent_dialogue = [
        DialoguePair(turn=5, player="안녕", narrator="노파가 미소 짓습니다."),
    ]
    h = build_history_layer(fresh_state, corpses=[{"id": "hag", "name": "노파"}])
    assert "사망" in h
    assert "노파" in h
    corpse_idx = h.index("사망")
    dialogue_idx = h.index("최근 대화")
    assert corpse_idx < dialogue_idx  # corpse signal lands before dialogue prose


def test_history_layer_omits_corpse_block_when_empty(fresh_state):
    fresh_state.recent_dialogue = [
        DialoguePair(turn=1, player="p", narrator="n"),
    ]
    h = build_history_layer(fresh_state, corpses=[])
    assert "사망" not in h


def test_history_layer_redacts_dead_npc_quotes_in_dialogue(fresh_state):
    """Direct-quote blocks attributed to a now-dead NPC inside `recent_dialogue`
    must be stripped before the prompt sees them. The "사망" header alone hasn't
    been enough — the LLM picks up the quote pattern from the inline narrator
    text and resurrects the speaker. With the redaction the model still sees
    the surrounding context (so it can write corpse-tone prose) but no longer
    has the speech to mimic."""
    fresh_state.recent_dialogue = [
        DialoguePair(
            turn=4,
            player="노파에게 인사한다",
            narrator="노파가 고개를 들어 봅니다. 「오랜만이오, 젊은이.」 손이 살짝 떨립니다.",
        ),
    ]
    h = build_history_layer(fresh_state, corpses=[{"id": "hag", "name": "노파"}])
    assert "「오랜만이오, 젊은이.」" not in h
    assert "노파가 고개를 들어 봅니다." in h  # surrounding prose kept
    assert "…" in h


def test_history_layer_keeps_live_npc_quotes(fresh_state):
    """Live NPCs (not in corpses) keep their dialogue intact — redaction is
    scoped to dead names only."""
    fresh_state.recent_dialogue = [
        DialoguePair(
            turn=4,
            player="상인에게 흥정한다",
            narrator="상인이 미소 짓습니다. 「오늘 좋은 물건이 있소.」",
        ),
    ]
    h = build_history_layer(fresh_state, corpses=[{"id": "hag", "name": "노파"}])
    assert "「오늘 좋은 물건이 있소.」" in h


async def test_world_layer_reads_md():
    with tempfile.TemporaryDirectory() as tmp:
        pdir = Path(tmp) / "default"
        pdir.mkdir()
        (pdir / "world.md").write_text("# world\n중세", encoding="utf-8")
        text = await build_world_layer(LocalFsScenarioRepo(profile_dir=tmp), "default")
        assert "중세" in text
