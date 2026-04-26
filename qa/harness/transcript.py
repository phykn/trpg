import json
from pathlib import Path


def format_state_summary(front_state: dict) -> str:
    """front_state (mapping/to_front 출력) 를 player LLM 용 요약 텍스트로."""
    lines: list[str] = []

    place = front_state.get("place")
    if place:
        lines.append(
            f"장소: {place['name']} ({place['date']} {place['period']} {place['hour']}시)"
        )
        if place.get("surroundings"):
            lines.append(f"인접: {', '.join(place['surroundings'])}")
        if place.get("features"):
            lines.append(f"환경: {', '.join(place['features'])}")
        if place.get("weather"):
            lines.append(f"날씨: {', '.join(place['weather'])}")

    hero = front_state.get("hero")
    if hero:
        lines.append(
            f"나: {hero['name']} ({hero['race']}{' ' + hero['job'] if hero['job'] else ''}) "
            f"HP {hero['hp']}/{hero['hpMax']}"
        )
        inv = hero.get("inventory") or []
        if inv:
            lines.append("인벤토리: " + ", ".join(f"{i['name']}×{i['qty']}" for i in inv))

    subject = front_state.get("subject")
    if subject:
        lines.append(
            f"눈앞 NPC: {subject['name']} ({subject.get('role') or '-'}) — 친밀도 {subject['trust']}"
        )
        known = subject.get("known") or []
        if known:
            lines.append("  아는 정보: " + " / ".join(known))

    quest = front_state.get("quest")
    if quest:
        lines.append(f"진행 퀘스트: {quest['title']} — {quest.get('summary') or ''}")

    return "\n".join(lines) or "(상황 정보 없음)"


def last_gm_text(log_entries: list[dict]) -> str:
    for e in reversed(log_entries):
        if e.get("kind") == "gm":
            return e.get("text", "")
    return ""


def write_sse_jsonl(path: Path, turn_no: int, kind: str, events: list[dict]) -> None:
    """sse.jsonl 에 turn 별 이벤트들을 한 줄씩 append. kind = 'turn' | 'roll' | 'intro'."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(
                json.dumps(
                    {"turn": turn_no, "kind": kind, **ev}, ensure_ascii=False
                )
                + "\n"
            )


def append_transcript_block(
    path: Path,
    *,
    turn_no: int,
    kind: str,
    player_input: str | None,
    gm_body: str,
    judge: dict | None,
    pending: dict | None,
    roll_log: dict | None,
    error: dict | None,
) -> None:
    """transcript.md 한 블록 append."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    header = f"## Turn {turn_no}"
    if kind != "turn":
        header += f" ({kind})"
    parts.append(header)

    if player_input is not None:
        parts.append(f"**플레이어**: {player_input}")
    if judge:
        parts.append(f"**판단**: `{judge.get('action')}`")
    if pending:
        parts.append(
            f"**굴림 대기**: {pending['stat']} · {pending['tier']['label']} "
            f"(DC {pending['dc']}, mod {pending['mod']:+d}, {pending['required_roll']}+ 필요)"
        )
    if roll_log:
        parts.append(
            f"**판정 결과**: {roll_log['check']} → "
            f"주사위 {roll_log['roll']} (mod {roll_log['mod']:+d}, DC {roll_log['dc']}) "
            f"= **{roll_log['result']}**"
        )
    if gm_body:
        parts.append(f"**GM**:\n\n{gm_body.strip()}")
    if error:
        parts.append(f"**ERROR**: `{error.get('code')}` — {error.get('message')}")

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
