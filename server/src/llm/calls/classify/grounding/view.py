from __future__ import annotations

from typing import Any

from .coerce import (
    corpse_ids,
    dict_entries,
    equipment_item_ids,
    ids_from_list,
    merchant_ids,
    quest_choice_ids,
    self_refs,
    str_value,
)
from .types import ViewIds


def collect_view_ids(surroundings: dict[str, Any]) -> ViewIds:
    entity_ids: set[str] = set()
    character_ids: set[str] = set()
    non_player_character_ids: set[str] = set()
    attackable_character_ids: set[str] = set()
    protected_character_ids: set[str] = set()
    connection_ids: set[str] = set()
    visible_item_ids: set[str] = set()
    player_ids: set[str] = set()

    for entry in dict_entries(surroundings.get("entities")):
        entry_id = str_value(entry.get("id"))
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
            if entry.get("protected") is True:
                protected_character_ids.add(entry_id)
            else:
                attackable_character_ids.add(entry_id)
        elif entry_type == "connection":
            connection_ids.add(entry_id)
        elif entry_type == "item":
            visible_item_ids.add(entry_id)

    location_ids = {
        location_id
        for location_id in [str_value((surroundings.get("location") or {}).get("id"))]
        if location_id is not None
    }
    inventory_item_ids = ids_from_list(surroundings.get("inventory"))
    location_item_ids = ids_from_list(surroundings.get("location_items"))
    current_equipment_item_ids = equipment_item_ids(surroundings.get("equipment"))
    skill_ids = ids_from_list(surroundings.get("skills"))
    current_merchant_ids, merchant_stock_item_ids = merchant_ids(
        surroundings.get("merchants")
    )
    (
        current_corpse_ids,
        corpse_inventory_item_ids,
        corpse_inventory_by_corpse,
    ) = corpse_ids(surroundings.get("corpses"))
    quests = dict_entries(surroundings.get("quests"))
    quest_ids = ids_from_list(quests)
    choice_ids = quest_choice_ids(quests)
    current_self_refs = self_refs(player_ids)

    return ViewIds(
        in_combat=bool(surroundings.get("in_combat", False)),
        entity_ids=entity_ids,
        character_ids=character_ids,
        non_player_character_ids=non_player_character_ids,
        attackable_character_ids=attackable_character_ids,
        protected_character_ids=protected_character_ids,
        connection_ids=connection_ids,
        location_ids=location_ids,
        inventory_item_ids=inventory_item_ids,
        location_item_ids=location_item_ids,
        equipment_item_ids=current_equipment_item_ids,
        visible_item_ids=visible_item_ids,
        skill_ids=skill_ids,
        merchant_ids=current_merchant_ids,
        merchant_stock_item_ids=merchant_stock_item_ids,
        corpse_ids=current_corpse_ids,
        corpse_inventory_item_ids=corpse_inventory_item_ids,
        corpse_inventory_by_corpse=corpse_inventory_by_corpse,
        quest_ids=quest_ids,
        choice_ids=choice_ids,
        self_refs=current_self_refs,
    )
