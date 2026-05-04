from src.domain.memory import PendingCheck


def test_pending_check_default_kind_is_stat():
    pc = PendingCheck(
        player_input="test",
        tier="보통",
        stat="CHA",
        target="npc.1",
        targets=["npc.1"],
        dc=10,
        mod=0,
        required_roll=10,
        reason="test",
        created_at="2026-05-04T00:00:00",
    )
    assert pc.kind == "stat"


def test_pending_check_recruit_kind():
    pc = PendingCheck(
        player_input="test",
        kind="recruit",
        tier="보통",
        stat="CHA",
        target="npc.1",
        targets=["npc.1"],
        dc=10,
        mod=0,
        required_roll=10,
        reason="동료 영입",
        created_at="2026-05-04T00:00:00",
    )
    assert pc.kind == "recruit"
