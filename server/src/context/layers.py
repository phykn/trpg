"""Narrate prompt input — world / session / history layers."""
from pathlib import Path

from ..domain.clock import day_phase
from ..domain.state import GameState


_QUOTE_OPEN_TO_CLOSE = {"「": "」", "『": "』"}
_REDACT_PRE_WINDOW = 30


def redact_dead_quotes(text: str, dead_names: list[str]) -> str:
    """Strip Korean direct-quote blocks attributed to dead NPCs.

    For each `「` / `『` opener in `text`, if any of `dead_names` appears as
    a substring within the 30 chars preceding the opener, the entire quote
    block (opener through matching closer) is replaced with `…`. Names are
    matched as substrings so trailing particles (가/이/은/는/께서) don't
    affect detection.

    Two callers — same single root cause:
    - `build_history_layer` → strips them from `recent_dialogue` so the
      narrate LLM doesn't see resurrected speech as an in-context pattern
      to mimic. The corpse "사망" header alone hasn't been enough: when the
      same NPC's quotes are inline in `=== 최근 대화 ===` the LLM follows
      the pattern.
    - `consume_narrate` → strips them from the post-LLM body before
      persisting to log_entry / dialogue / turn_log so a one-off slip
      doesn't compound across turns.
    """
    if not dead_names or not text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        close = _QUOTE_OPEN_TO_CLOSE.get(ch)
        if close is None:
            out.append(ch)
            i += 1
            continue
        close_idx = text.find(close, i + 1)
        if close_idx == -1:
            # Unmatched opener — leave the rest as-is rather than swallow it.
            out.append(text[i:])
            break
        window = text[max(0, i - _REDACT_PRE_WINDOW):i]
        if any(name and name in window for name in dead_names):
            out.append("…")
        else:
            out.append(text[i:close_idx + 1])
        i = close_idx + 1
    return "".join(out)


def build_world_layer(
    profile_dir: str, profile: str, *, missing_ok: bool = False
) -> str:
    """Read <profile>/world.md. Strict by default — set missing_ok=True for
    callers (combat_auto narrate input, encounter summon) that should fall
    back to an empty string."""
    p = Path(profile_dir) / profile / "world.md"
    if missing_ok and not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def build_session_layer(state: GameState) -> dict:
    chapter_data = None
    active_chapter = next(
        (c for c in state.chapters.values() if c.status == "active"),
        None,
    )
    if active_chapter:
        active_quests = []
        for qid in active_chapter.quest_ids:
            q = state.quests.get(qid)
            if q is None or q.status != "active":
                continue
            giver = state.characters.get(q.giver_id)
            giver_name = giver.name if giver else q.giver_id
            pending_goals = [
                t.name
                for i, t in enumerate(q.triggers)
                if i >= len(q.triggers_met) or not q.triggers_met[i]
            ]
            active_quests.append(
                {
                    "title": q.title,
                    "summary": q.summary,
                    "giver": giver_name,
                    "goals": pending_goals,
                    "conditions": q.conditions,
                }
            )
        chapter_data = {
            "title": active_chapter.title,
            "summary": active_chapter.summary,
            "quests": active_quests,
        }
    return {"chapter": chapter_data, "day_phase": day_phase(state.turn_count)}


def build_history_layer(
    state: GameState, corpses: list[dict] | None = None
) -> str:
    dialogue_turns = {d.turn for d in state.recent_dialogue}
    summary_entries = [e for e in state.turn_log if e.turn not in dialogue_turns]

    blocks: list[str] = []

    dead_names = [
        c["name"] for c in (corpses or [])
        if isinstance(c, dict) and c.get("name")
    ]

    if corpses:
        lines = ["=== 사망 — 다시 등장시키거나 발화시키지 말 것 ==="]
        for c in corpses:
            lines.append(f"- {c['name']} (생전 발화가 아래 대화에 남아 있을 수 있으나 더 이상 말하지 않습니다)")
        blocks.append("\n".join(lines))

    if summary_entries:
        lines = ["=== 이전 요약 ==="]
        for e in summary_entries:
            lines.append(f"[턴 {e.turn}] — {e.summary}")
        blocks.append("\n".join(lines))

    if state.recent_dialogue:
        items = [
            f"[턴 {d.turn}]\n  플레이어: {d.player}\n  서술자: {redact_dead_quotes(d.narrator, dead_names)}"
            for d in state.recent_dialogue
        ]
        blocks.append("=== 최근 대화 ===\n" + "\n".join(items))

    return "\n\n".join(blocks)
