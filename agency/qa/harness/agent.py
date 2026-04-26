from pathlib import Path

from src.llm import LLMClient


class PlayerAgent:
    """QA 플레이어. system prompt = 성향, 매 턴 LLM 한 번 호출해 다음 입력 한 줄 생성."""

    def __init__(self, name: str, prompt_path: Path, llm: LLMClient):
        self.name = name
        self.system = prompt_path.read_text(encoding="utf-8")
        self.llm = llm
        self.history: list[tuple[str, str]] = []  # (player_input, gm_body)

    async def next_input(self, state_summary: str, last_gm: str) -> str:
        recent_block = "\n".join(
            f"[지난 턴] 나: {p}\n  → 서술자: {n[:200]}"
            for p, n in self.history[-3:]
        ) or "(아직 없음)"

        user_msg = (
            "=== 현재 상황 ===\n"
            f"{state_summary}\n\n"
            "=== 직전 서술자 출력 ===\n"
            f"{last_gm or '(없음)'}\n\n"
            "=== 최근 흐름 ===\n"
            f"{recent_block}\n\n"
            "=== 다음 행동 ===\n"
            "너의 성향대로 다음에 할 행동을 한국어 한 줄로. 머리표/메타 금지."
        )
        result = await self.llm.chat(
            [
                {"role": "system", "content": self.system},
                {"role": "user", "content": user_msg},
            ],
            think=False,
        )
        text = (result["answer"] or "").strip()
        # LLM 이 따옴표·머리표를 붙이는 경우 정제
        text = text.strip('"').strip("'").strip()
        for prefix in ("다음 행동:", "행동:", "플레이어:", "나:", "주인공:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text or "주변을 둘러본다."

    def record(self, player_input: str, gm_body: str) -> None:
        self.history.append((player_input, gm_body))
