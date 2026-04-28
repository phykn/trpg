from pathlib import Path

from src.llm import LLMClient


class PlayerAgent:
    """QA player. The system prompt encodes a persona; one LLM call per turn yields the next single-line input."""

    def __init__(self, name: str, prompt_path: Path, llm: LLMClient, max_turns: int = 0):
        self.name = name
        self.system = prompt_path.read_text(encoding="utf-8")
        self.llm = llm
        self.max_turns = max_turns
        self.history: list[tuple[str, str]] = []  # (player_input, gm_body)

    async def next_input(
        self, state_summary: str, last_gm: str, turn_no: int = 0
    ) -> str:
        recent_block = "\n".join(
            f"[지난 턴] 나: {p}\n  → 서술자: {n[:200]}"
            for p, n in self.history[-3:]
        ) or "(아직 없음)"

        if self.max_turns:
            turn_line = f"이번 턴: {turn_no}/{self.max_turns}"
        else:
            turn_line = f"이번 턴: {turn_no}"

        user_msg = (
            f"=== {turn_line} ===\n\n"
            "=== 현재 상황 ===\n"
            f"{state_summary}\n\n"
            "=== 우선순위 가드 (페르소나 표보다 먼저) ===\n"
            "아래 두 트리거 중 하나라도 켜져 있으면 페르소나의 '진행 순서' 표를 무시하고 그 행동을 이번 턴 입력으로 내라. 트리거가 꺼지면 표로 복귀.\n"
            "1. **레벨업 트리거**: '나' 줄에 '레벨업 가능' 표시가 있으면 이번 턴 입력은 '성장한다' / '더 강해진다' / '더 똑똑해진다' / 'STR 을 올리고 CHA 를 내린다' 식 한 줄. 페르소나 색깔이 있어도 이 한 턴은 성장 시도여야 한다 (다음 턴부터 표 복귀).\n"
            "2. **스킬 후보 트리거**: 직전 턴 GM 출력에 '익힐 수 있는 스킬' / 'skill_candidates' / '몇 번' / '첫째·둘째·셋째' 같은 후보 제시 표현이 있으면 이번 턴 입력은 '첫 번째를 익힌다' / '치유 쪽을 배운다' 같이 candidate index 를 고르는 한 줄.\n\n"
            "=== 직전 서술자 출력 ===\n"
            f"{last_gm or '(없음)'}\n\n"
            "=== 최근 흐름 ===\n"
            f"{recent_block}\n\n"
            "=== 다음 행동 ===\n"
            "위 우선순위 가드가 모두 비어 있으면, 시스템 프롬프트의 페르소나 '진행 순서' 표를 보고 이번 턴이 가리키는 행동을 한국어 한 줄로 내라. 머리표/메타 금지."
        )
        result = await self.llm.chat(
            [
                {"role": "system", "content": self.system},
                {"role": "user", "content": user_msg},
            ],
            think=False,
            agent=f"qa_player_{self.name}",
        )
        text = (result["answer"] or "").strip()
        # strip quotes / leading labels the LLM sometimes adds
        text = text.strip('"').strip("'").strip()
        for prefix in ("다음 행동:", "행동:", "플레이어:", "나:", "주인공:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text or "주변을 둘러본다."

    def record(self, player_input: str, gm_body: str) -> None:
        self.history.append((player_input, gm_body))
