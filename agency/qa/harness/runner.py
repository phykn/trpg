"""One agent's QA session — drives the FastAPI app in-process via ASGI.

Scenarios and graph saves are local-only. QA never writes production Supabase
tables and does not read release scenario storage.
"""

import json
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from src.db.graph.local_fs import LocalFsGraphRepo
from src.db.scenario.local_fs import LocalFsScenarioRepo
from src.game.runtime.load import load_runtime_state
from src.llm import LLMClient, set_llm_session
from src.wire.graph.to_front import graph_to_front_state

from run_api import build_app

from .agent import PlayerAgent
from .state_view import format_state_summary, last_gm_text
from .transcript import (
    append_transcript_block,
    write_sse_jsonl,
    write_transcript_header,
)

ROOT = Path(__file__).resolve().parents[3]


def _find(events: list[dict], event_type: str) -> dict | None:
    for ev in events:
        if ev["type"] == event_type:
            return ev["data"]
    return None


def _pending_resolution_request(
    game_id: str, front: dict
) -> tuple[str, str, dict, dict] | None:
    pending_roll = front.get("pendingRoll")
    if pending_roll:
        return (
            "roll",
            f"/session/{game_id}/graph/roll",
            {"roll_id": pending_roll["id"]},
            pending_roll,
        )

    pending_confirmation = front.get("pendingConfirmation")
    if pending_confirmation:
        return (
            "confirm",
            f"/session/{game_id}/graph/confirm",
            {
                "confirmation_id": pending_confirmation["id"],
                "decision": "confirm",
            },
            pending_confirmation,
        )

    return None


def _turn_body(result: dict, front: dict) -> str:
    if result.get("message"):
        return result["message"]
    if _pending_resolution_request("", front) is not None:
        return ""
    return last_gm_text(front.get("log") or [])


def _server_relative_env_path(name: str) -> Path:
    path = Path(os.environ[name])
    if path.is_absolute():
        return path
    return (ROOT / "server" / path).resolve()


def _build_scenario_repo() -> LocalFsScenarioRepo:
    return LocalFsScenarioRepo(str(_server_relative_env_path("SCENARIO_DIR")))


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

    graph_repo = LocalFsGraphRepo(str(saves_dir))
    scenario_repo = _build_scenario_repo()

    app = build_app(
        llm=llm,
        basic_auth_user="qa",
        basic_auth_pass="qa",
        scenario_repo=scenario_repo,
        graph_repo=graph_repo,
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
            "/session/graph/init",
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
        init_state = init_resp.json()["state"]

        write_transcript_header(
            transcript_path,
            agent_name=agent.name,
            run_id=run_id,
            profile=profile,
            game_id=game_id,
            max_turns=max_turns,
        )

        write_sse_jsonl(
            sse_path,
            0,
            "init",
            [{"type": "graph_state", "data": init_state}],
        )
        last_gm = last_gm_text(init_state.get("log") or [])
        append_transcript_block(
            transcript_path,
            turn_no=0,
            kind="init",
            gm_body=last_gm,
        )

        for turn_no in range(1, max_turns + 1):
            try:
                state_resp = await client.get(f"/session/{game_id}/graph/state")
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
                response = await client.post(
                    f"/session/{game_id}/graph/input",
                    json={"player_input": player_input},
                )
                response.raise_for_status()
                result = response.json()
                front = result["state"]
                body = _turn_body(result, front)
                events = [
                    {
                        "type": "graph_response",
                        "data": {
                            "status": result.get("status"),
                            "message": result.get("message"),
                            "state": front,
                        },
                    }
                ]
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
            pending_request = _pending_resolution_request(game_id, front)
            pending = pending_request[3] if pending_request is not None else None
            err = _find(events, "error")
            if err:
                error_count += 1

            append_transcript_block(
                transcript_path,
                turn_no=turn_no,
                kind="turn",
                player_input=player_input,
                gm_body=body,
                pending=pending,
                error=err,
            )
            agent.record(player_input, body)
            if body:
                last_gm = body

            pending_failed = False
            while True:
                pending_request = _pending_resolution_request(game_id, front)
                if pending_request is None:
                    break

                pending_kind, pending_path, pending_payload, _pending_payload = (
                    pending_request
                )
                try:
                    pending_response = await client.post(
                        pending_path, json=pending_payload
                    )
                    pending_response.raise_for_status()
                    pending_result = pending_response.json()
                    front = pending_result["state"]
                    pending_body = pending_result.get("message") or last_gm_text(
                        front.get("log") or []
                    )
                    pending_events = [
                        {
                            "type": f"graph_{pending_kind}",
                            "data": {
                                "status": pending_result.get("status"),
                                "message": pending_result.get("message"),
                                "state": front,
                            },
                        }
                    ]
                except Exception as e:  # noqa: BLE001
                    error_count += 1
                    append_transcript_block(
                        transcript_path,
                        turn_no=turn_no,
                        kind=f"{pending_kind}-error",
                        error=e,
                    )
                    pending_failed = True
                    break

                write_sse_jsonl(sse_path, turn_no, pending_kind, pending_events)
                pending_err = _find(pending_events, "error")
                if pending_err:
                    error_count += 1
                append_transcript_block(
                    transcript_path,
                    turn_no=turn_no,
                    kind=pending_kind,
                    gm_body=pending_body,
                    error=pending_err,
                )
                agent.record(
                    "(판정)" if pending_kind == "roll" else "(확인)",
                    pending_body,
                )
                if pending_body:
                    last_gm = pending_body

            completed_turns = turn_no

            if err or pending_failed:
                # stop on error — continuing would be meaningless
                break

        try:
            runtime = await load_runtime_state(graph_repo, game_id)
            state = graph_to_front_state(runtime)
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
