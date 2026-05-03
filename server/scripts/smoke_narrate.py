"""Smoke check the narrate chain (body + extract) against the env-routed LLM.

Run from repo root:
  .venv/bin/python server/scripts/smoke_narrate.py

Streams a single sample turn through stream_narrate (body + extract) using the
env config so prompts hit Gemini exactly as production does. Exits 0 if a body
streamed and metadata parsed; non-zero otherwise.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

load_dotenv(SERVER_DIR / ".env.dev")

from src.llm.client import LLMClient  # noqa: E402
from src.llm_calls.narrate import (  # noqa: E402
    NarrateInput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)


async def main() -> int:
    client = LLMClient.from_env()
    providers = client._providers
    print(
        f"narrate_body    : {providers.get('narrate_body', providers['default']).model}"
    )
    print(
        f"narrate_extract : {providers.get('narrate_extract', providers['default']).model}"
    )
    print()

    input_ = NarrateInput(
        world="중세 판타지. 광장은 활기차다.",
        session={"chapter": "프롤로그", "quest": ""},
        history="",
        player_view={
            "name": "주인공",
            "race": {"name": "인간", "description": ""},
            "appearance": "",
            "description": "",
            "gender": "male",
        },
        surroundings={
            "location": {"id": "isnar_square", "name": "이스나르 광장"},
            "entities": [
                {"id": "guard_01", "name": "경비병", "type": "npc"},
            ],
            "corpses": [],
            "skills": [],
            "inventory": [],
            "equipment": {},
            "in_combat": False,
            "growth": {"can_level_up": False},
            "skill_candidates": [],
            "merchants": [],
            "recent_npc": "guard_01",
        },
        judge_result={"action": "pass", "targets": ["guard_01"]},
        player_input="경비병에게 인사한다",
    )

    print("--- streaming body ---")
    body = ""
    final: NarrativeFinal | None = None
    async for ev in stream_narrate(client, input_):
        if isinstance(ev, NarrativeDelta):
            print(ev.text, end="", flush=True)
            body += ev.text
        else:
            final = ev
    print()
    print()
    print("--- metadata ---")
    if final is None:
        print("FAIL: no NarrativeFinal received")
        return 1
    print(f"turn_summary  : {final.output.turn_summary!r}")
    print(f"state_changes : {final.output.state_changes}")
    print(f"suggestions   : {final.output.suggestions}")
    print(f"memorable     : {final.output.memorable}")
    print(f"importance    : {final.output.importance}")
    print(f"parse_error   : {final.parse_error}")
    if not body.strip():
        print("FAIL: empty body")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
