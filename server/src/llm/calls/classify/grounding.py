from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.game.domain.verb import Verb

from .schema import JudgeOutput


class JudgeGroundingError(ValueError):
    pass


@dataclass(frozen=True)
class _ViewIds:
    in_combat: bool = False
    entity_ids: set[str] = field(default_factory=set)
    character_ids: set[str] = field(default_factory=set)
    non_player_character_ids: set[str] = field(default_factory=set)
    connection_ids: set[str] = field(default_factory=set)
    location_ids: set[str] = field(default_factory=set)
    inventory_item_ids: set[str] = field(default_factory=set)
    equipment_item_ids: set[str] = field(default_factory=set)
    visible_item_ids: set[str] = field(default_factory=set)
    skill_ids: set[str] = field(default_factory=set)
    merchant_ids: set[str] = field(default_factory=set)
    merchant_stock_item_ids: set[str] = field(default_factory=set)
    carryable_item_ids: set[str] = field(default_factory=set)
    corpse_ids: set[str] = field(default_factory=set)
    corpse_inventory_item_ids: set[str] = field(default_factory=set)
    self_refs: set[str] = field(default_factory=set)

    @property
    def actor_refs(self) -> set[str]:
        return self.character_ids | self.merchant_ids | self.corpse_ids | self.self_refs

    @property
    def exposed_item_ids(self) -> set[str]:
        return (
            self.inventory_item_ids
            | self.equipment_item_ids
            | self.visible_item_ids
            | self.merchant_stock_item_ids
            | self.carryable_item_ids
            | self.corpse_inventory_item_ids
        )

    @property
    def perceive_target_ids(self) -> set[str]:
        return self.entity_ids | self.corpse_ids | self.location_ids


def validate_grounded_output(
    output: JudgeOutput,
    surroundings: dict[str, Any],
) -> JudgeOutput:
    if output.actions is None:
        return output
    view = _collect_view_ids(surroundings)
    for verb in output.actions:
        _validate_verb(verb, view)
    return output


def _collect_view_ids(surroundings: dict[str, Any]) -> _ViewIds:
    entity_ids: set[str] = set()
    character_ids: set[str] = set()
    non_player_character_ids: set[str] = set()
    connection_ids: set[str] = set()
    visible_item_ids: set[str] = set()
    player_ids: set[str] = set()

    for entry in _dicts(surroundings.get("entities")):
        entry_id = _str(entry.get("id"))
        if entry_id is None:
            continue
        entity_ids.add(entry_id)
        entry_type = entry.get("type")
        if entry_type == "player":
            character_ids.add(entry_id)
            player_ids.add(entry_id)
        elif entry_type in {"npc", "enemy"}:
            character_ids.add(entry_id)
            non_player_character_ids.add(entry_id)
        elif entry_type == "connection":
            connection_ids.add(entry_id)
        elif entry_type == "item":
            visible_item_ids.add(entry_id)

    location_ids = {
        location_id
        for location_id in [_str((surroundings.get("location") or {}).get("id"))]
        if location_id is not None
    }
    inventory_item_ids = _ids_from_list(surroundings.get("inventory"))
    equipment_item_ids = _equipment_item_ids(surroundings.get("equipment"))
    skill_ids = _ids_from_list(surroundings.get("skills"))
    merchant_ids, merchant_stock_item_ids = _merchant_ids(surroundings.get("merchants"))
    carryable_item_ids = _carryable_item_ids(surroundings.get("entities"))
    corpse_ids, corpse_inventory_item_ids = _corpse_ids(surroundings.get("corpses"))
    self_refs = _self_refs(player_ids)

    return _ViewIds(
        in_combat=bool(surroundings.get("in_combat", False)),
        entity_ids=entity_ids,
        character_ids=character_ids,
        non_player_character_ids=non_player_character_ids,
        connection_ids=connection_ids,
        location_ids=location_ids,
        inventory_item_ids=inventory_item_ids,
        equipment_item_ids=equipment_item_ids,
        visible_item_ids=visible_item_ids,
        skill_ids=skill_ids,
        merchant_ids=merchant_ids,
        merchant_stock_item_ids=merchant_stock_item_ids,
        carryable_item_ids=carryable_item_ids,
        corpse_ids=corpse_ids,
        corpse_inventory_item_ids=corpse_inventory_item_ids,
        self_refs=self_refs,
    )


def _validate_verb(verb: Verb, view: _ViewIds) -> None:
    modifiers = verb.modifiers or {}
    if verb.name == "move":
        if view.in_combat and modifiers.get("destination") is None:
            return
        _require_id(
            modifiers.get("destination"),
            view.connection_ids,
            verb=verb,
            field="destination",
        )
    elif verb.name == "use":
        _require_id(modifiers.get("item_id"), view.inventory_item_ids, verb=verb, field="item_id")
        target_id = modifiers.get("target_id")
        if target_id is not None:
            _require_id(target_id, view.character_ids, verb=verb, field="target_id")
    elif verb.name == "attack":
        _require_all_ids(
            verb.target_ids,
            view.non_player_character_ids,
            verb=verb,
            field="target_ids",
        )
    elif verb.name == "cast":
        _require_id(modifiers.get("skill_id"), view.skill_ids, verb=verb, field="skill_id")
        if verb.target_ids:
            _require_all_ids(
                verb.target_ids,
                view.character_ids,
                verb=verb,
                field="target_ids",
            )
    elif verb.name == "speak":
        target_id = modifiers.get("target")
        if target_id is not None:
            _require_id(
                target_id,
                view.non_player_character_ids,
                verb=verb,
                field="target",
            )
    elif verb.name == "transfer":
        _validate_transfer(verb, view)
    elif verb.name == "perceive" and verb.target_ids:
        _require_all_ids(
            verb.target_ids,
            view.perceive_target_ids,
            verb=verb,
            field="target_ids",
        )


def _validate_transfer(verb: Verb, view: _ViewIds) -> None:
    modifiers = verb.modifiers or {}
    _require_id(modifiers.get("from_id"), view.actor_refs, verb=verb, field="from_id")
    _require_id(modifiers.get("to_id"), view.actor_refs, verb=verb, field="to_id")
    item_id = modifiers.get("item_id")
    if item_id is not None:
        _require_id(item_id, view.exposed_item_ids, verb=verb, field="item_id")


def _require_id(
    value: object,
    allowed: set[str],
    *,
    verb: Verb,
    field: str,
) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise JudgeGroundingError(
            f"ungrounded verb={verb.name} {field}: {value!r}"
        )


def _require_all_ids(
    values: list[str],
    allowed: set[str],
    *,
    verb: Verb,
    field: str,
) -> None:
    missing = [value for value in values if value not in allowed]
    if missing:
        raise JudgeGroundingError(
            f"ungrounded verb={verb.name} {field}: {missing!r}"
        )


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _ids_from_list(value: object) -> set[str]:
    return {entry_id for entry_id in (_str(entry.get("id")) for entry in _dicts(value)) if entry_id}


def _equipment_item_ids(value: object) -> set[str]:
    if not isinstance(value, dict):
        return set()
    ids: set[str] = set()
    for item in value.values():
        if isinstance(item, dict):
            item_id = _str(item.get("id"))
            if item_id is not None:
                ids.add(item_id)
    return ids


def _merchant_ids(value: object) -> tuple[set[str], set[str]]:
    merchant_ids: set[str] = set()
    item_ids: set[str] = set()
    for merchant in _dicts(value):
        merchant_id = _str(merchant.get("id"))
        if merchant_id is not None:
            merchant_ids.add(merchant_id)
        item_ids |= _ids_from_list(merchant.get("stock"))
    return merchant_ids, item_ids


def _carryable_item_ids(value: object) -> set[str]:
    item_ids: set[str] = set()
    for entity in _dicts(value):
        item_ids |= _ids_from_list(entity.get("carryables"))
    return item_ids


def _corpse_ids(value: object) -> tuple[set[str], set[str]]:
    corpse_ids: set[str] = set()
    item_ids: set[str] = set()
    for corpse in _dicts(value):
        corpse_id = _str(corpse.get("id"))
        if corpse_id is not None:
            corpse_ids.add(corpse_id)
        item_ids |= _ids_from_list(corpse.get("inventory"))
    return corpse_ids, item_ids


def _self_refs(player_ids: set[str]) -> set[str]:
    refs = {"<self>.inventory", "<self>.equipped"}
    for slot in ("weapon", "armor", "accessory"):
        refs.add(f"<self>.equipped.{slot}")
    for player_id in player_ids:
        refs.add(player_id)
        refs.add(f"{player_id}.inventory")
        refs.add(f"{player_id}.equipped")
        for slot in ("weapon", "armor", "accessory"):
            refs.add(f"{player_id}.equipped.{slot}")
    return refs
