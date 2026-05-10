"""Temperature comparison for the classify agent.

Runs STRESS + ADVERSARIAL cases at temp=0.2 and temp=1.0, rate-limited to
~10 calls/min for hosted provider quotas.

DISTINCTION (8 cases) was already covered in the prior run (8/8 tied at both
temps). This run focuses on the harder categories where temps may diverge.

Total: 23 cases × 2 temps = 46 calls. Sleeps 6s between calls → ~5 min.

Run from repo root:
  .venv/bin/python server/scripts/temp_compare.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

load_dotenv(SERVER_DIR / ".env.dev")

from src.llm.calls._runner import get_prompt, run_with_retries  # noqa: E402
from src.llm.calls.classify.schema import (  # noqa: E402
    ActionOutput,
    ClassifyInput,
    validate_action_output_json,
)
from src.llm.calls.classify.grounding import (  # noqa: E402
    ActionGroundingError,
    validate_grounded_output,
)
from scripts.classify_stress import CATEGORIES, CountingClient  # noqa: E402

_PROMPT = get_prompt("classify", "ko")

_RATE_LIMIT_SLEEP_S = 6.0  # ~10 calls/min


# Pull STRESS + ADVERSARIAL only. DISTINCTION was 8/8 tied last run; skip to save tokens.
CASES_BY_CATEGORY = [
    (title, cases)
    for title, cases in CATEGORIES
    if title.startswith("STRESS") or title.startswith("ADVERSARIAL")
]


async def classify_with_temp(client, input_, *, temperature, retries=5):
    def parse(answer):
        in_combat = bool(input_.surroundings.get("in_combat", False))
        out = validate_action_output_json(answer, in_combat=in_combat)
        return validate_grounded_output(out, input_.surroundings)

    return await run_with_retries(
        client,
        system_prompt=_PROMPT,
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, json.JSONDecodeError, ActionGroundingError),
        retries=retries,
        agent="classify",
        temperature=temperature,
    )


async def run_one(client, sc, *, temperature):
    client.calls = 0
    client.last_answers = []
    t0 = time.time()
    try:
        result = await classify_with_temp(
            client,
            ClassifyInput(
                player_input=sc["player_input"], surroundings=sc["surroundings"]
            ),
            temperature=temperature,
        )
        return {
            "name": sc["name"],
            "attempts": client.calls,
            "elapsed": time.time() - t0,
            "action": _action_label(result),
            "error": None,
        }
    except Exception as e:
        return {
            "name": sc["name"],
            "attempts": client.calls,
            "elapsed": time.time() - t0,
            "action": None,
            "error": f"{type(e).__name__}: {str(e)[:160]}",
        }


def _action_label(output: ActionOutput) -> str:
    if output.refuse is not None:
        return "refuse"
    actions = output.actions or []
    if not actions:
        return "none"
    if len(actions) == 1:
        return actions[0].verb
    return "+".join(action.verb for action in actions)


def summarize(label, results):
    ok = [r for r in results if r["error"] is None]
    failed = [r for r in results if r["error"]]
    dist = {}
    for r in results:
        dist[r["attempts"]] = dist.get(r["attempts"], 0) + 1
    avg = sum(r["elapsed"] for r in results) / len(results) if results else 0
    print(
        f"\n[{label}] total={len(results)} ok={len(ok)} fail={len(failed)} attempts={dict(sorted(dist.items()))} avg={avg:.2f}s"
    )
    if failed:
        print("  failures:")
        for r in failed:
            print(f"    - {r['name']}: {r['error'][:120]}")


async def run_all_at_temp(client, temperature):
    print(f"\n{'=' * 60}\nrunning at temperature={temperature}\n{'=' * 60}", flush=True)
    all_results = []
    per_cat = []
    for title, cases in CASES_BY_CATEGORY:
        print(f"\n--- {title} ---", flush=True)
        cat_results = []
        for sc in cases:
            r = await run_one(client, sc, temperature=temperature)
            mark = "✓" if r["error"] is None else "✗"
            extra = (
                f" → {r['error'][:80]}"
                if r["error"]
                else f" → {r['action']} (attempts={r['attempts']})"
            )
            print(f"  [{mark}] {r['name']}{extra}", flush=True)
            cat_results.append(r)
            all_results.append(r)
            await asyncio.sleep(_RATE_LIMIT_SLEEP_S)
        per_cat.append((title, cat_results))
    print(f"\n--- summary @ temp={temperature} ---")
    for title, cat_results in per_cat:
        summarize(title.split(" — ")[0], cat_results)
    summarize(f"TOTAL @ temp={temperature}", all_results)
    return all_results


async def main():
    client = CountingClient.from_env()
    n_cases = sum(len(c) for _, c in CASES_BY_CATEGORY)
    expected_min_calls = n_cases * 2
    expected_minutes = (expected_min_calls * _RATE_LIMIT_SLEEP_S) / 60
    print(
        f"cases: {n_cases} × 2 temps = {expected_min_calls} calls (min)\n"
        f"rate limit: {_RATE_LIMIT_SLEEP_S}s between calls → ~{expected_minutes:.1f} min minimum"
    )

    res_low = await run_all_at_temp(client, 0.2)
    res_high = await run_all_at_temp(client, 1.0)

    # Side-by-side comparison
    print(f"\n{'=' * 60}\nCOMPARISON\n{'=' * 60}")
    by_name = {r["name"]: r for r in res_low}
    print(f"{'case':<55} {'temp=0.2':<25} {'temp=1.0':<25}")
    for r_high in res_high:
        r_low = by_name.get(r_high["name"])
        low_str = f"{r_low['action'] or 'ERR'} ({r_low['attempts']}t)" if r_low else "?"
        high_str = f"{r_high['action'] or 'ERR'} ({r_high['attempts']}t)"
        same = "" if (r_low and r_low["action"] == r_high["action"]) else "  ← differ"
        print(f"{r_high['name'][:53]:<55} {low_str:<25} {high_str:<25}{same}")


if __name__ == "__main__":
    asyncio.run(main())
