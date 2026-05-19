from dataclasses import dataclass, field
from typing import Any

from src.game.domain.action import Action, ActionCheckHint, ActionOutput


class ActionGroundingError(ValueError):
    pass


_EQUIP_SLOTS = frozenset({"weapon", "armor", "accessory"})


@dataclass(frozen=True)
class _ViewIds:
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


def validate_grounded_output(
    output: ActionOutput,
    surroundings: dict[str, Any],
    *,
    allow_partial: bool = False,
) -> ActionOutput:
    if output.actions is None:
        return output
    view = _collect_view_ids(surroundings)
    if not allow_partial:
        for action in output.actions:
            _validate_action(action, view)
        return output
    return _partially_grounded_output(output, view)


def _partially_grounded_output(output: ActionOutput, view: _ViewIds) -> ActionOutput:
    actions = output.actions or []
    if len(actions) <= 1:
        for action in actions:
            _validate_action(action, view)
        return output

    checks = output.action_checks
    keep_checks = bool(checks)
    next_actions: list[Action] = []
    next_checks: list[ActionCheckHint] = []
    valid_original = False
    first_error: ActionGroundingError | None = None
    for index, action in enumerate(actions):
        try:
            _validate_action(action, view)
        except ActionGroundingError as exc:
            first_error = first_error or exc
            next_actions.append(Action(verb="pass", note=str(exc)[:120]))
            if keep_checks:
                next_checks.append(ActionCheckHint())
            continue
        valid_original = True
        next_actions.append(action)
        if keep_checks:
            next_checks.append(checks[index])

    if not valid_original and first_error is not None:
        raise first_error
    return ActionOutput.model_validate(
        {
            "actions": [
                action.model_dump(mode="json", by_alias=True)
                for action in next_actions
            ],
            "action_checks": [
                check.model_dump(mode="json") for check in next_checks
            ],
        },
        context={"in_combat": view.in_combat},
    )


def _collect_view_ids(surroundings: dict[str, Any]) -> _ViewIds:
    entity_ids: set[str] = set()
    character_ids: set[str] = set()
    non_player_character_ids: set[str] = set()
    attackable_character_ids: set[str] = set()
    protected_character_ids: set[str] = set()
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
        for location_id in [_str((surroundings.get("location") or {}).get("id"))]
        if location_id is not None
    }
    inventory_item_ids = _ids_from_list(surroundings.get("inventory"))
    location_item_ids = _ids_from_list(surroundings.get("location_items"))
    equipment_item_ids = _equipment_item_ids(surroundings.get("equipment"))
    skill_ids = _ids_from_list(surroundings.get("skills"))
    merchant_ids, merchant_stock_item_ids = _merchant_ids(surroundings.get("merchants"))
    (
        corpse_ids,
        corpse_inventory_item_ids,
        corpse_inventory_by_corpse,
    ) = _corpse_ids(surroundings.get("corpses"))
    quest_ids = _ids_from_list(surroundings.get("quests"))
    self_refs = _self_refs(player_ids)

    return _ViewIds(
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
        equipment_item_ids=equipment_item_ids,
        visible_item_ids=visible_item_ids,
        skill_ids=skill_ids,
        merchant_ids=merchant_ids,
        merchant_stock_item_ids=merchant_stock_item_ids,
        corpse_ids=corpse_ids,
        corpse_inventory_item_ids=corpse_inventory_item_ids,
        corpse_inventory_by_corpse=corpse_inventory_by_corpse,
        quest_ids=quest_ids,
        self_refs=self_refs,
    )


def _validate_action(action: Action, view: _ViewIds) -> None:
    if action.verb == "move":
        destination = _single(action.to) or _single(action.what)
        if view.in_combat and destination is None:
            return
        _require_id(
            destination,
            view.connection_ids,
            action=action,
            field="to",
        )
    elif action.verb == "use":
        item_id = _single(action.what) or _single(action.with_)
        _validate_use_item(item_id, view, action=action)
        target = _single(action.to)
        if target is not None:
            _require_id(target, view.character_ids, action=action, field="to")
    elif action.verb == "attack":
        _reject_protected_attack(_list(action.what), view, action=action)
        _require_all_ids(
            _list(action.what),
            view.attackable_character_ids,
            action=action,
            field="what",
        )
    elif action.verb == "speak":
        target = _single(action.to) or _single(action.what)
        if target is not None:
            _require_id(
                target,
                view.non_player_character_ids,
                action=action,
                field="to",
            )
    elif action.verb == "transfer":
        _validate_transfer(action, view)
    elif action.verb == "perceive" and _list(action.what):
        _require_all_ids(
            _list(action.what),
            view.perceive_targets,
            action=action,
            field="what",
        )


def _reject_protected_attack(
    values: list[str],
    view: _ViewIds,
    *,
    action: Action,
) -> None:
    protected = [value for value in values if value in view.protected_character_ids]
    if protected:
        raise ActionGroundingError(
            f"protected target cannot be attacked action={action.verb} "
            f"what: {protected!r}"
        )


def _validate_transfer(action: Action, view: _ViewIds) -> None:
    item_id = _single(action.what) or _single(action.with_)
    if action.how == "equip":
        _require_id(
            item_id,
            view.inventory_item_ids | view.equipment_item_ids,
            action=action,
            field="what",
        )
        _require_slot(action.to, action=action, field="to")
        return
    if action.how == "unequip":
        _require_id(
            item_id,
            view.equipment_item_ids,
            action=action,
            field="what",
        )
        return
    if item_id in view.location_item_ids:
        _require_id(
            action.from_,
            view.location_ids,
            action=action,
            field="from",
        )
        _require_id(action.to, view.self_refs, action=action, field="to")
        return
    source = _single(action.from_)
    if source in view.corpse_ids:
        _require_id(source, view.corpse_ids, action=action, field="from")
        _require_id(action.to, view.self_refs, action=action, field="to")
        if item_id not in view.corpse_inventory_by_corpse.get(source, set()):
            raise ActionGroundingError(
                f"corpse item mismatch action={action.verb} "
                f"from: {source!r} what: {item_id!r}"
            )
        return
    _require_id(action.from_, view.actor_refs, action=action, field="from")
    _require_id(action.to, view.actor_refs, action=action, field="to")
    if item_id is not None:
        allowed_ids = view.exposed_item_ids
        if action.how in {"accept", "abandon"}:
            allowed_ids = allowed_ids | view.quest_ids
        _require_id(item_id, allowed_ids, action=action, field="what")


def _validate_use_item(
    item_id: str | None,
    view: _ViewIds,
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


def _require_id(
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


def _require_slot(value: object, *, action: Action, field: str) -> None:
    if value not in _EQUIP_SLOTS:
        raise ActionGroundingError(
            f"ungrounded action={action.verb} {field}: {value!r}"
        )


def _require_all_ids(
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


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _ids_from_list(value: object) -> set[str]:
    return {
        entry_id
        for entry_id in (_str(entry.get("id")) for entry in _dicts(value))
        if entry_id
    }


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


def _corpse_ids(value: object) -> tuple[set[str], set[str], dict[str, set[str]]]:
    corpse_ids: set[str] = set()
    item_ids: set[str] = set()
    by_corpse: dict[str, set[str]] = {}
    for corpse in _dicts(value):
        corpse_id = _str(corpse.get("id"))
        corpse_item_ids = _ids_from_list(corpse.get("inventory"))
        if corpse_id is not None:
            corpse_ids.add(corpse_id)
            by_corpse[corpse_id] = corpse_item_ids
        item_ids |= corpse_item_ids
    return corpse_ids, item_ids, by_corpse


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
