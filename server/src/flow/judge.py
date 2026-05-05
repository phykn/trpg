from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import ValidationError

from ..domain.errors import JudgeMalformed
from ..domain.types import StatKey, Tier
from ..llm_calls.classify import JudgeSemanticError, classify
from ..llm_calls.classify.schema import JudgeInput, JudgeOutput, Verb
from ..llm.client import LLMClient
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..context import build_surroundings
from ..mapping.labels import ROLL_REASON_DEFAULT


@dataclass(frozen=True)
class PendingCheckTrigger:
    """Semantic fallback 또는 verb-driven uncertainty 결과로 즉시 pending_check 발사가 필요한 경우.
    JudgeOutput과 별 type — turn.py가 isinstance로 분기.

    현재는 semantic fallback에서만 발사 (triggering_verb=None). 후속 uncertainty
    룰에서는 verb dispatch 안에서 같은 trigger를 생성해 emit_roll_pending_from_trigger 호출."""
    tier: Tier
    stat: StatKey
    targets: list[str]
    reason: str
    triggering_verb: Verb | None = None


class JudgeResult(TypedDict):
    outcome: Literal["satisfied", "partial", "rejected"]
    reason: str
    progress_delta: int | None


def _call_judge_llm(prompt: str, schema: type) -> dict:
    """LLM call wrapper — override in tests via monkeypatch."""
    # not yet wired; callers catch NotImplementedError.
    raise NotImplementedError(
        "Judge LLM integration not wired (test-only stub)."
    )


def judge_quest_progress(
    quest: dict,
    history: list[dict],
    claim: str | None,
    npc_context: dict | None,
) -> JudgeResult:
    """Free-path quest evaluation. LLM judges if player satisfied the objective.

    Args:
        quest: dict with at least id, objective_text
        history: recent engine event summaries
        claim: player's assertion if in dialogue (None for auto turn-end check)
        npc_context: {npc_id, favor} for NPC dialogue context (None for auto check)
    """
    history_text = (
        "\n".join(f"- {h.get('summary', str(h))}" for h in history) or "(없음)"
    )
    npc_block = (
        f"NPC: {npc_context.get('npc_id')}, 호감도: {npc_context.get('favor', 0)}"
        if npc_context
        else "(turn 종료 자동 체크)"
    )
    prompt = (
        f"[Quest 자유 경로 판정]\n"
        f"Quest 목표: {quest.get('objective_text', '(목표 없음)')}\n"
        f"\nPlayer 최근 행적:\n{history_text}\n"
        f"\nPlayer 주장: {claim or '(주장 없음)'}\n"
        f"{npc_block}\n"
        f"\n다음 enum 중 하나로 판정:\n"
        f"- satisfied: 목표를 충분히 달성했다고 인정. 보상 지급.\n"
        f"- partial: 일부 진행 — progress_delta로 누적량 반환.\n"
        f"- rejected: 충족 근거 부족.\n"
        f"\n진행 시그널 인식: 다음 행위도 quest 진행으로 인정합니다 — "
        f"의뢰자 NPC에게 결과를 보고하는 발화, 의뢰의 핵심 조건을 충족하는 다른 우회 행위(예: 처치 대신 추방·설득). "
        f"직전 turn_log에 quest의 trigger와 매칭되는 사건이 있고, "
        f"현재 행위가 그 결과를 의뢰자에게 알리거나 의뢰 완료 의사를 표현하면 satisfied로 판정합니다.\n"
    )
    return _call_judge_llm(prompt, schema=JudgeResult)


async def run_judge(
    client: LLMClient,
    state: GameState,
    player_input: str,
    *,
    graph: GameGraph | None = None,
) -> JudgeOutput | PendingCheckTrigger:
    """Call the classify LLM. After 5 self-correction retries inside the runner:
    - schema-only failure (ValidationError) → raise JudgeMalformed.
    - semantic failure (JudgeSemanticError) → return PendingCheckTrigger
      (WIS roll on player's current location — 현 동작 동일성 유지).

    `graph` is the relational SSOT — flow entry points pass the turn-start
    graph so build_surroundings doesn't rebuild. Test/ad-hoc callers can omit.
    """
    surroundings = build_surroundings(state, state.player_id, graph)
    history = [
        {"turn": e.turn, "target": e.target, "summary": e.summary}
        for e in state.turn_log[-5:]
    ]
    recent_dialogue = [
        {"turn": d.turn, "player": d.player, "narrator": d.narrator}
        for d in state.recent_dialogue[-2:]
    ]
    try:
        return await classify(
            client,
            JudgeInput(
                player_input=player_input,
                surroundings=surroundings,
                history=history,
                recent_dialogue=recent_dialogue,
            ),
        )
    except ValidationError as e:
        raise JudgeMalformed(str(e)) from e
    except JudgeSemanticError as e:
        loc_id = state.characters[state.player_id].location_id
        if loc_id is None:
            raise JudgeMalformed(
                f"semantic fallback impossible: no location ({e})"
            ) from e
        return PendingCheckTrigger(
            tier="normal",
            stat="WIS",
            targets=[loc_id],
            reason=ROLL_REASON_DEFAULT,
            triggering_verb=None,
        )
