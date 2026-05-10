from src.game.domain.action import Action
from src.llm.context.graph_surroundings import build_graph_surroundings
from src.locale.render import render
from src.wire.graph_to_front import graph_to_front_state

from .state import GameRuntimeState


def answer_graph_query(runtime: GameRuntimeState, action: Action) -> str:
    topic = _single(action.what) or "surroundings"
    surroundings = build_graph_surroundings(runtime)
    locale = runtime.progress.locale
    if topic == "exits":
        return _exits_text(surroundings, locale)
    if topic == "inventory":
        return _inventory_text(surroundings, locale)
    if topic == "status":
        return _status_text(runtime)
    return _surroundings_text(surroundings, locale)


def _surroundings_text(surroundings: dict, locale: str) -> str:
    location = surroundings.get("location") or {}
    location_name = location.get("name") or render("runtime.query.unknown_place", locale)
    npcs = _entity_names(surroundings, "npc")
    items = _entity_names(surroundings, "item")
    exits = _entity_names(surroundings, "connection")

    pieces = [
        render("runtime.query.current_location", locale, location=location_name)
    ]
    pieces.append(
        render("runtime.query.nearby_entities", locale, names=_join(npcs + items))
        if npcs or items
        else render("runtime.query.no_nearby_entities", locale)
    )
    pieces.append(
        render("runtime.query.exits", locale, names=_join(exits))
        if exits
        else render("runtime.query.no_exits", locale)
    )
    return " ".join(pieces)


def _exits_text(surroundings: dict, locale: str) -> str:
    exits = _entity_names(surroundings, "connection")
    if not exits:
        return render("runtime.query.no_exits", locale)
    return render("runtime.query.exits", locale, names=_join(exits))


def _inventory_text(surroundings: dict, locale: str) -> str:
    names = _names_from_entries(surroundings.get("inventory"))
    if not names:
        return render("runtime.query.no_inventory", locale)
    return render("runtime.query.inventory", locale, names=_join(names))


def _status_text(runtime: GameRuntimeState) -> str:
    hero = graph_to_front_state(runtime).hero
    hp = _resource_label(hero.resources["hp"].state, runtime.progress.locale)
    mp = _resource_label(hero.resources["mp"].state, runtime.progress.locale)
    return render("runtime.query.status", runtime.progress.locale, hp=hp, mp=mp)


def _entity_names(surroundings: dict, entity_type: str) -> list[str]:
    names: list[str] = []
    for entry in surroundings.get("entities") or []:
        if not isinstance(entry, dict) or entry.get("type") != entity_type:
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _names_from_entries(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _resource_label(state: str, locale: str) -> str:
    try:
        return render(f"runtime.resource.{state}", locale)
    except KeyError:
        return state


def _join(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names)


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
