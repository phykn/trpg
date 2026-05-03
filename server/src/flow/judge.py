from typing import Literal, TypedDict

from pydantic import ValidationError

from ..domain.errors import JudgeMalformed
from ..llm_calls.classify import JudgeSemanticError, classify
from ..llm_calls.classify.schema import JudgeInput, JudgeOutput, RollAction
from ..llm.client import LLMClient
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..context import build_surroundings


class JudgeResult(TypedDict):
    outcome: Literal["satisfied", "partial", "rejected"]
    reason: str
    progress_delta: int | None


def _call_judge_llm(prompt: str, schema: type) -> dict:
    """LLM call wrapper — override in tests via monkeypatch."""
    # real LLM wiring lands in Task 10; stub raises to surface accidental live calls
    raise NotImplementedError("Judge LLM integration not wired in this cycle (test-only stub).")


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
    history_text = "\n".join(f"- {h.get('summary', str(h))}" for h in history) or "(없음)"
    npc_block = (
        f"NPC: {npc_context.get('npc_id')}, 호감도: {npc_context.get('favor', 0)}"
        if npc_context else "(turn 종료 자동 체크)"
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
    )
    return _call_judge_llm(prompt, schema=JudgeResult)


async def run_judge(
    client: LLMClient,
    state: GameState,
    player_input: str,
    *,
    graph: GameGraph | None = None,
) -> JudgeOutput:
    """Call the classify LLM. After 5 self-correction retries inside the runner:
    - schema-only failure (ValidationError) → raise JudgeMalformed.
    - semantic failure (JudgeSemanticError) → fall back to a roll on the
      player's current location (docs/02-runtime §2.3 step 3).

    `graph` is the relational SSOT — flow entry points pass the turn-start
    graph so build_surroundings doesn't rebuild. Test/ad-hoc callers can omit.
    """
    surroundings = build_surroundings(state, state.player_id, graph)
    try:
        return await classify(
            client,
            JudgeInput(player_input=player_input, surroundings=surroundings),
        )
    except ValidationError as e:
        raise JudgeMalformed(str(e)) from e
    except JudgeSemanticError as e:
        loc_id = state.characters[state.player_id].location_id
        if loc_id is None:
            raise JudgeMalformed(
                f"semantic fallback impossible: no location ({e})"
            ) from e
        return RollAction(action="roll", tier="보통", stat="WIS", targets=[loc_id])
