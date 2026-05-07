"""Quest auto-trigger / reward application / chapter progression. Event-driven: each (event_type, target_id) scans active quests' triggers and cascades through prerequisites and chapter progress."""

from __future__ import annotations

from ..domain.entities import Quest
from ..domain.errors import InventoryInvalid
from ..domain.state import GameState
from src.locale import render
from ..ontology.graph import GameGraph
from ..ontology.queries import (
    connections_of, giver_of, kill_targets_of, quests_given_by,
)
from .inventory.carry import check_can_carry

# Quest mutations accept a full `flow.dirty.Dirty` (or `None`) — `Dirty.entities`
# tracks which entities to upsert, `Dirty.log` collects card emissions. The
# helpers below extract each piece so apply/inventory/skill can pass either.


def _entities_set(dirty) -> set[tuple[str, str]] | None:
    if dirty is None:
        return None
    if isinstance(dirty, set):
        return dirty
    return dirty.entities


def _as_dirty(dirty):
    """Return the full Dirty if available; None when the caller only had a set."""
    if dirty is None or isinstance(dirty, set):
        return None
    return dirty


def accept_quest(state: GameState, quest_id: str, dirty=None) -> bool:
    """`locked` or `pending` → active. Default-seeded quests start at `locked`
    (no prereq auto-unlock fires for prereq-less quests), so natural acceptance
    via classify intent=accept must flip from there too. With a full Dirty,
    also marks the quest entity dirty and pushes a start card; without it,
    only the in-memory transition happens. Pins active_quest_id. No-op for
    any other status."""
    quest = state.quests.get(quest_id)
    if not quest or quest.status not in ("locked", "pending"):
        return False
    quest.status = "active"
    _ensure_runtime_fields(quest)
    entities = _entities_set(dirty)
    full = _as_dirty(dirty)
    if entities is not None:
        entities.add(("quests", quest.id))
    if full is not None:
        from ..flow.format import format_quest_start_log

        text = format_quest_start_log(quest.title)
        full.deferred_act_cards.append((text, text))
    state.active_quest_id = quest.id
    return True


def accept_npc_locked_quest(
    state: GameState, graph: GameGraph, npc_id: str, dirty=None
) -> str | None:
    """Find the NPC's first locked quest and flip it via accept_quest. Returns
    the flipped quest id, or None if the NPC has no locked quest to give.
    Used by the natural-language accept route (speak intent=accept) so quest
    transitions don't depend on narrate extract emitting set quests.status."""
    for qid in quests_given_by(graph, npc_id):
        q = state.quests.get(qid)
        if q and q.status == "locked":
            if accept_quest(state, qid, dirty):
                return qid
    return None


def abandon_quest(state: GameState, quest_id: str, dirty=None) -> bool:
    """active → failed via _fail_quest. No-op for any other status."""
    quest = state.quests.get(quest_id)
    if not quest or quest.status != "active":
        return False
    _fail_quest(
        state, quest, reason=render("log.quest.abandon_reason", "ko"), dirty=dirty
    )
    return True


def _fail_quest(state: GameState, quest: Quest, reason: str, dirty) -> None:
    """Mark quest failed, clear active pointer if matching, emit fail card.

    Card emit only when `dirty` is the full `flow.dirty.Dirty` (has `.log`);
    callers passing None get the state mutation without the card.
    """
    quest.status = "failed"
    quest.fail_reason = reason
    entities = _entities_set(dirty)
    full = _as_dirty(dirty)
    if entities is not None:
        entities.add(("quests", quest.id))
    if full is not None:
        from ..flow.format import format_quest_fail_log

        text = format_quest_fail_log(title=quest.title, reason=reason)
        full.deferred_act_cards.append(
            (text, render("log.quest.fail_log", "ko", title=quest.title, reason=reason))
        )
    if state.active_quest_id == quest.id:
        state.active_quest_id = None


def cascade_giver_death(state: GameState, victim_id: str, dirty) -> None:
    """When an NPC dies, fail every active/pending quest where they were the giver.

    Routes through `_fail_quest` so the card emit + active_quest_id clear stay
    consistent with the player-initiated abandon path.
    """
    for quest in state.quests.values():
        if quest.status not in ("active", "pending"):
            continue
        if quest.giver_id == victim_id:
            _fail_quest(
                state,
                quest,
                reason=render("log.quest.giver_dead_reason", "ko"),
                dirty=dirty,
            )


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


def _apply_rewards(state: GameState, quest: Quest, dirty) -> None:
    entities = _entities_set(dirty)
    full = _as_dirty(dirty)
    actor = state.characters.get(state.player_id)
    if actor is None:
        return
    actor.gold += quest.rewards.gold
    actor.xp_pool += quest.rewards.exp
    # Carry-overflow rewards land at the player's location (loot-on-the-ground), so quest completion can't silently break the carry invariant.
    location = state.locations.get(actor.location_id) if actor.location_id else None
    granted_item_names: list[str] = []
    for item_id in quest.rewards.items:
        item = state.items.get(item_id)
        if item is not None:
            granted_item_names.append(item.name)
        try:
            check_can_carry(actor, state.items, item_id)
        except InventoryInvalid:
            if location is not None:
                location.item_ids.append(item_id)
                if entities is not None:
                    entities.add(("locations", location.id))
            continue
        actor.inventory_ids.append(item_id)
    if entities is not None:
        entities.add(("characters", actor.id))
    if full is not None:
        # Inline imports avoid the engines→flow cycle (flow already imports engines).
        from ..flow.format import format_quest_success_log

        text = format_quest_success_log(
            title=quest.title,
            exp=quest.rewards.exp,
            gold=quest.rewards.gold,
            items=granted_item_names,
        )
        full.deferred_act_cards.append(
            (text, render("log.quest.success_log", "ko", title=quest.title))
        )
    if state.active_quest_id == quest.id:
        state.active_quest_id = None


def _maybe_unlock_dependents(state: GameState, dirty) -> None:
    """If all prerequisite_ids of another quest are completed, flip locked → active."""
    entities = _entities_set(dirty)
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
            if entities is not None:
                entities.add(("quests", q.id))


def update_chapter_progress(state: GameState, dirty=None) -> None:
    """Recompute progress for every chapter. Only required=true quests count."""
    entities = _entities_set(dirty)
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
            if entities is not None:
                entities.add(("chapters", ch.id))


def _maybe_advance_chapters(state: GameState, dirty) -> None:
    """If all required quests of a chapter are completed, flip active → completed."""
    entities = _entities_set(dirty)
    for ch in state.chapters.values():
        if ch.status != "active":
            continue
        if ch.progress.total > 0 and ch.progress.done >= ch.progress.total:
            ch.status = "completed"
            if entities is not None:
                entities.add(("chapters", ch.id))


def _maybe_unlock_chapters(state: GameState, dirty) -> None:
    """If all prerequisite_ids of a locked chapter are completed, flip locked → active."""
    entities = _entities_set(dirty)
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
            if entities is not None:
                entities.add(("chapters", ch.id))


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


def _trigger_matches(
    state: GameState,
    trigger,
    event_type: str,
    target_id: str | None,
) -> bool:
    """Exact-id match, or character_death fallback by location / race for hostile
    spawns whose runtime ids don't equal the scenario's literal trigger target_id."""
    if trigger.type != event_type:
        return False
    if trigger.target_id == target_id:
        return True
    if event_type != "character_death" or target_id is None:
        return False
    expected = state.characters.get(trigger.target_id)
    victim = state.characters.get(target_id)
    if expected is None or victim is None:
        return False
    # Same-location fallback (existing behavior, race-agnostic).
    if expected.location_id is not None and victim.location_id == expected.location_id:
        return victim.combat_behavior is not None
    # Race-match fallback for dynamic spawns whose runtime id differs from the
    # seed but share the seed's race. Restricted to the expected location's
    # direct neighbors so cross-region quests don't co-progress on the same kill.
    if expected.race_id is None or victim.race_id != expected.race_id:
        return False
    if victim.combat_behavior is None:
        return False
    if victim.location_id is None or expected.location_id is None:
        return False
    graph = state.graph()
    neighbor_ids = {e.to_id for e in connections_of(graph, expected.location_id)}
    return victim.location_id in neighbor_ids


def check_quests(
    state: GameState,
    event_type: str,
    target_id: str | None,
    dirty=None,
) -> list[str]:
    """Evaluate quests against an event; returns ids whose status changed. Triggers are single-fire.

    `dirty` may be `None` or a full `Dirty`. Only the latter receives a
    success/fail card on completion.
    """
    entities = _entities_set(dirty)
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
            if _trigger_matches(state, t, event_type, target_id):
                q.triggers_met[i] = True
                any_change = True
        for i, t in enumerate(q.fail_triggers):
            if q.fail_triggers_met[i]:
                continue
            if _trigger_matches(state, t, event_type, target_id):
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
        if entities is not None:
            entities.add(("quests", q.id))

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
    dirty,
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

        # locked / abandoned / failed quests are intentionally excluded.
        if is_giver_dead and q.status in ("active", "pending", "completed"):
            if q.status == "completed" and q.id in changed:
                # Undo same-turn completion so fail wins.
                changed.remove(q.id)
            _fail_quest(
                state,
                q,
                reason=render("log.quest.giver_dead_reason", "ko"),
                dirty=dirty,
            )
            if q.id not in changed:
                changed.append(q.id)

        elif is_kill_target_dead and not is_giver_dead:
            if q.status == "completed" and q.id in changed and q.success_reason is None:
                # Trigger path already completed it this turn — annotate reason.
                q.success_reason = "objective_killed"
