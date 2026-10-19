from __future__ import annotations

from .locale import ko
from .onto.atoms import PLAYER
from .onto.view import Obs
from .rules.acts import Action
from .rules.candidates import space
from .rules.roll import preview
from .view import action_label, chips, effect_names, rely_label, tag_name

# A card is a function of (Vₜ, plan) and makes no event (engine.md 4).


def rely_options(u, o: Obs, a: Action) -> list[str]:
    for slot in space(u, o):
        if slot.schema == a.schema and slot.intent == a.intent:
            return [v for v in slot.values("rely") if v is not None]
    return []


def preview_json(u, o: Obs, p: dict, a: Action) -> dict:
    pv = preview(u, o, a)
    f, m, s = pv.odds
    clock = None
    if pv.clock:
        clock = {"id": pv.clock["id"], "name": u.name(pv.clock["id"]), "boxes": pv.clock["boxes"],
                 "fill": pv.clock["fill"]}
    return {
        "risk": pv.risk, "mods": chips(u, p, pv.mods.chips()), "z": pv.z,
        "odds": {"fail": round(f, 3), "mixed": round(m, 3), "success": round(s, 3)},
        "stakes": {res: {"clock": pv.clock[res] if pv.clock else 0, "weight": pv.stakes[res]["weight"]}
                   for res in ("mixed", "fail")},
        "clock": clock, "gain": _gain(u, p, pv.gain),
    }


def _gain(u, p: dict, g: dict) -> dict:
    if g["kind"] == "fill":
        return {"kind": "fill", "boxes": g["boxes"], "fit": g["fit"]}
    if g["kind"] == "tag":
        return {"kind": "tag", "remove": tag_name(u, p, g["remove"]) if g["remove"] else None}
    if g["kind"] == "favor":
        return {"kind": "favor", "effects": effect_names(u, g["effects"])}
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
              selected: str | None = None) -> dict:
    base = a.with_(rely=None)
    options = []
    for v in rely_options(u, o, base):
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
    option = {"id": str(a), "label": action_label(u, o, p, a), "effects": effect_names(u, effects)}
    public = {"id": card_id, "kind": "confirm", "echo": echo, "plan": _plan(u, o, p, a, rest_labels),
              "options": [option], "selected": None}
    return {"id": card_id, "kind": "confirm", "options": [str(a)], "rest": rest, "public": public}


def clarify_card(rest: list, rest_labels: list[str], echo: dict, card_id: str, ask: dict) -> dict:
    options = [{"id": w["id"], "label": w["label"]} for w in ask["options"]]
    public = {"id": card_id, "kind": "clarify", "echo": echo, "question": ask["question"],
              "plan": {"step": None, "rest": rest_labels}, "options": options, "selected": None}
    return {"id": card_id, "kind": "clarify", "options": [w["id"] for w in options], "resume": ask["resume"],
            "rest": rest, "public": public}
