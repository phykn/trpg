from __future__ import annotations

from .locale import ko
from .onto.atoms import PLAYER
from .onto.view import Obs
from .rules.acts import Action, make
from .rules.candidates import space
from .rules.roll import preview
from .view import action_label, chips, effect_names, rely_label, tag_name

# A card is a function of (Vₜ, plan), plus the relevant reliances for a roll card, and makes no event (engine.md 4).


def rely_options(u, o: Obs, a: Action) -> list[str]:
    for slot in space(u, o):
        if slot.schema == a.schema and slot.intent == a.intent:
            return [v for v in slot.values("rely") if v is not None]
    return []


def preview_json(u, o: Obs, p: dict, a: Action) -> dict:
    pv = preview(u, o, a)
    clock = None
    if pv.clock:
        clock = {"id": pv.clock["id"], "name": u.name(pv.clock["id"]), "boxes": pv.clock["boxes"],
                 "fill": pv.clock["fill"]}
    return {
        "risk": pv.risk, "mods": chips(u, p, pv.mods.chips()), "z": pv.z,
        "dc": pv.dc,
        "stakes": {"clock": pv.clock["fail"] if pv.clock else 0, "weight": pv.stakes["weight"]},
        "clock": clock, "gain": _gain(u, p, pv.gain),
    }


def _gain(u, p: dict, g: dict) -> dict:
    if g["kind"] == "fill":
        return {"kind": "fill", "boxes": g["boxes"], "fit": g["fit"]}
    if g["kind"] == "tag":
        return {"kind": "tag", "remove": tag_name(p, g["remove"]) if g["remove"] else None}
    if g["kind"] == "favor":
        return {"kind": "favor", "effects": effect_names(u, g["effects"])}
    if g["kind"] == "follow":
        return {"kind": "follow"}
    return {"kind": "topic"}


def target_json(u, o: Obs, a: Action) -> dict | None:
    x = a.intent[0] if a.intent else None
    if x is None or x == PLAYER or u.kind(x) is None:
        return None
    out = {"id": x, "name": u.name(x)}
    if x in u.obstacles:
        out |= {"fill": o.facts.fill(x), "boxes": u.boxes(x)}
    return out


def _plan(u, o: Obs, p: dict, a: Action, rest_labels: list[str]) -> dict:
    return {"step": {"action": str(a), "label": action_label(u, o, p, a), "target": target_json(u, o, a)},
            "rest": rest_labels}


def roll_card(u, o: Obs, p: dict, a: Action, rest: list, rest_labels: list[str], echo: dict, card_id: str,
              selected: str | None = None, relies: list[str] | None = None) -> dict:
    base = a.with_(rely=None)
    options = []
    for v in rely_options(u, o, base) if relies is None else relies:
        av = base.with_(rely=v)
        kind = v.split(":", 1)[0]
        options.append({"id": str(av), "label": rely_label(u, p, o.facts, v), "consumed": kind in ko.CONSUMED,
                        "note": ko.CONSUMED.get(kind), "preview": preview_json(u, o, p, av)})
    options.append({"id": str(base), "label": ko.NO_RELY, "consumed": False, "note": None,
                    "preview": preview_json(u, o, p, base)})
    ids = [x["id"] for x in options]
    chosen = str(base.with_(rely=selected)) if selected else str(base)
    public = {"id": card_id, "kind": "roll", "echo": echo, "plan": _plan(u, o, p, base, rest_labels),
              "options": options, "selected": chosen if chosen in ids else str(base)}
    return {"id": card_id, "kind": "roll", "options": ids, "rest": rest, "public": public}


def confirm_card(u, o: Obs, p: dict, a: Action, rest: list, rest_labels: list[str], echo: dict,
                 card_id: str) -> dict:
    effects = []
    if a.schema == "choose":
        g, c = a.intent
        effects = next(e for cid, _, e in u.obstacles[g].choices if cid == c)
    elif a.schema == "give":
        effects = [("move", *a.intent)]
    option = {"id": str(a), "label": action_label(u, o, p, a), "effects": effect_names(u, effects)}
    public = {"id": card_id, "kind": "confirm", "echo": echo, "plan": _plan(u, o, p, a, rest_labels),
              "options": [option], "selected": None}
    return {"id": card_id, "kind": "confirm", "options": [str(a)], "rest": rest, "public": public}


def ways(u, o: Obs) -> list[str]:
    return [slot.intent[0] for slot in space(u, o) if slot.schema == "go"]


def move_card(u, o: Obs, p: dict, a: Action, rest: list, rest_labels: list[str], echo: dict, card_id: str,
              only: bool = False) -> dict:
    """The sentence's way first, then the other ways unless the sentence named it alone; each says who comes along
    (engine.md 4.4)."""
    out = [a.intent[0]] if only else [a.intent[0], *(q for q in ways(u, o) if q != a.intent[0])]
    company = [h for h, g in o.facts.rows("follows") if g == PLAYER]
    options = []
    for q in out:
        effects = [ko.fill(ko.MOVE_LEFT, name=u.name(h), fear=u.agents[h].fear) if q in u.agents[h].avoids
                   else ko.fill(ko.MOVE_WITH, name=u.name(h)) for h in sorted(company, key=u.rank)]
        options.append({"id": str(make("go", (q,))), "label": u.name(q), "effects": effects})
    public = {"id": card_id, "kind": "move", "echo": echo, "plan": _plan(u, o, p, a, rest_labels),
              "options": options, "selected": str(a)}
    return {"id": card_id, "kind": "move", "options": [x["id"] for x in options], "rest": rest, "public": public}


def clarify_card(rest: list, rest_labels: list[str], echo: dict, card_id: str, ask: dict) -> dict:
    options = [{"id": w["id"], "label": w["label"]} for w in ask["options"]]
    public = {"id": card_id, "kind": "clarify", "echo": echo, "question": ask["question"],
              "plan": {"step": None, "rest": rest_labels}, "options": options, "selected": None}
    return {"id": card_id, "kind": "clarify", "options": [w["id"] for w in options], "resume": ask["resume"],
            "rest": rest, "public": public}
