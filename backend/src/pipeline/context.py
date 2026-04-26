from collections import Counter
from pathlib import Path

from ..domain.entities import Character, ConsumableEffect
from ..rules import RULES
from ..state.models import GameState


# --- world layer -----------------------------------------------------------


def build_world_layer(profile_dir: str, profile: str) -> str:
    return (Path(profile_dir) / profile / "world.md").read_text(encoding="utf-8")


# --- session layer ---------------------------------------------------------


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


# --- history layer ---------------------------------------------------------


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


# --- surroundings layer ----------------------------------------------------


def _state_tags(actor: Character, npc: Character) -> list[str]:
    tags: list[str] = []
    aff = actor.relations.get(npc.id, 0)
    threshold = RULES.social.friendly_threshold
    if aff >= threshold:
        tags.append(f"우호적(affinity {aff})")
    elif aff <= -threshold:
        tags.append(f"경계중(affinity {aff})")
    if npc.max_hp > 0:
        hp_pct = round(npc.hp / npc.max_hp * 100)
        if hp_pct < 50:
            tags.append(f"부상(hp {hp_pct}%)")
    return tags


def _inventory_payload(state: GameState, actor: Character) -> list[dict]:
    """judge use 매칭용. consumable / on_use 트리거 있는 아이템만 노출.
    같은 item_id 끼리 묶어 qty 카운트. weapon/armor 는 use 대상 아니라 제외."""
    counts: Counter[str] = Counter(actor.inventory_ids)
    out: list[dict] = []
    for item_id, qty in counts.items():
        item = state.items.get(item_id)
        if item is None:
            continue
        eff = item.effects
        is_consumable = isinstance(eff, ConsumableEffect)
        has_on_use = bool(item.on_use)
        if not is_consumable and not has_on_use:
            continue
        entry: dict = {"id": item_id, "name": item.name, "qty": qty}
        if is_consumable:
            entry["effect"] = eff.effect
        if item.description:
            entry["description"] = item.description
        out.append(entry)
    return out


def _learned_skills_payload(actor: Character) -> list[dict]:
    """judge 의미 매칭용. learned_skills 만 노출 — racial_skills 는 자동 매칭 대상이 아님."""
    out: list[dict] = []
    for s in actor.learned_skills:
        if s.level > actor.level or actor.mp < s.mp_cost:
            continue  # 게이트·MP 미달이면 매칭 후보에서 제외 (silent 폴백 유도)
        item: dict = {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "target": s.target,
        }
        if s.description:
            item["description"] = s.description
        if s.special_effect:
            item["effect"] = s.special_effect
        out.append(item)
    return out


def build_surroundings(state: GameState, actor_id: str) -> dict:
    actor = state.characters[actor_id]
    if not actor.location_id or actor.location_id not in state.locations:
        return {
            "location": None,
            "entities": [],
            "learned_skills": [],
            "inventory": [],
        }
    location = state.locations[actor.location_id]

    entities: list[dict] = [{"id": actor_id, "name": actor.name, "type": "player"}]

    for cid, char in state.characters.items():
        if cid == actor_id or char.location_id != actor.location_id:
            continue
        if not char.alive:
            continue
        entry: dict = {"id": cid, "name": char.name, "type": "npc"}
        tags = _state_tags(actor, char)
        if tags:
            entry["state_tags"] = tags
        entities.append(entry)

    for item_id in location.item_ids:
        if item_id in state.items:
            entities.append(
                {
                    "id": item_id,
                    "name": state.items[item_id].name,
                    "type": "item",
                }
            )

    for conn in location.connections:
        if conn.target_id not in state.locations:
            continue
        entry = {
            "id": conn.target_id,
            "name": state.locations[conn.target_id].name,
            "type": "connection",
        }
        if conn.difficulty:
            entry["difficulty"] = conn.difficulty
        entities.append(entry)

    location_data: dict = {
        "id": location.id,
        "name": location.name,
        "description": location.description,
    }
    if location.tags:
        location_data["tags"] = location.tags
    if location.weather:
        location_data["weather"] = location.weather
    if location.difficulty:
        location_data["difficulty"] = location.difficulty

    return {
        "location": location_data,
        "entities": entities,
        "learned_skills": _learned_skills_payload(actor),
        "inventory": _inventory_payload(state, actor),
    }
