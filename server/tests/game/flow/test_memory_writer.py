from src.game.domain.entities import Character, Stats
from src.game.domain.memory import Memory
from src.llm.calls.narrate import NarrateOutput
from src.game.flow.memory_writer import write_memories
from src.game.rules import RULES


def _state_with_two_chars(fresh_state):
    fresh_state.characters["p"] = Character(
        id="p", name="P", race_id="human", stats=Stats()
    )
    fresh_state.characters["g"] = Character(
        id="g", name="G", race_id="human", stats=Stats()
    )
    return fresh_state


def test_memorable_false_skips(fresh_state):
    s = _state_with_two_chars(fresh_state)
    n = write_memories(s, NarrateOutput(memorable=False, memory={"g": "x"}), turn=1)
    assert n == 0
    assert s.characters["g"].memories == []


def test_memory_links_target_id_per_entity(fresh_state):
    s = _state_with_two_chars(fresh_state)
    n = write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["g", "p"],
            memory={"g": "낯선 자가 뇌물", "p": "내가 경비병에게 뇌물"},
            importance=2,
            memory_links={"g": "p", "p": "g"},
        ),
        turn=17,
    )
    assert n == 2
    assert s.characters["g"].memories[0].content == "낯선 자가 뇌물"
    assert s.characters["g"].memories[0].target_id == "p"
    assert s.characters["p"].memories[0].content == "내가 경비병에게 뇌물"
    assert s.characters["p"].memories[0].target_id == "g"


def test_memory_links_missing_entity_target_id_none(fresh_state):
    s = _state_with_two_chars(fresh_state)
    write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["g"],
            memory={"g": "혼자"},
            importance=1,
            memory_links={},
        ),
        turn=18,
    )
    assert s.characters["g"].memories[-1].target_id is None


def test_entity_without_memory_text_is_skipped(fresh_state):
    s = _state_with_two_chars(fresh_state)
    n = write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["g", "p"],
            memory={"g": "G 시점만"},  # no p key
            importance=1,
        ),
        turn=20,
    )
    assert n == 1
    assert s.characters["g"].memories[0].content == "G 시점만"
    assert s.characters["p"].memories == []


def test_empty_memory_text_skipped(fresh_state):
    s = _state_with_two_chars(fresh_state)
    n = write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["g", "p"],
            memory={"g": "G", "p": ""},  # empty p
            importance=1,
        ),
        turn=21,
    )
    assert n == 1
    assert s.characters["p"].memories == []


def test_cap_evicts_lowest_importance_then_oldest_turn(fresh_state):
    s = _state_with_two_chars(fresh_state)
    cap = RULES.memory.cap
    # cap-1 entries at importance=1 + 1 at importance=3
    for i in range(cap - 1):
        s.characters["g"].memories.append(
            Memory(content=f"old{i}", importance=1, turn=i + 1)
        )
    s.characters["g"].memories.append(Memory(content="중요", importance=3, turn=cap))

    write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["g"],
            memory={"g": "새것"},
            importance=2,
            memory_links={},
        ),
        turn=cap + 1,
    )

    assert len(s.characters["g"].memories) == cap
    contents = {m.content for m in s.characters["g"].memories}
    assert "old0" not in contents  # weakest entry is evicted
    assert "중요" in contents
    assert "새것" in contents


def test_unknown_entity_id_silently_skipped(fresh_state):
    s = _state_with_two_chars(fresh_state)
    n = write_memories(
        s,
        NarrateOutput(
            memorable=True,
            memory_targets=["ghost"],
            memory={"ghost": "x"},
            importance=1,
        ),
        turn=99,
    )
    assert n == 0
