"""Narrate prompt input — world / session / history layers."""
from pathlib import Path

from ..domain.state import GameState


def build_world_layer(profile_dir: str, profile: str) -> str:
    return (Path(profile_dir) / profile / "world.md").read_text(encoding="utf-8")


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
    return {"chapter": chapter_data, "world_time": state.world_time}


def build_history_layer(state: GameState) -> str:
    dialogue_turns = {d.turn for d in state.recent_dialogue}
    summary_entries = [e for e in state.turn_log if e.turn not in dialogue_turns]

    blocks: list[str] = []

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
