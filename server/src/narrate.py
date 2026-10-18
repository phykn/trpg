"""Qwen writes the scene for a saved turn; Kev checks it against the facts; failures are rewritten."""

import re
from collections.abc import AsyncIterator

from src.content.schema import Story
from src.locale import ko
from src.models.kev import KevClient
from src.models.qwen import QwenClient
from src.scene.build import build
from src.scene.render import change_line, facts
from src.world.state import GameState, TurnRecord

ATTEMPTS = 3
PREVIOUS_CHARS = 300
RECAP_LIMIT = 5
TAG_NAME = re.compile(r"^@(\S+)\s+(.{1,12})$")


class TagFilter:
    """Hide lines that start with '@' from the stream and read tag names out of them."""

    def __init__(self, tag_ids: set[str]):
        self.tag_ids = tag_ids
        self.names: dict[str, str] = {}
        self.line_start = True
        self.held = ""

    def feed(self, chunk: str) -> str:
        shown = ""
        for char in chunk:
            if self.held or (self.line_start and char == "@"):
                self.held += char
                if char == "\n":
                    self._read(self.held)
                    self.held, self.line_start = "", True
                continue
            shown += char
            self.line_start = char == "\n"
        return shown

    def finish(self) -> None:
        if self.held:
            self._read(self.held)
            self.held = ""

    def _read(self, line: str) -> None:
        match = TAG_NAME.match(line.strip())
        if match and match[1] in self.tag_ids:
            self.names[match[1]] = match[2].strip()


def turn_lines(story: Story, state: GameState, record: TurnRecord) -> list[str]:
    lines = []
    for step in record.steps:
        grade = f": {ko.GRADES[step.roll.grade]}" if step.roll else ""
        lines.append(f"- {step.label}{grade}")
        lines += [f"  - {line}" for c in step.changes if (line := change_line(story, state, c))]
    lines += [f"- {line}" for c in record.changes if (line := change_line(story, state, c))]
    return lines


def new_tags(record: TurnRecord) -> list[tuple[str, str, str]]:
    adds = [c for s in record.steps for c in s.changes] + record.changes
    return [(c.target, str(c.before), "") for c in adds if c.kind == "tag_add" and not c.after]


def messages(story: Story, style: str, state: GameState, record: TurnRecord, feedback: str = "") -> list[dict]:
    scene = build(story, state)
    blocks = ["[사실]", *facts(story, state, scene), "", "[바뀐 것]", *(turn_lines(story, state, record) or ["- 없음"])]
    previous = next((r.narration for r in reversed(state.turns) if r.n < record.n and r.narration), None)
    if previous:
        blocks += ["", "[직전 서술]", previous[-PREVIOUS_CHARS:]]
    if record.n == 0:
        blocks += ["", "[첫 장면]", ko.OPENING, story.intro]
    else:
        blocks += ["", "[플레이어 입력]", record.input]
    if record.hint:
        o = story.obstacles[record.hint]
        approach = story.labels.approaches.get(o.fits[0]) or ko.APPROACHES[o.fits[0]]
        blocks += ["", "[힌트]", ko.fill(ko.HINT, name=o.name, approach=approach)]
    if record.recap:
        notable = [n for r in state.turns for n in r.notable][-RECAP_LIMIT:]
        blocks += ["", "[되돌아보기]", ko.RECAP, *[f"- {n}" for n in notable]]
    for tag_id, kind, _ in new_tags(record):
        label = ko.TRACES.get(kind) or ko.TAG_DEFAULT.get(kind, kind)
        blocks += ["", "[이름 짓기]", ko.fill(ko.NAMING, id=tag_id, kind=label, target=scene.place.name)]
    if feedback:
        blocks += ["", "[고칠 점]", feedback]
    system = ko.NARRATOR + ("\n\n[문체]\n" + style if style else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(blocks)}]


class Narrator:
    def __init__(self, qwen: QwenClient, kev: KevClient, max_tokens: int = 500):
        self.qwen = qwen
        self.kev = kev
        self.max_tokens = max_tokens

    async def check(self, story: Story, state: GameState, record: TurnRecord, text: str) -> str:
        """Empty when the text passes, otherwise the feedback for the rewrite."""
        scene = build(story, state)
        context = "\n".join(["사실:", *facts(story, state, scene), "바뀐 것:", *turn_lines(story, state, record),
                             "서술:", text])
        answers = await self.kev.decide(context, {
            "contradicts": {"type": "noul", "instructions": ko.CHECK_CONTRADICTS,
                            "criteria": {"true": ko.YES, "false": ko.NO}},
            "invents": {"type": "noul", "instructions": ko.CHECK_INVENTS,
                        "criteria": {"true": ko.YES, "false": ko.NO}},
        })
        failed = [k for k, a in answers.items() if a.answer is True and not a.low]
        return " ".join(ko.FEEDBACK[k] for k in failed)

    async def narrate(self, story: Story, style: str, state: GameState, record: TurnRecord) -> AsyncIterator[dict]:
        """Events: delta, reset (the shown text failed the check), done, or error."""
        feedback = ""
        tag_ids = {t for t, _, _ in new_tags(record)}
        for _ in range(ATTEMPTS):
            tags = TagFilter(tag_ids)
            text = ""
            async for chunk in self.qwen.stream(messages(story, style, state, record, feedback), self.max_tokens):
                shown = tags.feed(chunk)
                if shown:
                    text += shown
                    yield {"type": "delta", "text": shown}
            tags.finish()
            text = text.strip()
            feedback = await self.check(story, state, record, text) if text else ko.FEEDBACK["contradicts"]
            if not feedback:
                yield {"type": "done", "text": text, "tags": tags.names}
                return
            yield {"type": "reset"}
        yield {"type": "error", "retry": True}
