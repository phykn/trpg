import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from .rules.act import act
from .save import SaveError, make_save, read_save, write_save


class Missing(LookupError):
    pass


class Conflict(ValueError):
    pass


class Broken(ValueError):
    pass


class GameService:
    def __init__(self, stories, save_dir):
        self.stories = stories
        self.save_dir = Path(save_dir)
        self.games = {}

    def create(self, request_id, story_name):
        digest = hashlib.sha256(request_id.encode()).hexdigest()
        game = digest[:16]
        if (self.save_dir / f"{game}.json").exists():
            if self.load(game)[0]["head"]["story"] != story_name:
                raise Conflict("this request opened a game of another story")
            return game
        if story_name not in self.stories:
            raise Missing(f"no story {story_name!r}")
        story = self.stories[story_name]
        data = make_save(game, story, int(digest[16:24], 16), datetime.now(UTC).isoformat(timespec="seconds"))
        write_save(self.save_dir / f"{game}.json", data)
        self.games[game] = (data, story, data["state"])
        return game

    def load(self, game):
        if game not in self.games:
            path = self.save_dir / f"{game}.json"
            if not re.fullmatch(r"[0-9a-f]{16}", game) or not path.is_file():
                raise Missing(f"no game {game!r}")
            try:
                self.games[game] = read_save(path)
            except SaveError as exc:
                raise Broken(str(exc)) from None
        return self.games[game]

    def command(self, game, receipt, action, heard=None):
        data, story, state = self.load(game)
        for turn in data["turns"]:
            if turn["receipt"] == receipt:
                if turn["action"] != action:
                    raise Conflict("this receipt carried another action")
                return turn
        result = act(story, state, action, heard)
        turn = {"turn": result["state"]["turn"], "receipt": receipt, "action": action, "heard": heard,
                "dice": result["dice"], "changes": result["changes"], "happened": result["happened"],
                "talk": result["talk"], "text": None}
        data = {**data, "turns": data["turns"] + [turn], "state": result["state"]}
        write_save(self.save_dir / f"{game}.json", data)
        self.games[game] = (data, story, result["state"])
        return turn
