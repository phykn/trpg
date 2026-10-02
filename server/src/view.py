"""Player-visible projection of an adventure; hidden graph facts stay server-side."""

from pydantic import BaseModel, Field

from src.game.dice import compute_grade
from src.game.engine import can_choose, list_choices, matches_condition, required_roll
from src.game.graph.query import (
    characters_at,
    edges_from,
    inventory_of,
    known_skills_of,
    location_of,
)
from src.game.models import GameState, Story, chapter
from src.locale.ko import STATS, text


class NamedText(BaseModel):
    id: str
    name: str
    text: str = ""


class ActionView(BaseModel):
    id: str
    target: str
    label: str
    description: str
    cost: str
    enabled: bool
    blocked: str = ""
    confirm: bool = False
    group: str = "story"


class CombatView(BaseModel):
    opponent: str
    player_hearts: int
    enemy_hearts: int
    understanding: int
    round: int


class EndingView(NamedText):
    epilogue: list[str] = Field(default_factory=list)


class GameView(BaseModel):
    game_id: str
    revision: int
    title: str
    player_name: str
    role: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    gold: int
    scene: NamedText
    characters: list[NamedText]
    objective: str
    clock: str
    remaining: int
    alert: str
    actions: list[ActionView]
    knowledge: list[NamedText]
    inventory: list[NamedText]
    skills: list[NamedText]
    journal: list[dict[str, str | int]]
    combat: CombatView | None = None
    ending: EndingView | None = None


def game_view(story: Story, state: GameState) -> GameView:
    graph = state.graph
    player = graph.nodes["player"].properties
    props = chapter(state)
    place = location_of(graph, "player")

    def named(node_id):
        desc = story.descriptions[node_id]
        reaction = next(
            (
                reaction
                for reaction in story.reactions
                if reaction.target == node_id
                and all(
                    matches_condition(state, condition) for condition in reaction.when
                )
            ),
            None,
        )
        return NamedText(
            id=node_id, name=desc.name, text=reaction.text if reaction else desc.text
        )

    actions = []
    for option in list_choices(story, state):
        can_use = can_choose(state, option)
        name = story.descriptions[option.target].name
        label = text(option.label, name=name) if option.system else option.label
        description = (
            text(option.description, mp=option.mp)
            if option.system and option.description
            else option.description
        )
        costs = [text("time", ticks=option.ticks)]
        if option.gold:
            costs.append(text("gold", gold=option.gold))
        if option.mp:
            costs.append(text("mp", mp=option.mp))
        roll = required_roll(state, option)
        if roll is not None:
            wins = sum(
                compute_grade(dice, dice, roll) in {"success", "critical_success"}
                if option.check
                else dice >= roll
                for dice in range(1, 21)
            )
            costs.append(
                text(
                    "chance",
                    chance=wins * 5,
                    stat=STATS[option.check.stat]
                    if option.check
                    else text("combat_stat"),
                )
            )
        elif option.enemy is None and can_use:
            costs.append(text("certain"))
        group = "story"
        for prefix, category in (
            ("move:", "move"),
            ("combat.", "combat"),
            ("item:", "item"),
            ("growth:", "growth"),
        ):
            if option.id.startswith(prefix):
                group = category
        actions.append(
            ActionView(
                id=option.id,
                target=name,
                label=label,
                description=description,
                cost=" · ".join(costs),
                enabled=can_use,
                blocked=(
                    text("no_gold")
                    if player["gold"] < option.gold
                    else text("no_mp")
                    if player["mp"] < option.mp
                    else option.blocked
                )
                if not can_use
                else "",
                confirm=option.confirm,
                group=group,
            )
        )
    journal = []
    for entry in state.journal:
        values = dict(entry.values)
        if entry.key == "arrive":
            values["text"] = values.pop("text_value")
        if entry.key == "roll":
            values["result"] = text(values["result"])
        journal.append(
            {
                "turn": entry.turn,
                "kind": entry.kind,
                "text": text(entry.key, **values) if entry.key else entry.text,
            }
        )
    ending = None
    if props.get("ending"):
        desc = story.endings[props["ending"]]
        epilogue = []
        if props["violence"]:
            epilogue.append(
                text(
                    "epilogue_violent" if props["rescued"] else "epilogue_violent_alone"
                )
            )
        elif props.get("merciful"):
            epilogue.append(text("epilogue_merciful"))
        if props.get("owed") and props["ledger_to"] != "keeper":
            epilogue.append(text("epilogue_debt"))
        ending = EndingView(
            id=props["ending"], name=desc.name, text=desc.text, epilogue=epilogue
        )
    battle = state.combat
    return GameView(
        game_id=state.game_id,
        revision=state.revision,
        title=story.title,
        player_name=player["name"],
        role=story.roles[state.role].name,
        hp=player["hp"],
        max_hp=player["max_hp"],
        mp=player["mp"],
        max_mp=player["max_mp"],
        gold=player["gold"],
        scene=named(place),
        characters=[
            named(node_id)
            for node_id in characters_at(graph, place)
            if node_id != "player"
            and graph.nodes[node_id].properties.get("alive", True)
        ],
        objective=text(
            "goal_ended" if ending else "goal_rescued" if props["rescued"] else "goal"
        ),
        remaining=max(0, story.deadline - props["elapsed_ticks"]),
        clock=text("clock", remaining=max(0, story.deadline - props["elapsed_ticks"])),
        alert=text("alert", alert=props["alert"]),
        actions=actions,
        knowledge=[
            named(edge.to_node_id)
            for edge in edges_from(graph, "player", "has_knowledge")
        ],
        inventory=[named(node_id) for node_id in inventory_of(graph, "player")],
        skills=[named(edge.to_node_id) for edge in known_skills_of(graph, "player")],
        journal=journal,
        combat=CombatView(
            opponent=story.descriptions[battle.active_enemy_id].name,
            player_hearts=battle.player_hearts,
            enemy_hearts=battle.enemy_hearts,
            understanding=battle.enemy_pressure,
            round=battle.round,
        )
        if battle
        else None,
        ending=ending,
    )
