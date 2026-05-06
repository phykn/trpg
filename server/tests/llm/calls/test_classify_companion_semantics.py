import pytest

from src.llm.calls.classify.schema import JudgeOutput, Verb
from src.llm.calls.classify.semantics import JudgeSemanticError, check_semantics


def _surroundings(*, entities=(), companions=(), max_companions=3):
    return {
        "entities": list(entities),
        "companions": list(companions),
        "companions_max": max_companions,
    }


def _npc(npc_id, *, friendly=True, protected=False, relations_player=10):
    return {
        "id": npc_id,
        "type": "npc",
        "friendly": friendly,
        "protected": protected,
        "relations_player": relations_player,
    }


def _recruit_output(target: str) -> JudgeOutput:
    return JudgeOutput(
        actions=[Verb(name="speak", modifiers={"intent": "recruit", "target": target})]
    )


def _dismiss_output(target: str) -> JudgeOutput:
    return JudgeOutput(
        actions=[Verb(name="speak", modifiers={"intent": "part", "target": target})]
    )


def test_recruit_valid_friendly_npc():
    surroundings = _surroundings(entities=[_npc("npc.edric")])
    check_semantics(_recruit_output("npc.edric"), surroundings)


def test_recruit_target_not_in_surroundings():
    surroundings = _surroundings(entities=[_npc("npc.edric")])
    with pytest.raises(JudgeSemanticError, match="not in surroundings"):
        check_semantics(_recruit_output("npc.unknown"), surroundings)


def test_recruit_hostile_rejected():
    surroundings = _surroundings(entities=[_npc("npc.bandit", relations_player=-30)])
    with pytest.raises(JudgeSemanticError, match="hostile"):
        check_semantics(_recruit_output("npc.bandit"), surroundings)


def test_recruit_neutral_boundary_passes():
    surroundings = _surroundings(entities=[_npc("npc.edge", relations_player=0)])
    check_semantics(_recruit_output("npc.edge"), surroundings)


def test_recruit_just_hostile_boundary():
    surroundings = _surroundings(entities=[_npc("npc.edge", relations_player=-1)])
    with pytest.raises(JudgeSemanticError, match="hostile"):
        check_semantics(_recruit_output("npc.edge"), surroundings)


def test_recruit_protected_rejected():
    surroundings = _surroundings(entities=[_npc("npc.child", protected=True)])
    with pytest.raises(JudgeSemanticError, match="protected"):
        check_semantics(_recruit_output("npc.child"), surroundings)


def test_recruit_already_companion_rejected():
    surroundings = _surroundings(
        entities=[_npc("npc.edric")],
        companions=["npc.edric"],
    )
    with pytest.raises(JudgeSemanticError, match="already a companion"):
        check_semantics(_recruit_output("npc.edric"), surroundings)


def test_recruit_at_capacity_rejected():
    surroundings = _surroundings(
        entities=[_npc("npc.edric"), _npc("npc.a"), _npc("npc.b"), _npc("npc.c")],
        companions=["npc.a", "npc.b", "npc.c"],
        max_companions=3,
    )
    with pytest.raises(JudgeSemanticError, match="capacity"):
        check_semantics(_recruit_output("npc.edric"), surroundings)


def test_dismiss_valid_companion():
    surroundings = _surroundings(
        entities=[_npc("npc.edric")],
        companions=["npc.edric"],
    )
    check_semantics(_dismiss_output("npc.edric"), surroundings)


def test_dismiss_not_a_companion_rejected():
    surroundings = _surroundings(entities=[_npc("npc.edric")])
    with pytest.raises(JudgeSemanticError, match="not a companion"):
        check_semantics(_dismiss_output("npc.edric"), surroundings)
