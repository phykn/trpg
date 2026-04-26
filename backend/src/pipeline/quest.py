"""퀘스트 자동 트리거·보상 적용·챕터 진행 (P3 §2.8).

이벤트 (`event_type`, `target_id`) 가 들어오면 active quest 들의 triggers/fail_triggers 를
순회하며 매칭. triggers 가 모두 충족되면 `completed` 로 전환 + 보상 적용. fail_triggers 가
하나라도 충족되면 `failed`. 상태가 바뀐 quest 가 다른 quest 의 prerequisite_ids 에 들어
있으면 `locked → active` 잠금 해제. chapter.progress 는 required=true 인 quest 만 카운트.

이벤트 종류 (자유 문자열, 시드가 정함):
- "character_death" — combat 또는 use(damage) 로 적 처치
- "location_enter" — apply_move 가 location 변경
- "item_use" — use endpoint 가 아이템 사용
"""
from __future__ import annotations

from ..domain.entities import Chapter, Quest
from ..rules import RULES  # noqa: F401  (튜닝 노브가 추가될 때 사용)
from ..domain.state import GameState

DirtySet = set[tuple[str, str]] | None


def _ensure_runtime_fields(quest: Quest) -> None:
    """triggers_met / fail_triggers_met 의 길이를 triggers 길이와 맞춤."""
    if len(quest.triggers_met) != len(quest.triggers):
        quest.triggers_met = [False] * len(quest.triggers)
    if len(quest.fail_triggers_met) != len(quest.fail_triggers):
        quest.fail_triggers_met = [False] * len(quest.fail_triggers)


def _apply_rewards(state: GameState, quest: Quest, dirty: DirtySet) -> None:
    """quest.rewards → 플레이어. P1·P2 단일 플레이어 전제."""
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
    """다른 quest 의 prerequisite_ids 가 모두 completed 면 locked → active."""
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
    """모든 chapter 의 progress 재계산. required=true 인 quest 만 카운트."""
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
    """chapter 의 required quest 가 모두 completed 면 active → completed."""
    for ch in state.chapters.values():
        if ch.status != "active":
            continue
        if ch.progress.total > 0 and ch.progress.done >= ch.progress.total:
            ch.status = "completed"
            if dirty is not None:
                dirty.add(("chapters", ch.id))


def check_quests(
    state: GameState,
    event_type: str,
    target_id: str | None,
    dirty: DirtySet = None,
) -> list[str]:
    """이벤트로 quest 평가. 상태가 바뀐 quest id 리스트 반환.

    같은 trigger 가 두 번 발화돼도 single-fire — `triggers_met[i]` 가 True 가 된 뒤로는
    재평가 시 무시 (docs §2.8 단일 충족 모델).
    """
    changed: list[str] = []
    for q in state.quests.values():
        if q.status != "active":
            continue
        _ensure_runtime_fields(q)

        any_change = False
        # success triggers
        for i, t in enumerate(q.triggers):
            if q.triggers_met[i]:
                continue
            if t.type == event_type and t.target_id == target_id:
                q.triggers_met[i] = True
                any_change = True
        # fail triggers
        for i, t in enumerate(q.fail_triggers):
            if q.fail_triggers_met[i]:
                continue
            if t.type == event_type and t.target_id == target_id:
                q.fail_triggers_met[i] = True
                any_change = True

        if not any_change:
            continue

        # 상태 전환: fail 우선 (한 trigger 만 발동돼도 fail).
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
    return changed
