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
            f"=== {turn_line} ===\n"
            "프롬프트의 '진행 순서' 표를 보고 이번 턴이 가리키는 행동을 골라라.\n\n"
            "=== 현재 상황 ===\n"
            f"{state_summary}\n\n"
            "=== 직전 서술자 출력 ===\n"
            f"{last_gm or '(없음)'}\n\n"
            "=== 최근 흐름 ===\n"
            f"{recent_block}\n\n"
            "=== 공통 행동 가이드 ===\n"
            "- '나' 줄에 '레벨업 가능' 이 보이면, 한 턴은 '성장한다' / '더 강해진다' / '더 똑똑해진다' 같은 표현으로 level_up 을 먼저 시도하라 (페르소나에 별도 지침이 없어도). 레벨업 직후 skill_candidates 가 떠 있다면 그 다음 턴에 '치유 쪽을 익힌다' 같은 표현으로 learn_skill 도 시도하라.\n"
            "- 직전 GM 출력이 같은 의미의 clarify/되묻기를 두 번 이상 반복했다면 같은 입력을 또 던지지 말고 페르소나 안에서 다른 결을 찾아 한 가지 구체 행동으로 좁혀라.\n\n"
            "=== 다음 행동 ===\n"
            "너의 성향대로 다음에 할 행동을 한국어 한 줄로. 머리표/메타 금지."
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
