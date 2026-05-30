from __future__ import annotations

from dataclasses import dataclass, field


class ActionGroundingError(ValueError):
    pass


EQUIP_SLOTS = frozenset({"weapon", "armor", "accessory"})


@dataclass(frozen=True)
class ViewIds:
    in_combat: bool = False
    entity_ids: set[str] = field(default_factory=set)
    character_ids: set[str] = field(default_factory=set)
    non_player_character_ids: set[str] = field(default_factory=set)
    attackable_character_ids: set[str] = field(default_factory=set)
    protected_character_ids: set[str] = field(default_factory=set)
    connection_ids: set[str] = field(default_factory=set)
    location_ids: set[str] = field(default_factory=set)
    inventory_item_ids: set[str] = field(default_factory=set)
    location_item_ids: set[str] = field(default_factory=set)
    equipment_item_ids: set[str] = field(default_factory=set)
    visible_item_ids: set[str] = field(default_factory=set)
    skill_ids: set[str] = field(default_factory=set)
    merchant_ids: set[str] = field(default_factory=set)
    merchant_stock_item_ids: set[str] = field(default_factory=set)
    corpse_ids: set[str] = field(default_factory=set)
    corpse_inventory_item_ids: set[str] = field(default_factory=set)
    corpse_inventory_by_corpse: dict[str, set[str]] = field(default_factory=dict)
    quest_ids: set[str] = field(default_factory=set)
    choice_ids: set[str] = field(default_factory=set)
    self_refs: set[str] = field(default_factory=set)

    @property
    def actor_refs(self) -> set[str]:
        return self.character_ids | self.merchant_ids | self.corpse_ids | self.self_refs

    @property
    def exposed_item_ids(self) -> set[str]:
        return (
            self.inventory_item_ids
            | self.location_item_ids
            | self.equipment_item_ids
            | self.visible_item_ids
            | self.merchant_stock_item_ids
            | self.corpse_inventory_item_ids
        )

    @property
    def perceive_targets(self) -> set[str]:
        return self.entity_ids | self.corpse_ids | self.location_ids
