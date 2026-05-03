"""Quest auto-trigger / reward application / chapter progression. Event-driven: each (event_type, target_id) scans active quests' triggers and cascades through prerequisites and chapter progress."""

from __future__ import annotations

from ..domain.entities import Quest
from ..domain.errors import InventoryInvalid
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import giver_of, kill_targets_of
from .inventory.carry import check_can_carry

DirtySet = set[tuple[str, str]] | None


def apply_judge_result(state: GameState, quest_id: str, result: dict) -> bool:
    """Apply free-path judge outcome. Returns True if state changed."""
    quest = state.quests.get(quest_id)
    if not quest or quest.status != "active":
        return False
    outcome = result.get("outcome")
    if outcome == "satisfied":
        quest.status = "completed"
        quest.success_reason = "free_path_satisfied"
        return True
    if outcome == "partial":
        delta = result.get("progress_delta") or 0
        quest.progress = (quest.progress or 0) + delta
        return True
    # rejected → no-op
    return False


def accept_quest(state: GameState, quest_id: str) -> bool:
    """pending → active. No-op for any other status."""
    quest = state.quests.get(quest_id)
    if not quest or quest.status != "pending":
        return False
    quest.status = "active"
    _ensure_runtime_fields(quest)
    return True


def abandon_quest(state: GameState, quest_id: str) -> bool:
    """active → abandoned. No-op for any other status."""
    quest = state.quests.get(quest_id)
    if not quest or quest.status != "active":
        return False
    quest.status = "abandoned"
    quest.fail_reason = "abandoned"
    return True


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
    # Carry-overflow rewards land at the player's location (loot-on-the-ground), so quest completion can't silently break the carry invariant.
    location = state.locations.get(actor.location_id) if actor.location_id else None
    for item_id in quest.rewards.items:
        try:
            check_can_carry(actor, state.items, item_id)
        except InventoryInvalid:
            if location is not None:
                location.item_ids.append(item_id)
                if dirty is not None:
                    dirty.add(("locations", location.id))
            continue
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
            q.status = "pending" if q.requires_acceptance else "active"
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
    graph = state.graph()
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

    # Death cascade: giver death → fail; kill-target death → complete (objective_killed).
    # Runs as a second pass so it can also catch quests with no explicit triggers.
    # Giver-dead overrides a trigger-completed result (fail wins).
    if event_type == "character_death" and target_id is not None:
        _cascade_death(state, graph, target_id, changed, dirty)

    if changed:
        _maybe_unlock_dependents(state, dirty)
    update_chapter_progress(state, dirty)
    _maybe_advance_chapters(state, dirty)
    _maybe_unlock_chapters(state, dirty)
    _refresh_active_quest_id(state)
    return changed


def _cascade_death(
    state: GameState,
    graph: GameGraph,
    dead_id: str,
    changed: list[str],
    dirty: DirtySet,
) -> None:
    """Cascade entity death onto quest statuses without requiring explicit triggers.

    - Giver died → active quest fails (fail_reason='giver_dead'); overrides a
      same-turn trigger-completion so fail always wins.
    - Kill-target died → if quest is already completed this turn via its trigger,
      annotate success_reason='objective_killed'.
    """
    for q in state.quests.values():
        giver = giver_of(graph, q.id)
        kill_targets = kill_targets_of(graph, q.id)
        is_giver_dead = giver == dead_id
        is_kill_target_dead = dead_id in kill_targets

        # locked / pending / abandoned / failed quests are intentionally excluded.
        if is_giver_dead and q.status in ("active", "completed"):
            if q.status == "completed" and q.id in changed:
                # Undo same-turn completion so fail wins.
                changed.remove(q.id)
            q.status = "failed"
            q.fail_reason = "giver_dead"
            if q.id not in changed:
                changed.append(q.id)
            if dirty is not None:
                dirty.add(("quests", q.id))

        elif is_kill_target_dead and not is_giver_dead:
            if q.status == "completed" and q.id in changed and q.success_reason is None:
                # Trigger path already completed it this turn — annotate reason.
                q.success_reason = "objective_killed"
