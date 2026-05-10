"""One-shot smoke check for movement classification: replays user-reported
inputs against the env-routed classify LLM (Gemini) to see whether `move`
fires for adjacent connections.

Run from repo root:
  .venv/bin/python server/scripts/smoke_move.py

Loads .env.dev. Surroundings mirror the isnar_square seed (player_01 standing
at the village square, six connections including gray_raven_inn and
herb_garden). Calls the classify runner directly so the markdown-fence /
retry handling matches production.
"""

import asyncio
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

load_dotenv(SERVER_DIR / ".env.dev")

from src.llm.calls._runner import get_prompt  # noqa: E402
from src.llm.calls.classify.schema import ClassifyInput, validate_action_output_json  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.MULTILINE)


def _strip_fence(answer: str) -> str:
    """Some Gemma routes wrap the JSON in a markdown code fence. Strip it
    before json.loads — production sees this through the retry loop, but a
    smoke script wants a clean view of the first response."""
    return _FENCE_RE.sub("", answer).strip()

SURROUNDINGS = {
    "location": {
        "id": "isnar_square",
        "name": "이스나르 광장",
        "description": "변경 마을 한가운데 자리 잡은 돌이 닳은 광장.",
        "tags": ["outdoor", "town"],
        "weather": ["옅은 안개"],
    },
    "entities": [
        {"id": "player_01", "name": "주인공", "type": "player"},
        {
            "id": "edrik_chief",
            "name": "에드릭",
            "type": "npc",
            "gender": "male",
            "race": "인간",
            "role": "이스나르 촌장",
            "relations_player": 0,
            "roles": ["merchant", "quest_giver"],
        },
        {
            "id": "mira_kid",
            "name": "미라",
            "type": "npc",
            "gender": "female",
            "race": "인간",
            "role": "광장 분수 곁의 마을 어린이",
            "relations_player": 0,
        },
        {
            "id": "bandit_01",
            "name": "산적",
            "type": "npc",
            "gender": "male",
            "race": "인간",
            "role": "광장에 들이닥친 약탈자",
            "relations_player": -50,
        },
        {"id": "gray_raven_inn", "name": "잿빛 까마귀 여관", "type": "connection"},
        {"id": "general_store", "name": "오린의 잡화", "type": "connection"},
        {"id": "forge_smithy", "name": "탈크의 대장간", "type": "connection"},
        {"id": "starlight_shrine", "name": "별빛 신전", "type": "connection"},
        {"id": "herb_garden", "name": "셀레나의 약초원", "type": "connection"},
        {"id": "watch_post", "name": "마을 망루", "type": "connection"},
    ],
    "corpses": [],
    "skills": [
        {"id": "heal_minor", "name": "소소한 치유", "type": "heal"},
    ],
    "inventory": [
        {"id": "herb_01", "name": "약초", "kind": "consumable"},
        {"id": "shortsword_01", "name": "단검", "kind": "weapon"},
    ],
    "equipment": {"weapon": None, "armor": None, "accessory": None},
    "in_combat": False,
    "growth": {"can_level_up": False},
    "merchants": [
        {
            "id": "edrik_chief",
            "name": "에드릭",
            "stock": [{"id": "rope_01", "name": "밧줄", "price": 3}],
        }
    ],
    "recent_npc": None,
    "companions": [],
    "companions_max": 3,
}

CASES: list[tuple[str, str]] = [
    # --- move ---
    ("셀레나의 약초원으로 이동합니다", "move(to=herb_garden)"),
    ("잿빛 까마귀 여관으로 이동합니다", "move(to=gray_raven_inn)"),
    ("흑탑으로 이동한다", "wait (not in connections)"),
    # --- speak ---
    ("에드릭에게 인사한다", "speak(to=edrik_chief, how=friendly)"),
    ("미라에게 말을 건다", "speak(to=mira_kid, how=friendly)"),
    # --- attack ---
    ("산적을 공격한다", "attack(what=[bandit_01])"),
    # --- use ---
    ("약초를 마신다", "use(what=herb_01)"),
    # --- transfer (equip) ---
    ("단검을 장착한다", "transfer(how=equip, what=shortsword_01)"),
    # --- cast (heal) ---
    ("소소한 치유를 시전한다", "cast(with=heal_minor)"),
    # --- perceive / wait ---
    ("주변을 둘러본다", "perceive"),
    ("한숨을 내쉰다", "wait"),
]

REPEATS = 1  # one shot — what does the LLM produce on its first attempt?


async def main() -> int:
    print("Loading LLMClient from env routing...")
    client = LLMClient.from_env()
    providers = client._providers
    default_route = providers["default"].model
    classify_route = providers.get("classify", providers["default"]).model
    print(f"  default route: {default_route}")
    print(f"  classify route: {classify_route}")
    print()

    sys_prompt = get_prompt("classify", "ko")
    total = 0
    pass_count = 0
    schema_fail_count = 0
    transport_fail_count = 0
    raw_collisions: list[tuple[str, str, str]] = []  # (input, raw, error)
    for player_input, expected in CASES:
        print(f"--- INPUT: {player_input!r}  (expect: {expected})")
        inp = ClassifyInput(player_input=player_input, surroundings=SURROUNDINGS)
        msgs = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": inp.model_dump_json()},
        ]
        for i in range(REPEATS):
            total += 1
            try:
                resp = await client.chat(
                    messages=msgs, think=False, agent="classify", temperature=1.0
                )
            except Exception as e:
                transport_fail_count += 1
                print(f"    [{i + 1}] TRANSPORT_FAIL  {type(e).__name__}: {e}")
                continue
            cleaned = _strip_fence(resp["answer"] or "")
            if not cleaned:
                schema_fail_count += 1
                print(f"    [{i + 1}] EMPTY  (think={resp.get('think', '')[:80]!r})")
                continue
            try:
                parsed = validate_action_output_json(cleaned, in_combat=False)
            except Exception as e:
                schema_fail_count += 1
                raw_collisions.append((player_input, cleaned[:300], str(e)[:200]))
                print(f"    [{i + 1}] SCHEMA_FAIL  raw={cleaned[:150]!r}  err={type(e).__name__}: {str(e)[:120]}")
                continue
            pass_count += 1
            print(f"    [{i + 1}] OK            {parsed.model_dump_json()}")
        print()

    print(f"Result: {pass_count}/{total} validated; {schema_fail_count} schema fails, {transport_fail_count} transport fails.")
    if raw_collisions:
        print()
        print("=== schema-fail samples (LLM shape vs schema) ===")
        for inp, raw, err in raw_collisions[:8]:
            print(f"  input: {inp!r}")
            print(f"    raw: {raw}")
            print(f"    err: {err}")
            print()
    return 0 if (schema_fail_count == 0 and transport_fail_count == 0) else 1



if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
