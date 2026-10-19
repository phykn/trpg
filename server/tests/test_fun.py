"""Fun metrics read what the service records (fun.md 4)."""

from src.fun import measure
from test_service import STORIES, cmd, new, service


async def settle(svc, gid, view, rid):
    """Pays any cost due, so the next command is free."""
    while view["due"]:
        out = await cmd(svc, gid, view, f"{rid}-pay", action=view["due"][0]["action"])
        view = out["view"]
    return view


async def test_metrics_read_sentence_outcomes_card_origins_and_closed_cards(tmp_path):
    svc = service(tmp_path, {"ask": ["talk:yunseul:t_wall"], "back": ["go:dock"]})
    gid, view = await new(svc)

    out = await cmd(svc, gid, view, "r1", text="ask")                       # a sentence opens a roll card
    card = out["view"]["card"]
    assert card["kind"] == "roll" and len(card["options"]) > 1
    rely = next(o["id"] for o in card["options"] if ";rely=" in o["id"])
    out = await cmd(svc, gid, out["view"], "r2", card=card["id"], pick=rely)
    view = await settle(svc, gid, out["view"], "r2")

    out = await cmd(svc, gid, view, "r3", action="go:village")               # a button
    out = await cmd(svc, gid, out["view"], "r4", action="talk:dohae:t_oil")  # a roll card, then closed
    out = await cmd(svc, gid, out["view"], "r5", card=out["view"]["card"]["id"], cancel=True)
    await cmd(svc, gid, out["view"], "r6", text="back")

    m = measure(sorted(tmp_path.glob("*.json")), STORIES, now=0)
    assert m["games"] == 1 and m["F1"]["outcomes"] == {"accepted": 2}
    assert m["F2"]["steps"] == {"text": 2, "button": 1}
    assert m["F13"]["rolls"] == 1 and m["F13"]["relied"] == 1.0
    assert m["F14"] == {"value": 0.5, "roll_cards": 2, "closed": 1}
    assert m["F4"]["rolls"] == 1 and m["F11"]["chapter1"] == 0.0
