"""Verify dead entity's hints (death fact) surface in subject.known."""

from src.domain.entities import Character, Race, Stats
from src.mapping.to_front import to_subject


def _minimal_state(fresh_state, *, npc_hints=None, npc_alive=True):
    s = fresh_state
    s.races["human"] = Race(id="human", name="인간", description="x")
    s.characters["player_01"] = Character(
        id="player_01", name="주인공", race_id="human", stats=Stats()
    )
    s.characters["npc_01"] = Character(
        id="npc_01",
        name="용의자",
        race_id="human",
        appearance="수상한 인물",
        alive=npc_alive,
        hp=0 if not npc_alive else 20,
        max_hp=20,
        hints=npc_hints or [],
        stats=Stats(),
    )
    s.active_subject_id = "npc_01"
    return s


def test_dead_entity_hints_appear_in_known(fresh_state):
    state = _minimal_state(
        fresh_state,
        npc_hints=["주인공에게 살해당했다."],
        npc_alive=False,
    )
    result = to_subject(state)
    assert result is not None
    assert "주인공에게 살해당했다." in result["known"]


def test_hints_appear_even_when_alive(fresh_state):
    state = _minimal_state(
        fresh_state,
        npc_hints=["비밀을 알고 있다."],
        npc_alive=True,
    )
    result = to_subject(state)
    assert result is not None
    assert "비밀을 알고 있다." in result["known"]
    # appearance still present for living NPC
    assert "수상한 인물" in result["known"]


def test_hints_ordered_after_appearance_before_memories(fresh_state):
    from src.domain.memory import Memory

    state = _minimal_state(
        fresh_state,
        npc_hints=["힌트A"],
        npc_alive=True,
    )
    state.characters["player_01"].memories = [
        Memory(content="기억B", importance=1, turn=1, target_id="npc_01")
    ]
    result = to_subject(state)
    assert result is not None
    known = result["known"]
    assert known == ["수상한 인물", "힌트A", "기억B"]


def test_empty_hints_no_regression(fresh_state):
    state = _minimal_state(fresh_state, npc_hints=[], npc_alive=True)
    result = to_subject(state)
    assert result is not None
    assert result["known"] == ["수상한 인물"]
