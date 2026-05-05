"""LLM quest judge — free-path satisfaction evaluator."""

from server.src.game.flow.judge import judge_quest_progress


def test_satisfied_when_history_supports_claim(monkeypatch):
    """History has kill record, player asserts → satisfied."""

    def mock_call(*args, **kwargs):
        return {
            "outcome": "satisfied",
            "reason": "처치 기록 확인",
            "progress_delta": None,
        }

    monkeypatch.setattr(
        "server.src.game.flow.judge._call_judge_llm", mock_call, raising=False
    )
    quest = {"id": "q1", "objective_text": "산문 길 약탈자 처치"}
    history = [{"type": "combat", "summary": "고블린 약탈자 처치 (HP 0)"}]
    npc_context = {"npc_id": "edric", "favor": 0}
    result = judge_quest_progress(
        quest, history, claim="처치했습니다", npc_context=npc_context
    )
    assert result["outcome"] == "satisfied"
    assert "reason" in result


def test_rejected_when_no_evidence(monkeypatch):
    """No history support → rejected."""

    def mock_call(*args, **kwargs):
        return {"outcome": "rejected", "reason": "근거 부족", "progress_delta": None}

    monkeypatch.setattr(
        "server.src.game.flow.judge._call_judge_llm", mock_call, raising=False
    )
    quest = {"id": "q1", "objective_text": "산문 길 약탈자 처치"}
    result = judge_quest_progress(
        quest,
        history=[],
        claim="처치했습니다",
        npc_context={"npc_id": "edric", "favor": 0},
    )
    assert result["outcome"] == "rejected"


def test_partial_outcome_with_progress_delta(monkeypatch):
    """Partial credit — quest progresses but not done."""

    def mock_call(*args, **kwargs):
        return {"outcome": "partial", "reason": "1/2 처치", "progress_delta": 1}

    monkeypatch.setattr(
        "server.src.game.flow.judge._call_judge_llm", mock_call, raising=False
    )
    quest = {"id": "q1", "objective_text": "약탈자 둘 처치"}
    history = [{"type": "combat", "summary": "약탈자 1마리 처치"}]
    result = judge_quest_progress(quest, history, claim="모두 처치", npc_context=None)
    assert result["outcome"] == "partial"
    assert result["progress_delta"] == 1


def test_no_npc_context_for_turn_end_check(monkeypatch):
    """Turn-end auto check passes None npc_context."""

    def mock_call(*args, **kwargs):
        return {"outcome": "rejected", "reason": "", "progress_delta": None}

    monkeypatch.setattr(
        "server.src.game.flow.judge._call_judge_llm", mock_call, raising=False
    )
    result = judge_quest_progress(
        quest={"id": "q1", "objective_text": "산문 길 약탈자 처치"},
        history=[],
        claim=None,
        npc_context=None,
    )
    assert result["outcome"] in ("satisfied", "partial", "rejected")
