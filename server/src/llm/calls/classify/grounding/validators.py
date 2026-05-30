from __future__ import annotations

from src.game.domain.action import Action

from .coerce import single_value, str_list
from .types import EQUIP_SLOTS, ActionGroundingError, ViewIds


def validate_action(action: Action, view: ViewIds) -> None:
    if action.verb == "move":
        destination = single_value(action.to) or single_value(action.what)
        if view.in_combat and destination is None:
            return
        if action.note == "generated_open_move" and destination is None:
            return
        require_id(
            destination,
            view.connection_ids,
            action=action,
            field="to",
        )
    elif action.verb == "use":
        item_id = single_value(action.what) or single_value(action.with_)
        validate_use_item(item_id, view, action=action)
        target = single_value(action.to)
        if target is not None:
            require_id(target, view.character_ids, action=action, field="to")
    elif action.verb == "attack":
        reject_protected_attack(str_list(action.what), view, action=action)
        require_all_ids(
            str_list(action.what),
            view.attackable_character_ids,
            action=action,
            field="what",
        )
    elif action.verb == "speak":
        target = single_value(action.to) or single_value(action.what)
        if target is not None:
            require_id(
                target,
                view.non_player_character_ids,
                action=action,
                field="to",
            )
    elif action.verb == "transfer":
        validate_transfer(action, view)
    elif action.verb == "perceive" and str_list(action.what):
        require_all_ids(
            str_list(action.what),
            view.perceive_targets,
            action=action,
            field="what",
        )
    elif action.verb == "decide":
        require_id(
            single_value(action.what),
            view.quest_ids,
            action=action,
            field="what",
        )
        require_id(
            action.how,
            view.choice_ids,
            action=action,
            field="how",
        )


def reject_protected_attack(
    values: list[str],
    view: ViewIds,
    *,
    action: Action,
) -> None:
    protected = [value for value in values if value in view.protected_character_ids]
    if protected:
        raise ActionGroundingError(
            f"protected target cannot be attacked action={action.verb} "
            f"what: {protected!r}"
        )


def validate_transfer(action: Action, view: ViewIds) -> None:
    item_id = single_value(action.what) or single_value(action.with_)
    if action.how == "equip":
        require_id(
            item_id,
            view.inventory_item_ids | view.equipment_item_ids,
            action=action,
            field="what",
        )
        require_slot(action.to, action=action, field="to")
        return
    if action.how == "unequip":
        require_id(
            item_id,
            view.equipment_item_ids,
            action=action,
            field="what",
        )
        return
    if item_id in view.location_item_ids:
        require_id(
            action.from_,
            view.location_ids,
            action=action,
            field="from",
        )
        require_id(action.to, view.self_refs, action=action, field="to")
        return
    source = single_value(action.from_)
    if source in view.corpse_ids:
        require_id(source, view.corpse_ids, action=action, field="from")
        require_id(action.to, view.self_refs, action=action, field="to")
        if item_id not in view.corpse_inventory_by_corpse.get(source, set()):
            raise ActionGroundingError(
                f"corpse item mismatch action={action.verb} "
                f"from: {source!r} what: {item_id!r}"
            )
        return
    require_id(action.from_, view.actor_refs, action=action, field="from")
    require_id(action.to, view.actor_refs, action=action, field="to")
    if item_id is not None:
        allowed_ids = view.exposed_item_ids
        if action.how in {"accept", "abandon"}:
            allowed_ids = allowed_ids | view.quest_ids
        require_id(item_id, allowed_ids, action=action, field="what")


def validate_use_item(
    item_id: str | None,
    view: ViewIds,
    *,
    action: Action,
) -> None:
    if item_id in view.inventory_item_ids or item_id in view.skill_ids:
        return
    visible_uncarried = (
        view.location_item_ids
        | view.visible_item_ids
        | view.merchant_stock_item_ids
        | view.corpse_inventory_item_ids
    )
    if item_id in visible_uncarried:
        raise ActionGroundingError(
            f"item is not carried action={action.verb} what: {item_id!r}"
        )
    raise ActionGroundingError(
        f"missing item action={action.verb} what: {item_id!r}"
    )


def require_id(
    value: object,
    allowed: set[str],
    *,
    action: Action,
    field: str,
) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise ActionGroundingError(
            f"ungrounded action={action.verb} {field}: {value!r}"
        )


def require_slot(value: object, *, action: Action, field: str) -> None:
    if value not in EQUIP_SLOTS:
        raise ActionGroundingError(
            f"ungrounded action={action.verb} {field}: {value!r}"
        )


def require_all_ids(
    values: list[str],
    allowed: set[str],
    *,
    action: Action,
    field: str,
) -> None:
    missing = [value for value in values if value not in allowed]
    if missing:
        raise ActionGroundingError(
            f"ungrounded action={action.verb} {field}: {missing!r}"
        )
