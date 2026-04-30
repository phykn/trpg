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
            f"[prev turn] me: {p}\n  → narrator: {n[:200]}"
            for p, n in self.history[-3:]
        ) or "(none yet)"

        if self.max_turns:
            turn_line = f"This turn: {turn_no}/{self.max_turns}"
        else:
            turn_line = f"This turn: {turn_no}"

        user_msg = (
            f"=== {turn_line} ===\n\n"
            "=== Current situation ===\n"
            f"{state_summary}\n\n"
            "=== Priority guards (override the persona's '진행 순서' table) ===\n"
            "If either trigger below is on, ignore the persona's '진행 순서' table and emit that action as this turn's input. Once the trigger clears, return to the table.\n"
            "1. **Level-up trigger**: if the '나' line shows '레벨업 가능', this turn's input must be a one-liner like '성장한다' / '더 강해진다' / '더 똑똑해진다' / 'STR 을 올리고 CHA 를 내린다'. Even if the persona has its own flavor, this one turn must be a growth attempt (return to the schedule next turn).\n"
            "2. **Skill-candidate trigger**: if the previous GM output mentions options like '익힐 수 있는 기술' / 'skill_candidates' / '몇 번' / '첫째·둘째·셋째', this turn's input must pick a candidate index, e.g. '첫 번째를 익힌다' / '치유 쪽을 배운다'.\n\n"
            "=== Previous narrator output ===\n"
            f"{last_gm or '(none)'}\n\n"
            "=== Recent flow ===\n"
            f"{recent_block}\n\n"
            "=== Next action ===\n"
            "If both priority guards are clear, look at the persona's '진행 순서' table in the system prompt and emit, as one Korean line, the action this turn calls for. No headers or meta-commentary."
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
