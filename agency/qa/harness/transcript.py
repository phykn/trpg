import json
from pathlib import Path


def write_sse_jsonl(path: Path, turn_no: int, kind: str, events: list[dict]) -> None:
    """Append per-turn API events to sse.jsonl."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(
                json.dumps({"turn": turn_no, "kind": kind, **ev}, ensure_ascii=False)
                + "\n"
            )


def append_transcript_block(
    path: Path,
    *,
    turn_no: int,
    kind: str,
    player_input: str | None = None,
    gm_body: str = "",
    pending: dict | None = None,
    roll_log: dict | None = None,
    error: Exception | dict | None = None,
) -> None:
    """Append one block to transcript.md. `error` is either an Exception or a {code, message} dict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    header = f"## Turn {turn_no}"
    if kind != "turn":
        header += f" ({kind})"
    parts.append(header)

    if player_input is not None:
        parts.append(f"**플레이어**: {player_input}")
    if pending:
        if "stat" in pending:
            parts.append(
                f"**굴림 대기**: {pending['stat']} · {pending['tier']['label']} "
                f"(DC {pending['dc']}, mod {pending['mod']:+d}, "
                f"{pending['required_roll']}+ 필요)"
            )
        else:
            parts.append(
                f"**확인 대기**: {pending.get('title') or '-'} — "
                f"{pending.get('body') or ''}"
            )
    if roll_log:
        parts.append(
            f"**판정 결과**: {roll_log['check']} → "
            f"주사위 {roll_log['roll']} (margin {roll_log['margin']:+d}) "
            f"= **{roll_log['result']}**"
        )
    if gm_body:
        parts.append(f"**GM**:\n\n{gm_body.strip()}")
    if error is not None:
        if isinstance(error, Exception):
            code, message = type(error).__name__, str(error)
        else:
            code, message = error.get("code"), error.get("message")
        parts.append(f"**ERROR**: `{code}` — {message}")

    with path.open("a", encoding="utf-8") as f:
        f.write("\n\n".join(parts) + "\n\n---\n\n")


def write_transcript_header(
    path: Path,
    *,
    agent_name: str,
    run_id: str,
    profile: str,
    game_id: str,
    max_turns: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f"# QA Transcript — {agent_name}\n\n"
            f"- run_id: `{run_id}`\n"
            f"- profile: `{profile}`\n"
            f"- game_id: `{game_id}`\n"
            f"- max_turns: {max_turns}\n\n"
            "---\n\n"
        ),
        encoding="utf-8",
    )
