"""Quest auto-trigger / reward application / chapter progression. Event-driven: each (event_type, target_id) scans active quests' triggers and cascades through prerequisites and chapter progress."""

from __future__ import annotations

from ..domain.entities import Quest
from ..domain.state import GameState

DirtySet = set[tuple[str, str]] | None


def _ensure_runtime_fields(quest: Quest) -> None:
    """Align lengths of triggers_met / fail_triggers_met with their trigger lists.
    Preserves the existing prefix when triggers grew — a seed change that adds
    a new trigger mid-game must not wipe progress already accumulated against
    the old triggers."""
    n = len(quest.triggers)
    quest.triggers_met = quest.triggers_met[:n] + [False] * max(
        0, n - len(quest.triggers_met)
    )
    m = len(quest.fail_triggers)
    quest.fail_triggers_met = quest.fail_triggers_met[:m] + [False] * max(
        0, m - len(quest.fail_triggers_met)
    )


def _apply_rewards(state: GameState, quest: Quest, dirty: DirtySet) -> None:
    actor = state.characters.get(state.player_id)
    if actor is None:
        return
    actor.gold += quest.rewards.gold
    actor.xp_pool += quest.rewards.exp
    for item_id in quest.rewards.items:
        actor.inventory_ids.append(item_id)
    if dirty is not None:
        dirty.add(("characters", actor.id))


def _maybe_unlock_dependents(state: GameState, dirty: DirtySet) -> None:
    """If all prerequisite_ids of another quest are completed, flip locked → active."""
    for q in state.quests.values():
        if q.status != "locked":
            continue
        prereq_ids = q.prerequisite_ids
        if not prereq_ids:
            continue
        if all(
            pid in state.quests and state.quests[pid].status == "completed"
            for pid in prereq_ids
        ):
            q.status = "active"
            _ensure_runtime_fields(q)
            if dirty is not None:
                dirty.add(("quests", q.id))


def update_chapter_progress(state: GameState, dirty: DirtySet = None) -> None:
    """Recompute progress for every chapter. Only required=true quests count."""
    for ch in state.chapters.values():
        required_quests = [
            state.quests[qid]
            for qid in ch.quest_ids
            if qid in state.quests and state.quests[qid].required
        ]
        total = len(required_quests)
        done = sum(1 for q in required_quests if q.status == "completed")
        if ch.progress.done != done or ch.progress.total != total:
            ch.progress.done = done
            ch.progress.total = total
            if dirty is not None:
                dirty.add(("chapters", ch.id))


def _maybe_advance_chapters(state: GameState, dirty: DirtySet) -> None:
    """If all required quests of a chapter are completed, flip active → completed."""
    for ch in state.chapters.values():
        if ch.status != "active":
            continue
        if ch.progress.total > 0 and ch.progress.done >= ch.progress.total:
            ch.status = "completed"
            if dirty is not None:
                dirty.add(("chapters", ch.id))


def _maybe_unlock_chapters(state: GameState, dirty: DirtySet) -> None:
    """If all prerequisite_ids of a locked chapter are completed, flip locked → active."""
    for ch in state.chapters.values():
        if ch.status != "locked":
            continue
        if not ch.prerequisite_ids:
            continue
        if all(
            pid in state.chapters and state.chapters[pid].status == "completed"
            for pid in ch.prerequisite_ids
        ):
            ch.status = "active"
            if dirty is not None:
                dirty.add(("chapters", ch.id))


def _refresh_active_quest_id(state: GameState) -> None:
    """If active_quest_id no longer points to an active quest, switch to any
    other active one (insertion order). The seed pins an opening quest; once
    it completes/fails, the panel should follow whatever's still in play."""
    current = state.active_quest_id
    if current and current in state.quests and state.quests[current].status == "active":
        return
    state.active_quest_id = next(
        (qid for qid, q in state.quests.items() if q.status == "active"),
        None,
    )


def check_quests(
    state: GameState,
    event_type: str,
    target_id: str | None,
    dirty: DirtySet = None,
) -> list[str]:
    """Evaluate quests against an event; returns ids whose status changed. Triggers are single-fire."""
    changed: list[str] = []
    for q in state.quests.values():
        if q.status != "active":
            continue
        _ensure_runtime_fields(q)

        any_change = False
        for i, t in enumerate(q.triggers):
            if q.triggers_met[i]:
                continue
            if t.type == event_type and t.target_id == target_id:
                q.triggers_met[i] = True
                any_change = True
        for i, t in enumerate(q.fail_triggers):
            if q.fail_triggers_met[i]:
                continue
            if t.type == event_type and t.target_id == target_id:
                q.fail_triggers_met[i] = True
                any_change = True

        if not any_change:
            continue

        # State transition: fail wins (any single fail_trigger flips the quest to failed).
        if any(q.fail_triggers_met):
            q.status = "failed"
            changed.append(q.id)
        elif q.triggers and all(q.triggers_met):
            q.status = "completed"
            _apply_rewards(state, q, dirty)
            changed.append(q.id)
        if dirty is not None:
            dirty.add(("quests", q.id))

    if changed:
        _maybe_unlock_dependents(state, dirty)
    update_chapter_progress(state, dirty)
    _maybe_advance_chapters(state, dirty)
    _maybe_unlock_chapters(state, dirty)
    _refresh_active_quest_id(state)
    return changed
