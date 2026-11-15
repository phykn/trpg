import json
import os
import tempfile
from pathlib import Path

from .rules.state import apply_turn, start_state
from .story.load import Story, StoryFile

FORMAT = 1


class SaveError(ValueError):
    pass


def make_save(game, story, seed, made):
    head = {"game": game, "format": FORMAT, "story": story.head.name, "mark": story.mark, "seed": seed, "made": made}
    return {"head": head, "story": story.copy, "turns": [], "state": start_state(story, seed)}


def write_save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def read_save(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        head = data["head"]
        if head["format"] != FORMAT:
            raise SaveError(f"format {head['format']} has no way to open")
        story = Story(StoryFile.model_validate(data["story"]))
        if story.mark != head["mark"]:
            raise SaveError("the story copy does not match its mark")
        state = start_state(story, head["seed"])
        for turn in data["turns"]:
            state = apply_turn(story, state, turn["changes"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SaveError(f"{path.name}: {exc}") from None
    return data, story, state
