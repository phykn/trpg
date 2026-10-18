"""Play a story in the terminal with both real models and record every turn.

From server/:  ../.venv/bin/python scripts/play.py --story harbor [--run name]
Type a sentence, a button number, 'y'/'n' on a confirm card, or 'q' to quit.
Writes qa_test/agency/<run>/transcript.jsonl.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from run_api import load_stories
from src.config import load_server_env
from src.models.kev import KevClient, ModelUnavailable
from src.models.qwen import QwenClient
from src.service import GameService
from src.store import SaveStore


async def narrate(game: GameService, game_id: str, turn: int) -> dict:
    started, first, text = time.perf_counter(), None, ""
    async for event in game.narration(game_id, turn):
        if event["type"] == "delta":
            first = first or time.perf_counter()
            print(event["text"], end="", flush=True)
        elif event["type"] == "reset":
            print("\n[검사 실패, 다시 씁니다]")
        elif event["type"] == "done":
            text = event["text"]
        else:
            print("\n[서술 실패]")
    print()
    return {"narration": text, "first_ms": round(((first or time.perf_counter()) - started) * 1000),
            "total_ms": round((time.perf_counter() - started) * 1000)}


def show(view) -> None:
    print(f"\n== {view.place.name} · {view.danger.name} {view.danger.value}/{view.danger.boxes}")
    for o in view.obstacles:
        print(f"   {o.name} {o.value}/{o.boxes}")
    for t in view.tags:
        print(f"   [{t.kind}] {t.name}")
    for line in view.journal[-1].lines if view.journal else []:
        print(f"   · {line}")
    if view.pending and view.pending.card:
        card = view.pending.card
        print(f"   위험한 행동: {' / '.join(card.steps)}  성공 {card.odds[0]:.0%} 대가 {card.odds[1]:.0%} 실패 {card.odds[2]:.0%}")
    for i, b in enumerate(view.pending.options if view.pending else view.buttons, 1):
        print(f"   {i}. {b.label}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default="harbor")
    parser.add_argument("--run", default=f"{date.today()}-play")
    args = parser.parse_args()
    load_server_env(SERVER)
    run_dir = SERVER.parent / "qa_test/agency" / args.run
    game = GameService(
        load_stories(SERVER.parent / "scenarios"), SaveStore(run_dir / "saves"),
        KevClient(os.environ["KEV_BASE_URL"]), QwenClient(os.environ["QWEN_BASE_URL"]),
    )
    await game.check_models()
    view = await game.start(args.story)
    log = (run_dir / "transcript.jsonl").open("a", encoding="utf-8")
    print(view.intro)
    timing = await narrate(game, view.game_id, 0)
    while view.ending is None:
        show(view)
        line = input("> ").strip()
        if line == "q":
            break
        options = view.pending.options if view.pending and view.pending.options else view.buttons
        command: dict = {"text": line}
        if line.isdigit() and 0 < int(line) <= len(options):
            command = {"action_id": options[int(line) - 1].id}
        elif view.pending and view.pending.card and line in ("y", "n"):
            command = {"confirm": view.pending.card.id, "accept": line == "y"}
        started = time.perf_counter()
        try:
            out = await game.act(view.game_id, revision=view.revision, request_id=uuid4().hex, **command)
        except (ModelUnavailable, ValueError) as exc:
            print(f"[{type(exc).__name__}] {exc}")
            continue
        act_ms = round((time.perf_counter() - started) * 1000)
        view = out.view
        if out.kind in ("rejected", "clarify"):
            print(out.reason or "무엇을 말씀하시는지 골라 주십시오:")
            for i, b in enumerate(out.options, 1):
                print(f"   {i}. {b.label}")
            view.buttons = out.options or view.buttons
        elif out.kind == "turn":
            timing = await narrate(game, view.game_id, out.turn)
        log.write(json.dumps({"turn": out.turn, "input": line, "kind": out.kind, "act_ms": act_ms,
                              "lines": view.journal[-1].lines if out.kind == "turn" else [], **timing},
                             ensure_ascii=False) + "\n")
        log.flush()
    if view.ending:
        print(f"\n== 결말: {view.ending.name}\n{view.ending.text}")


if __name__ == "__main__":
    asyncio.run(main())
