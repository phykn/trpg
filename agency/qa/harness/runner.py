"""One agent's QA session — drives the FastAPI app in-process via ASGI
and records each SSE stream into transcript / sse.jsonl.

Persistence shape: scenarios are read from Supabase Storage (same source the
production server uses), but game saves go to a local `LocalFsSaveRepo` rooted
at `<run_dir>/saves/`, so QA never writes to the production Supabase save
tables. The per-agent run directory is wiped at session start by the caller.
"""

import json
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.llm import LLMClient, set_llm_session
from src.persistence.local_fs import LocalFsSaveRepo
from src.persistence.supabase import SupabaseStorageScenarioRepo

from run_api import build_app

from .agent import PlayerAgent
from .state_view import format_state_summary, last_gm_text
from .transcript import (
    append_transcript_block,
    write_sse_jsonl,
    write_transcript_header,
)


async def _drain_sse(response) -> tuple[str, list[dict]]:
    """Drain one SSE response. Returns (gm_body, all_events).

    Body comes from narrative_delta when narrate ran; if narrate was skipped
    (combat/rest/use), fall back to the gm log_entry text so the transcript
    isn't blank.
    """
    body = ""
    gm_logs: list[str] = []
    events: list[dict] = []
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        events.append(ev)
        if ev["type"] == "narrative_delta":
            body += ev["data"]["text"]
        elif ev["type"] == "log_entry" and ev["data"].get("kind") in ("gm", "act"):
            # `act` covers engine-side notices ("공격할 수 있는 대상이 없다",
            # 검증 실패 GM 메시지 등) the player would otherwise miss.
            text = ev["data"].get("text") or ""
            if text:
                gm_logs.append(text)
    if not body and gm_logs:
        body = "\n".join(gm_logs)
    return body, events


def _find(events: list[dict], event_type: str) -> dict | None:
    for ev in events:
        if ev["type"] == event_type:
            return ev["data"]
    return None


async def run_qa_session(
    *,
    agent: PlayerAgent,
    profile: str,
    max_turns: int,
    run_dir: Path,
    llm: LLMClient,
    run_id: str,
) -> dict:
    """Run one agent's QA session.

    Returns a summary dict: game_id, turn_count, error_count, and the transcript / sse / final-state paths.
    """
    set_llm_session(f"qa-{run_id}-{agent.name}")
    saves_dir = run_dir / "saves"
    saves_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = run_dir / "transcript.md"
    sse_path = run_dir / "sse.jsonl"
    final_state_path = run_dir / "final_state.json"

    save_repo = LocalFsSaveRepo(str(saves_dir))
    scenario_repo = SupabaseStorageScenarioRepo(
        url=os.environ["SUPABASE_URL"],
        service_key=os.environ["SUPABASE_SERVICE_KEY"],
        bucket=os.environ["SUPABASE_SCENARIO_BUCKET"],
    )

    app = build_app(
        llm=llm,
        basic_auth_user="qa",
        basic_auth_pass="qa",
        save_repo=save_repo,
        scenario_repo=scenario_repo,
        cors_origins=[],  # in-process via ASGITransport — no real cross-origin clients
    )

    error_count = 0
    completed_turns = 0
    game_id = ""
    last_gm = ""

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://qa",
        auth=("qa", "qa"),
        timeout=120.0,
    ) as client:
        init_resp = await client.post(
            "/session/init",
            json={
                "profile": profile,
                "player": {
                    "name": f"QA-{agent.name}",
                    "race_id": "human",
                    "gender": "male",
                },
            },
        )
        init_resp.raise_for_status()
        game_id = init_resp.json()["game_id"]

        write_transcript_header(
            transcript_path,
            agent_name=agent.name,
            run_id=run_id,
            profile=profile,
            game_id=game_id,
            max_turns=max_turns,
        )

        # intro is optional — swallow failures and continue
        try:
            async with client.stream("POST", f"/session/{game_id}/intro") as r:
                body, events = await _drain_sse(r)
            write_sse_jsonl(sse_path, 0, "intro", events)
            err = _find(events, "error")
            if err:
                error_count += 1
            append_transcript_block(
                transcript_path,
                turn_no=0,
                kind="intro",
                gm_body=body,
                error=err,
            )
            if body:
                last_gm = body
        except Exception as e:  # noqa: BLE001
            error_count += 1
            append_transcript_block(
                transcript_path,
                turn_no=0,
                kind="intro",
                error=e,
            )

        for turn_no in range(1, max_turns + 1):
            try:
                state_resp = await client.get(f"/session/{game_id}/state")
                state_resp.raise_for_status()
                front = state_resp.json()["state"]
            except Exception as e:  # noqa: BLE001
                error_count += 1
                append_transcript_block(
                    transcript_path,
                    turn_no=turn_no,
                    kind="state-error",
                    error=e,
                )
                break

            state_summary = format_state_summary(front)
            if not last_gm:
                last_gm = last_gm_text(front.get("log") or [])

            try:
                player_input = await agent.next_input(
                    state_summary, last_gm, turn_no=turn_no
                )
            except Exception as e:  # noqa: BLE001
                error_count += 1
                append_transcript_block(
                    transcript_path,
                    turn_no=turn_no,
                    kind="agent-error",
                    error=e,
                )
                break

            try:
                async with client.stream(
                    "POST",
                    f"/session/{game_id}/turn",
                    json={"player_input": player_input},
                ) as r:
                    body, events = await _drain_sse(r)
            except Exception as e:  # noqa: BLE001
                error_count += 1
                append_transcript_block(
                    transcript_path,
                    turn_no=turn_no,
                    kind="turn-error",
                    player_input=player_input,
                    error=e,
                )
                break

            write_sse_jsonl(sse_path, turn_no, "turn", events)
            judge = _find(events, "judge")
            pending = _find(events, "pending_check")
            err = _find(events, "error")
            if err:
                error_count += 1

            append_transcript_block(
                transcript_path,
                turn_no=turn_no,
                kind="turn",
                player_input=player_input,
                gm_body=body,
                judge=judge,
                pending=pending,
                error=err,
            )
            agent.record(player_input, body)
            if body:
                last_gm = body

            # pending_check → auto /roll
            if pending:
                try:
                    async with client.stream(
                        "POST", f"/session/{game_id}/roll", json={}
                    ) as r:
                        roll_body, roll_events = await _drain_sse(r)
                except Exception as e:  # noqa: BLE001
                    error_count += 1
                    append_transcript_block(
                        transcript_path,
                        turn_no=turn_no,
                        kind="roll-error",
                        error=e,
                    )
                    break

                write_sse_jsonl(sse_path, turn_no, "roll", roll_events)
                roll_err = _find(roll_events, "error")
                if roll_err:
                    error_count += 1
                roll_log_ev = next(
                    (
                        ev["data"]
                        for ev in roll_events
                        if ev["type"] == "log_entry"
                        and ev["data"].get("kind") == "roll"
                    ),
                    None,
                )
                append_transcript_block(
                    transcript_path,
                    turn_no=turn_no,
                    kind="roll",
                    gm_body=roll_body,
                    roll_log=roll_log_ev,
                    error=roll_err,
                )
                agent.record("(굴림)", roll_body)
                if roll_body:
                    last_gm = roll_body

            completed_turns = turn_no

            if err:
                # stop on error — continuing would be meaningless
                break

        try:
            state = await save_repo.load_game(game_id)
            final_state_path.write_text(
                state.model_dump_json(indent=2), encoding="utf-8"
            )
        except Exception as e:  # noqa: BLE001
            final_state_path.write_text(
                json.dumps(
                    {"error": f"{type(e).__name__}: {e}"},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    return {
        "agent": agent.name,
        "game_id": game_id,
        "turn_count": completed_turns,
        "error_count": error_count,
        "transcript_path": str(transcript_path),
        "final_state_path": str(final_state_path),
        "sse_path": str(sse_path),
    }
