from __future__ import annotations

from .locale import ko
from .onto.atoms import PLAYER
from .onto.view import Obs
from .rules.acts import Action, make, parse
from .rules.candidates import admits, avoided, space
from .rules.roll import gain, preview
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


def buys_box(u, o: Obs, a: Action) -> bool:
    return a.intent[0] in u.obstacles and gain(u, o, a)["forced"] > 0


def _gain(u, p: dict, g: dict) -> dict:
    if g["kind"] == "fill":
        return {"kind": "fill", "boxes": g["boxes"], "fit": g["fit"], "forced": g["forced"]}
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
    # Forcing is a toggle on the card: it costs a risk step for one more box, so the player opts in seeing both;
    # where it would buy nothing it is offered only if the sentence forced.
    strains = [base]
    if a.schema == "try" and a.intent[0] != PLAYER:
        forced = base.with_(strain="forced")
        if a.get("strain") == "forced" or buys_box(u, o, forced):
            strains = [base.with_(strain=None), forced]
    options = []
    for sv in (x for x in strains if admits(u, o, x)):
        forced = sv.get("strain") == "forced"
        for v in rely_options(u, o, sv) if relies is None else relies:
            av = sv.with_(rely=v)
            kind = v.split(":", 1)[0]
            options.append({"id": str(av), "label": rely_label(u, p, o.facts, v), "consumed": kind in ko.CONSUMED,
                            "note": ko.CONSUMED.get(kind), "rely": v, "forced": forced,
                            "preview": preview_json(u, o, p, av)})
        options.append({"id": str(sv), "label": ko.NO_RELY, "consumed": False, "note": None, "rely": None,
                        "forced": forced, "preview": preview_json(u, o, p, sv)})
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
    names = list(ko.CUT_EFFECTS[a.intent[0]]) if a.schema == "cut" else effect_names(u, effects)
    options = [{"id": str(a), "label": action_label(u, o, p, a), "effects": names}]
    if a.schema == "give":
        # a sentence that only showed a thing was read as giving it away (qa_test/runs/play-4-talker 7)
        show = make("show", a.intent)
        options.append({"id": str(show), "label": action_label(u, o, p, show), "effects": []})
    public = {"id": card_id, "kind": "confirm", "echo": echo, "plan": _plan(u, o, p, a, rest_labels),
              "options": options, "selected": None}
    return {"id": card_id, "kind": "confirm", "options": [x["id"] for x in options], "rest": rest, "public": public}


def _action(x: str) -> Action | None:
    try:
        return parse(x)
    except ValueError:
        return None


def ways(u, o: Obs) -> list[str]:
    return [slot.intent[0] for slot in space(u, o) if slot.schema == "go"]


def left_behind(u, o: Obs, q: str) -> bool:
    return any(g == PLAYER and q in avoided(u, o.facts, o.hist, h) for h, g in o.facts.rows("follows"))


def joiners(u, o: Obs) -> list[str]:
    """People here who could be asked to come along."""
    return [h for h in sorted(o.seen, key=u.rank)
            if h in u.agents and admits(u, o, make("talk", (h, "come"))) and not o.facts.has("follows", h, PLAYER)]


def move_card(u, o: Obs, p: dict, a: Action, rest: list, rest_labels: list[str], echo: dict, card_id: str,
              only: bool = False, asked: tuple[str, ...] = ()) -> dict:
    """The sentence's way first, then the other ways unless the sentence named it alone; each says who comes along
    (engine.md 4.4). The sentence's way can also be taken with someone it names asked first: "윤슬과 같이 마을로
    간다" went alone, the second half dropped."""
    q0 = a.intent[0]
    out = [q0] if only else [q0, *(q for q in ways(u, o) if q != q0)]
    company = [h for h, g in o.facts.rows("follows") if g == PLAYER]
    options, plans, selected = [], {}, str(a)
    for q in out:
        effects = [ko.fill(ko.MOVE_LEFT, name=u.name(h), fear=u.agents[h].fear) if q in avoided(u, o.facts, o.hist, h)
                   else ko.fill(ko.MOVE_WITH, name=u.name(h)) for h in sorted(company, key=u.rank)]
        options.append({"id": str(make("go", (q,))), "label": u.name(q), "effects": effects})
        if q != q0:
            continue
        for h in asked:
            if q in avoided(u, o.facts, o.hist, h):
                continue
            come, go = make("talk", (h, "come")), make("go", (q,))
            oid = f"{come}+{go}"
            options.append({"id": oid, "label": u.name(q), "with": u.name(h),
                            "effects": [*effects, ko.fill(ko.MOVE_ASK, name=u.name(h))]})
            plans[oid] = [{"action": str(come)}, {"action": str(go), "accepted": True}]
            if selected == str(a):
                selected = oid
    public = {"id": card_id, "kind": "move", "echo": echo, "plan": _plan(u, o, p, a, rest_labels),
              "options": options, "selected": selected}
    return {"id": card_id, "kind": "move", "options": [x["id"] for x in options], "plans": plans, "rest": rest,
            "public": public}


def clarify_card(u, o: Obs, rest: list, rest_labels: list[str], echo: dict, card_id: str, ask: dict) -> dict:
    """An option that is a roll on an obstacle carries its target number and risk: the two ways round the dog were
    labels without odds, so the fast dangerous way and the slow safe one were never compared."""
    options = []
    for w in ask["options"]:
        opt = {"id": w["id"], "label": w["label"]}
        a = _action(w["id"])
        if a is not None and a.schema == "try" and a.intent[0] in u.obstacles:
            pv = preview(u, o, a)
            opt |= {"dc": pv.dc, "risk": pv.risk}
        options.append(opt)
    public = {"id": card_id, "kind": "clarify", "echo": echo, "question": ask["question"],
              "plan": {"step": None, "rest": rest_labels}, "options": options, "selected": None}
    return {"id": card_id, "kind": "clarify", "options": [w["id"] for w in options], "resume": ask["resume"],
            "rest": rest, "public": public}
