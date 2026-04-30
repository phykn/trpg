"""Narrate prompt input — world / session / history layers."""
from pathlib import Path

from ..domain.clock import day_phase
from ..domain.state import GameState


def build_world_layer(
    profile_dir: str, profile: str, *, missing_ok: bool = False
) -> str:
    """Read <profile>/world.md. Strict by default — set missing_ok=True for
    callers (combat_oneshot narrate input, encounter summon) that should
    fall back to an empty string."""
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
            f"[턴 {d.turn}]\n  플레이어: {d.player}\n  서술자: {d.narrator}"
            for d in state.recent_dialogue
        ]
        blocks.append("=== 최근 대화 ===\n" + "\n".join(items))

    return "\n\n".join(blocks)
