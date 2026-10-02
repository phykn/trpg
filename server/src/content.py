"""Load and validate an authored adventure before it reaches the runtime."""

from pathlib import Path

from src.game.models import Story


def load_story(path: Path) -> Story:
    story = Story.model_validate_json(path.read_text(encoding="utf-8"))
    ids = set(story.graph.nodes)
    if (
        not {"player", "chapter", "square", "guard", "sailor", "bandage", "guard_fear"}
        <= ids
    ):
        raise ValueError("adventure is missing required actors or locations")
    if ids != set(story.descriptions):
        raise ValueError("every graph node must have exactly one description")
    choice_ids = [choice.id for choice in story.choices]
    if len(choice_ids) != len(set(choice_ids)):
        raise ValueError("duplicate choice id")
    if any(
        choice_id.startswith(("move:", "combat.", "item:", "growth:"))
        for choice_id in choice_ids
    ):
        raise ValueError("choice uses a reserved id prefix")
    for choice in story.choices:
        if choice.system:
            raise ValueError("authored choices cannot dispatch system commands")
        if choice.target not in ids or (choice.enemy and choice.enemy not in ids):
            raise ValueError(f"unknown choice target: {choice.id}")
        _validate_conditions(story, [*choice.show, *choice.requires])
        if choice.requires and not choice.blocked:
            raise ValueError("conditional choice requires a blocked explanation")
        for result in [choice.success, choice.failure]:
            if result:
                _validate_effects(story, result.effects)
    milestone_ids = [event.id for event in story.milestones]
    if len(set(milestone_ids)) != len(milestone_ids):
        raise ValueError("duplicate milestone id")
    for event in story.milestones:
        _validate_effects(story, event.result.effects)
    for reaction in story.reactions:
        if reaction.target not in ids:
            raise ValueError("unknown reaction target")
        _validate_conditions(story, reaction.when)
    if not story.roles:
        raise ValueError("adventure requires a role")
    for role in story.roles.values():
        if role.skill not in ids or (role.item and role.item not in ids):
            raise ValueError("unknown role item or skill")
        skill = story.graph.nodes[role.skill]
        if skill.type != "skill" or skill.properties.get("action") not in {
            "attack",
            "defend",
            "flee",
        }:
            raise ValueError("role must grant a supported combat skill")
        if (
            type(skill.properties.get("mp_cost")) is not int
            or skill.properties["mp_cost"] < 0
        ):
            raise ValueError("skill requires a nonnegative resource cost")
        if role.item and story.graph.nodes[role.item].type != "item":
            raise ValueError("role item must refer to an item")
    for ending in ("public", "bargain", "quiet", "departed", "stranded"):
        if ending not in story.endings:
            raise ValueError(f"missing ending: {ending}")
    return story


def _validate_effects(story, effects):
    for effect in effects:
        if (
            effect.target not in story.graph.nodes
            or effect.source not in story.graph.nodes
        ):
            raise ValueError("unknown effect reference")
        if effect.kind in {"set", "add", "relation"} and not effect.key:
            raise ValueError("property effect requires a key")
        if effect.kind == "add" and type(effect.value) is not int:
            raise ValueError("add effect requires an integer")
        expected_type = {
            "learn": "knowledge",
            "give": "item",
            "move": "location",
            "companion": "character",
            "relation": "character",
        }.get(effect.kind)
        if expected_type and story.graph.nodes[effect.target].type != expected_type:
            raise ValueError(f"{effect.kind} effect requires a {expected_type} target")
        if expected_type and story.graph.nodes[effect.source].type != "character":
            raise ValueError("relational effect requires a character source")
        if (
            effect.kind == "add"
            and type(story.graph.nodes[effect.target].properties.get(effect.key))
            is not int
        ):
            raise ValueError("add effect requires an existing integer property")


def _validate_conditions(story, conditions):
    for condition in conditions:
        if (
            condition.target not in story.graph.nodes
            or condition.source not in story.graph.nodes
        ):
            raise ValueError("unknown condition reference")
        if condition.kind in {"property", "relation"} and not condition.key:
            raise ValueError("property condition requires a key")
        if (
            condition.kind == "property"
            and condition.key not in story.graph.nodes[condition.target].properties
        ):
            raise ValueError("condition requires an existing property")
