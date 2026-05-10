"""One-shot smoke check: call the classify LLM against the env-routed LLM to
verify the production prompt path (kernel + agent rules + substitutions) works.

Run from repo root:
  .venv/bin/python server/scripts/smoke_classify.py

Loads .env.dev to mirror run_api.py.
Exits 0 if every case parses to a valid action; non-zero otherwise.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

load_dotenv(SERVER_DIR / ".env.dev")

from src.llm.calls.classify import classify  # noqa: E402
from src.llm.calls.classify.schema import ClassifyInput  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402

SAMPLE_SURROUNDINGS = {
    "location": {"id": "isnar_square", "name": "이스나르 광장"},
    "entities": [
        {"id": "player_01", "name": "주인공", "type": "player"},
        {"id": "guard_01", "name": "경비병", "type": "npc"},
        {"id": "merchant_01", "name": "광장 상인", "type": "npc"},
    ],
    "corpses": [],
    "skills": [],
    "inventory": [],
    "equipment": {},
    "in_combat": False,
    "growth": {"can_level_up": False},
    "merchants": [
        {
            "id": "merchant_01",
            "name": "광장 상인",
            "stock": [{"id": "healing_potion_01", "name": "회복약", "price": 5}],
        }
    ],
    "recent_npc": "guard_01",
}

CASES: list[tuple[str, str]] = [
    ("경비병에게 인사한다", "speak(to=guard_01, how=friendly)"),
    ("회복약을 산다", "transfer(from=merchant_01, to=player_01, how=trade, what=healing_potion_01)"),
    ("경비병을 설득해 통과시켜달라", "speak(to=guard_01, how=friendly|deceptive)"),
    ("뭔가 해봐", "pass (vague)"),
]


async def main() -> int:
    print("Loading LLMClient from env routing...")
    client = LLMClient.from_env()
    providers = client._providers
    default_route = providers["default"].model
    classify_route = providers.get("classify", providers["default"]).model
    print(f"  default route: {default_route}")
    print(f"  classify route: {classify_route}")
    print()

    failed = 0
    for player_input, hint in CASES:
        print(f"--- INPUT: {player_input!r}  (expect: {hint})")
        try:
            result = await classify(
                client,
                ClassifyInput(player_input=player_input, surroundings=SAMPLE_SURROUNDINGS),
                locale="ko",
                retries=2,
            )
            print(f"    OK  {result.model_dump_json()}")
        except Exception as e:
            failed += 1
            print(f"    FAIL  {type(e).__name__}: {e}")
        print()

    print(f"Result: {len(CASES) - failed}/{len(CASES)} cases passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
