import random

import pytest
from conftest import _DIGEST, REPO, SERVER, skeleton_raw
from src.onto.atoms import PLAYER, ConformError, State
from src.onto.change import Work
from src.onto.log import Delta, Event, Log
from src.onto.save import SaveError, new_game, rebuild, to_json
from src.onto.universe import build, conforms, initial
from src.onto.view import observe, record, witnesses
from src.story.load import StoryError, parse


def test_same_story_and_creation_give_the_same_start(u, creation):
    assert initial(u, creation) == initial(build(skeleton_raw(), _DIGEST), dict(creation))


def test_start_state_conforms_and_holds_defaults(u, s0):
    assert conforms(u, s0) == []
    assert s0.where(PLAYER) == "dock"
    assert s0.fill("door") == 0 and s0.fill("clock.1") == 0
    assert s0.where("clock.1") == PLAYER and s0.where("clock.2") is None
    assert s0.regards("dohae", PLAYER, "trust") == 0
    assert s0.flag("chapter") == 1 and s0.flag("gale") == 0
    assert s0.stat(PLAYER, "tinker") == 1 and s0.stat(PLAYER, "islander") is None


def test_creation_spends_the_story_total_within_its_highest_value(u):
    initial(u, {"approaches": {"force": 1, "finesse": 1, "wits": 1, "charm": 1}, "traits": ["sailor", "tinker"]})
    initial(u, {"approaches": {"force": 2, "finesse": 2, "wits": 0, "charm": 0}, "traits": ["sailor", "tinker"]})
    with pytest.raises(StoryError):
        initial(u, {"approaches": {"force": 1, "finesse": 1, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]})
    with pytest.raises(StoryError):
        initial(u, {"approaches": {"force": 3, "finesse": 1, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]})
    with pytest.raises(StoryError):
        initial(u, {"approaches": {"force": 2, "finesse": 1, "wits": 1, "charm": 0}, "traits": ["sailor"]})


def test_state_keeps_functional_atoms_unique():
    with pytest.raises(ConformError):
        State.of([("at", "a", "x"), ("at", "a", "y")])
    with pytest.raises(ConformError):
        State.of([("fill", "o", 1), ("fill", "o", 2)])


def test_random_operations_keep_conformance(u, s0):
    rng = random.Random(7)
    s = s0
    places, entities = list(u.places), ["letter", "key", "oil", "dohae", "yunseul"]
    for _ in range(400):
        w = Work(u, s)
        op = rng.randrange(8)
        if op == 0:
            w.move(PLAYER, rng.choice(places))
        elif op == 1:
            w.move(rng.choice(entities), rng.choice(places + ["dohae", PLAYER]))
        elif op == 2:
            w.set_("fill", (rng.choice(["door", "lamp", "clock.1", "t_bridge_fall"]),), rng.choice(["+3", "-2", 9, -1]))
        elif op == 3:
            w.set_("regards", ("dohae", PLAYER, "trust"), rng.choice(["+5", "-5", 2]))
        elif op == 4:
            w.tag(rng.choice([PLAYER, "door", "dock"]), rng.choice(["edge", "snag"]),
                  rng.choice(["scene", "chapter", "scar"]))
        elif op == 5:
            w.expire(rng.choice(["scene", "chapter"]))
        elif op == 6:
            w.set_("stat", (PLAYER, "wounds"), rng.choice(["+1", "+4", "-3"]))
        else:
            w.retire(rng.choice(["t_bridge_fall", "door"]))
        s = w.state()
        assert conforms(u, s) == [], op


def test_tag_skips_scars_and_stops_when_all_slots_are_scars(u, s0):
    w = Work(u, s0)
    for _ in range(3):
        w.tag(PLAYER, "snag", "scar")
    assert w.tag(PLAYER, "edge", "scene") is None
    w = Work(u, s0)
    w.tag(PLAYER, "snag", "scar")
    w.tag(PLAYER, "snag", "scene")
    w.tag(PLAYER, "edge", "chapter")
    assert w.tag(PLAYER, "edge", "scene") == 2


def test_player_moves_only_to_places(u, s0):
    with pytest.raises(ValueError):
        Work(u, s0).move(PLAYER, "dohae")


def test_failed_step_leaves_the_state_alone(u, s0):
    before = s0.atoms()
    w = Work(u, s0)
    w.set_("fill", ("door",), 2)
    with pytest.raises(ValueError):
        w.move(PLAYER, "key")
    assert s0.atoms() == before


def test_retire_sets_the_appear_flag(u, s0):
    w = Work(u, s0)
    w.retire("t_bridge_fall")
    assert w.state().flag("fired_appear.t_bridge_fall") == 1


def test_hidden_atoms_do_not_change_the_observation(u, s0):
    w = Work(u, s0)
    w.move("oil", "yard")                       # hidden, elsewhere
    w.reveal("dohae", "door.clue")              # someone else's belief
    w.set_("flag", ("gale",), 1)                # flags are never seen
    w.set_("regards", ("dohae", "yunseul", "trust"), 2)
    a, b = observe(u, s0, Log()), observe(u, w.state(), Log())
    assert a.seen == b.seen and a.facts == b.facts and a.beliefs == b.beliefs


def test_hidden_thing_shows_once_believed(u, s0):
    w = Work(u, s0)
    w.move(PLAYER, "village")
    assert "oil" not in observe(u, w.state(), Log()).seen
    w.reveal(PLAYER, "oil.hidden")
    assert "oil" in observe(u, w.state(), Log()).seen


def step(u, game, t, action, ops):
    before = game.state
    w = Work(u, before)
    for op, *args in ops:
        getattr(w, op)(*args)
    after = w.state()
    e = Event(t, action, None, "none", Delta.between(before, after), witnesses(u, before, after), ())
    record(u, game.log, before, after, e)
    game.state = after


def test_save_and_rebuild_give_the_same_state(u, creation):
    g = new_game(u, "g_x", 42, creation)
    step(u, g, 0, "go:village", [("move", PLAYER, "village"), ("set_", "stat", (PLAYER, "beats"), "+1")])
    step(u, g, 1, "look:oil", [("reveal", PLAYER, "oil.hidden")])
    data = to_json(u, g)
    again = rebuild(u, data)
    assert again.state == g.state
    assert again.log.hist == g.log.hist
    assert observe(u, again.state, again.log) == observe(u, g.state, g.log)
    assert data["log"][0]["witnesses"] == ["dohae", "player", "yunseul"]


def test_rebuild_refuses_another_story_or_schema(u, creation):
    data = to_json(u, new_game(u, "g_x", 1, creation))
    with pytest.raises(SaveError):
        rebuild(u, {**data, "schema_version": 1})
    with pytest.raises(SaveError):
        rebuild(u, {**data, "story": {**data["story"], "digest": "sha256:other"}})


def test_yaml_subset():
    assert parse("a: no\nb: on\nc: 3\nd: '3'\ne: -1\nf: '-1'\n") == {
        "a": "no", "b": "on", "c": 3, "d": "3", "e": -1, "f": "-1"}
    for bad in ("a: &x 1\nb: *x\n", "a: !!str 1\n", "a: 1\na: 2\n"):
        with pytest.raises(StoryError):
            parse(bad)


@pytest.mark.parametrize("edit, message", [
    (lambda r: r["endings"].pop("collapse"), "collapse"),
    (lambda r: r["places"].__setitem__("chat", r["places"].pop("dock")), "reserved"),
    (lambda r: r["obstacles"]["bridge"]["solutions"].pop("s_wedge"), "two or more"),
    (lambda r: r["chapters"][1]["deadline"].pop("ending"), "needs an ending"),
    (lambda r: r["triggers"]["tr_spray"]["effects"].append({"set": ["fill", "clock.1", 0]}), "clocks"),
    (lambda r: r["places"]["dock"].__setitem__("smell", "x"), "unknown field"),
])
def test_format_errors(edit, message):
    raw = skeleton_raw()
    edit(raw)
    with pytest.raises(StoryError, match=message):
        build(raw, "sha256:x")


def test_engine_code_names_no_story():
    raw = skeleton_raw()
    words = {raw["id"], raw["title"]} | set(raw["places"]) | set(raw["characters"]) | set(raw["obstacles"])
    words |= {v["name"] for sec in ("places", "characters", "things", "obstacles") for v in raw[sec].values()}
    for path in (SERVER / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        found = [w for w in words if len(w) > 2 and f'"{w}"' in text]
        assert not found, f"{path.relative_to(REPO)} names {found}"
