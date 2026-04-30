"""Player identity view — narrate / combat_narrate prompt input.

Mirrors target_view's deep-dump shape but for the active player. Surfaces
race, appearance, description, gender — the fields surroundings.entities[0]
flattens away — so prose voice can reflect "you are a goblin" instead of
defaulting to a human-shaped narrator. Stats / hp / equipment stay out:
narrate prompt forbids numeric leakage and equipment is already in
surroundings.
"""
from ..domain.state import GameState


def _omit_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def build_player_view(state: GameState) -> dict:
    player = state.characters[state.player_id]
    race = state.races.get(player.race_id)
    race_payload = (
        _omit_none({"name": race.name, "description": race.description or None})
        if race is not None
        else None
    )
    return _omit_none(
        {
            "name": player.name,
            "race": race_payload,
            "appearance": player.appearance or None,
            "description": player.description or None,
            "gender": player.gender if player.gender != "none" else None,
        }
    )
