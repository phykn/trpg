"""Whole games on the template story, pressing buttons only."""

from src.content.load import new_game
from src.rules.candidates import candidates
from src.rules.resolve import resolve
from src.world import query
from src.world.state import ActionStep

TURN_LIMIT = 60


def at(place):
    return lambda s: query.place_of(s.graph, "player") == place


def knows(k):
    return lambda s: query.knows(s.graph, "player", k)


def carries(item):
    return lambda s: item in query.carried(s.graph, "player")


def full(obstacle, boxes):
    return lambda s: s.obstacles[obstacle].value >= boxes


def play(story, seed: int, script, state=None):
    """Each turn, press the button of the first goal that does not hold yet."""
    state = state or new_game(story, game_id="g", seed=seed)
    while state.ending is None and state.turn < TURN_LIMIT:
        cands = candidates(story, state)
        button = next(b for b, done in script if not done(state))
        if button not in cands:
            button = next(b for b, done in script if not done(state) and b in cands)
        state, _ = resolve(story, state, [ActionStep(action_id=button)], cands[button].label)
    return state


KEY_PATH = [
    ("take:bread", lambda s: carries("bread")(s) or query.holder(s.graph, "bread") == "doha"),
    ("give:doha:bread", lambda s: query.holder(s.graph, "bread") == "doha"),
    ("topic:doha:topic_key_doha", knows("kn_spare_key")),
    ("act:lift_stone", carries("spare_key")),
    ("move:base", lambda s: not at("square")(s)),
    ("solve:door:0", full("door", 2)),
    ("move:top", at("top")),
    ("inspect:logbook", knows("kn_lamp_trick")),
    ("solve:lamp:0", lambda s: False),
]
FORCE_PATH = [
    ("move:base", lambda s: not at("square")(s)),
    ("solve:door:1", full("door", 2)),
    ("move:top", at("top")),
    ("solve:lamp:1", lambda s: False),
]


def test_key_path_reaches_an_ending(story):
    state = play(story, 3, KEY_PATH)
    assert state.ending in {"calm", "storm"}
    assert query.knows(state.graph, "player", "kn_spare_key")


def test_force_path_reaches_an_ending_another_way(story):
    state = play(story, 5, FORCE_PATH)
    assert state.ending in {"calm", "storm"}
    assert not query.knows(state.graph, "player", "kn_spare_key")


def test_dawdling_lets_the_storm_in(story):
    stalled = new_game(story, game_id="g", seed=7)
    for _ in range(24):
        stalled, _ = resolve(story, stalled, [ActionStep(action_id="inspect:mira")], "본다")
    assert stalled.complicated and stalled.flags["storm"] is True
    assert play(story, 7, FORCE_PATH, stalled).ending == "storm"
