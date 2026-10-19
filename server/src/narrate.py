"""Qwen writes the scene for a saved turn; Kev checks it against the facts; failures are rewritten."""

import random
import re
from collections.abc import AsyncIterator

from src.content.schema import PLAYER, Story
from src.locale import ko
from src.models.kev import KevClient
from src.models.qwen import QwenClient
from src.scene.build import build
from src.scene.render import change_line, facts
from src.world import query
from src.world.state import Change, GameState, TurnRecord

ATTEMPTS = 3
PREVIOUS_SENTENCES = 2
RECAP_LIMIT = 5
REPEAT_CHARS = 12
TAG_NAME = re.compile(r"^@(\S+)\s+(.{1,12})$")
ECHO = re.compile(r"^\[[^\]\n]{1,20}\](\s*\([^)\n]*\))?$")  # a prompt block header such as [고칠 점]: the model echoed its input
QUOTES = "\"'“”‘’`"
REPEAT_LIMIT = 2
SENTENCE_LIMIT = 9
HAN = re.compile(r"[\u3400-\u9fff]+")
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")
PLAIN_LIMIT = 1
RULE_TALK = re.compile(r"\d+\s*/\s*\d+|주사위|판정|성공입니다|실패입니다|대가 있는 성공|진행도")
LIST_LINE = re.compile(r"^\s*[-•]\s")
SECOND_PERSON = re.compile(r"(?<![가-힣])(너의|너는|너를|너에게|네가|너와|내가|나는|나의|나를|나에게|우리는|우리가|우리의|우리를|우리에게)(?![가-힣])")
SENTENCE_END = re.compile(r"[.?!](?=[\"'”’]?(\s|$))")


class TagFilter:
    """Hide tag lines ('@id name', also quoted) and any echoed prompt from the stream; read tag names."""

    def __init__(self, tag_ids: set[str]):
        self.tag_ids = tag_ids
        self.names: dict[str, str] = {}
        self.line_start = True
        self.held = ""
        self.quotes: str | None = None
        self.echoed = False

    def feed(self, chunk: str) -> str:
        shown = ""
        for char in chunk:
            if self.echoed:
                continue
            if self.held:
                self.held += char
                if char == "\n":
                    shown += self._close(self.held)
                    self.held, self.line_start = "", True
                continue
            if self.quotes is not None:
                if char == "@":
                    self.held, self.quotes = self.quotes + char, None
                    continue
                if char in QUOTES:
                    self.quotes += char
                    continue
                shown, self.quotes = shown + self.quotes, None
            elif self.line_start and char in "@[":
                self.held = char
                continue
            elif self.line_start and char in QUOTES:
                self.quotes = char
                continue
            shown += char
            self.line_start = char == "\n"
        return shown

    def finish(self) -> str:
        """Close the stream; returns text still held back, if any."""
        rest = self._close(self.held) if self.held and not self.echoed else ""
        rest, self.held, self.quotes = rest + (self.quotes or ""), "", None
        return rest

    def _close(self, line: str) -> str:
        """A held line ends: tag lines are read, an echoed prompt header ends the text, others are shown."""
        if line.startswith("["):
            if ECHO.match(line.strip()):
                self.echoed = True
                return ""
            return line
        self._read(line)
        return ""

    def scrub(self, text: str) -> str:
        """Drop any line that still names a tag, wherever the model put the '@id'."""
        marks = [f"@{t}" for t in self.tag_ids]
        # A '- ' line is the [바뀐 것] list echoed back; a scene never uses list lines.
        return "\n".join(line for line in text.splitlines()
                         if not any(m in line for m in marks) and not LIST_LINE.match(line))

    def _read(self, line: str) -> None:
        match = TAG_NAME.match(line.strip().strip(QUOTES).strip())
        if match and match[1] in self.tag_ids:
            self.names[match[1]] = match[2].strip()


def model_line(story: Story, state: GameState, c: Change) -> str:
    """The change line plus what it means, which the bare numbers do not tell the narrator."""
    line = change_line(story, state, c)
    if c.kind == "progress":
        boxes = story.obstacles[c.target].boxes
        if c.after >= boxes:
            return f"{line} ({ko.MEANING['overcome']})"
        return f"{line} ({ko.fill(ko.MEANING['partial'], left=boxes - c.after)})"
    return f"{line} ({ko.MEANING[c.kind]})" if line and c.kind in ko.MEANING else line


def turn_lines(story: Story, state: GameState, record: TurnRecord) -> list[str]:
    lines = []
    for step in record.steps:
        grade = f": {ko.GRADES[step.roll.grade]}" if step.roll else ""
        lines.append(f"- {step.label}{grade}")
        lines += [f"  - {line}" for c in step.changes if (line := model_line(story, state, c))]
    lines += [f"- {line}" for c in record.changes if (line := model_line(story, state, c))]
    return lines


def new_tags(record: TurnRecord) -> list[tuple[str, str, str]]:
    adds = [c for s in record.steps for c in s.changes] + record.changes
    return [(c.target, str(c.before), "") for c in adds if c.kind == "tag_add" and not c.after]


def previous_text(state: GameState, record: TurnRecord) -> str | None:
    return next((r.narration for r in reversed(state.turns) if r.n < record.n and r.narration), None)


def moved(record: TurnRecord) -> bool:
    """The player changed place this turn."""
    changes = [c for s in record.steps for c in s.changes] + record.changes
    return any(c.kind == "move" and c.target == "player" for c in changes)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!\"])\s+", text) if s.strip()]


def repeated(text: str, previous: str | None) -> list[str]:
    """Whole sentences of the previous narration that the text reuses."""
    if not previous:
        return []
    return [s for s in dict.fromkeys(sentences(previous)) if len(s) >= REPEAT_CHARS and s in text]


def must_name(story: Story, record: TurnRecord) -> list[str]:
    """Items that changed hands this turn; the scene has to show them by name."""
    changes = [c for s in record.steps for c in s.changes] + record.changes
    return list(dict.fromkeys(story.name(c.target) for c in changes if c.kind in ("gain", "lose")))


def withheld(story: Story, state: GameState) -> list[str]:
    """Rewards of obstacles here that are not yet overcome; the scene must not hand them over."""
    place = query.place_of(state.graph, PLAYER)
    out = [story.name(e.target) for oid, o in story.obstacles.items()
           if o.place == place and state.obstacles[oid].value < o.boxes
           for e in o.on_full if e.kind == "give" and e.target not in query.carried(state.graph)]
    return list(dict.fromkeys(out))


def without_ending(story: Story, state: GameState, text: str) -> str:
    """The screen shows the ending's own text after the scene; drop the scene's copy of it."""
    ending = next((e for e in story.endings if e.id == state.ending), None)
    if ending is None:
        return text
    copied = {x for x in sentences(ending.text) if len(x) >= REPEAT_CHARS}
    lines = []
    for line in text.splitlines():
        if line.strip().startswith(ending.title):
            continue
        kept_ = [x for x in sentences(line) if x not in copied]
        lines.append(" ".join(kept_) if kept_ or not line.strip() else "")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def kept(story: Story, state: GameState, record: TurnRecord) -> list[str]:
    """Items the player still holds after the turn; a scene where '당신' hands one over invents a move."""
    return [story.name(i) for i in query.carried(state.graph)]


GIVING = ("건넵", "건네", "내밉", "내밀", "쥐여", "넘겨줍", "줍니다")
HANDLING = ("열었", "엽니다", "열어", "꺼내", "꺼냅", "집어", "집습", "쥐었", "쥡니다", "부수", "부숩", "찢", "빼앗", "들어 올")


def meddled(text: str, items: list[str], said: str) -> list[str]:
    """Story items '당신' handles in the scene though neither the sentence nor the turn mentions them:
    Qwen opened an oil can nobody touched. Kev could not tell these from plain scenes."""
    found = []
    for sentence in sentences(QUOTED.sub(" ", text)):
        if "당신" not in sentence or not any(h in sentence for h in HANDLING):
            continue
        found += [name for name in items if name in sentence and name not in said]
    return list(dict.fromkeys(found))


def handed(text: str, names: list[str]) -> list[str]:
    """Held items a sentence of the scene gives away."""
    found = []
    for sentence in sentences(text):
        for name in names:
            if name in sentence and any(g in sentence for g in GIVING):
                found.append(name)
    return list(dict.fromkeys(found))


def stem(name: str) -> str:
    """A name without its last syllable when long enough, so '정정 명령서' also catches '정정 명령'."""
    return name[:-1] if len(name.replace(" ", "")) >= 4 else name


def form_feedback(text: str, previous: str | None, must: list[str] = (), unearned: list[str] = (),
                  held: list[str] = ()) -> str:
    """Problems a rule can see without a model, as one feedback string for the rewrite."""
    return " ".join(form_problems(text, previous, must, unearned, held))


def form_problems(text: str, previous: str | None, must: list[str] = (), unearned: list[str] = (),
                  held: list[str] = (), items: list[str] = (), said: str = "", alone: bool = False,
                  no_she: bool = False) -> list[str]:
    """Problems a rule can see without a model: foreign script, plain speech, length, copies, missing items."""
    problems = []
    if no_she and "그녀" in QUOTED.sub(" ", text):
        problems.append(ko.FEEDBACK["pronoun"])
    if alone and "동행" in QUOTED.sub(" ", text):
        problems.append(ko.FEEDBACK["alone"])
    touched = meddled(text, list(items), said) if said else []
    if touched:
        problems.append(ko.fill(ko.FEEDBACK["meddled"], names=", ".join(touched)))
    if "\ufffd" in text:
        problems.append(ko.FEEDBACK["broken"])
    if RULE_TALK.search(QUOTED.sub(" ", text)):
        problems.append(ko.FEEDBACK["rules"])
    if SECOND_PERSON.search(QUOTED.sub(" ", text)):
        problems.append(ko.FEEDBACK["you"])
    given = handed(text, list(held))
    if given:
        problems.append(ko.fill(ko.FEEDBACK["handed"], names=", ".join(given)))
    early = [name for name in unearned if stem(name) in text]
    if early:
        problems.append(ko.fill(ko.FEEDBACK["early"], names=", ".join(early)))
    # Any word of the name will do: demanding "외상 유예 쪽지" when the scene said "쪽지" spent the rewrites
    # and left the last attempt in plain speech.
    missing = [name for name in must if not any(w in text for w in name.split() if len(w) >= 2) and name not in text]
    if missing:
        problems.append(ko.fill(ko.FEEDBACK["missing"], names=", ".join(missing)))
    if HAN.search(text):
        problems.append(ko.FEEDBACK["foreign"])
    told = [x.strip() for x in re.split(r"(?<=[.?!])\s+", QUOTED.sub(" ", text)) if x.strip()]
    if sum(x.rstrip(".!").endswith("다") and not x.rstrip(".!").endswith("니다") for x in told) >= PLAIN_LIMIT:
        problems.append(ko.FEEDBACK["plain"])
    if len(SENTENCE_END.findall(text)) > SENTENCE_LIMIT:
        problems.append(ko.FEEDBACK["long"])
    own = [x for x in sentences(text) if len(x) >= REPEAT_CHARS]
    doubled = list(dict.fromkeys(x for x in own if own.count(x) > 1))
    if doubled:
        problems.append(ko.fill(ko.FEEDBACK["doubled"], sentences=" / ".join(doubled)))
    copied = repeated(text, previous)
    if len(copied) >= REPEAT_LIMIT:
        problems.append(ko.fill(ko.FEEDBACK["repeats"], sentences=" / ".join(copied)))
    return problems


def messages(story: Story, style: str, state: GameState, record: TurnRecord, feedback: str = "") -> list[dict]:
    scene = build(story, state)
    blocks = ["[사실]", *facts(story, state, scene), "", "[바뀐 것]", *(turn_lines(story, state, record) or ["- 없음"])]
    previous = previous_text(state, record)
    if previous and not moved(record):
        # Only where the last scene stopped: given the whole text, Qwen copied it as the new scene.
        # After a move the old place's last lines were put in the mouths of the new place's people.
        blocks += ["", ko.PREVIOUS, " ".join(sentences(previous)[-PREVIOUS_SENTENCES:])]
    changes = [c for st in record.steps for c in st.changes] + record.changes
    if record.n == 0:
        blocks += ["", "[첫 장면]", ko.OPENING, story.intro]
    elif any(c.kind == "chapter" for c in changes) and not record.steps:
        # A growth pick is not something '당신' does in the scene: the new chapter opens on its own.
        blocks += ["", "[새 장]", ko.CHAPTER_OPENING]
    else:
        blocks += ["", "[플레이어 입력]", record.input]
    ending = next((e for e in story.endings if e.id == state.ending), None)
    if ending is not None:
        # The client shows the ending text after this scene; the scene leads into it and asks nothing.
        blocks += ["", "[결말]", ko.ENDING_SCENE, f"{ending.title}: {ending.text}"]
    if record.hint:
        o = story.obstacles[record.hint]
        approach = story.labels.approaches.get(o.fits[0]) or ko.APPROACHES[o.fits[0]]
        blocks += ["", "[힌트]", ko.fill(ko.HINT, name=o.name, approach=approach)]
    if record.recap:
        notable = [n for r in state.turns for n in r.notable][-RECAP_LIMIT:]
        blocks += ["", "[되돌아보기]", ko.RECAP, *[f"- {n}" for n in notable]]
    for tag_id, kind, _ in [] if ending is not None else new_tags(record):
        label = ko.TRACES.get(kind) or ko.TAG_DEFAULT.get(kind, kind)
        blocks += ["", "[이름 짓기]", ko.fill(ko.NAMING, id=tag_id, kind=label)]
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
        previous = previous_text(state, record)
        must = must_name(story, record)
        unearned = withheld(story, state)
        held = kept(story, state, record)
        items = [i.name for i in story.items.values()]
        alone = not query.companions(state.graph)
        # Everyone here is '그' in the story: '그녀' is a drift (the inspector was both in one game).
        present = [story.characters[p.id] for p in build(story, state).people]
        no_she = bool(present) and all(c.pronoun == "그" for c in present)
        said = "\n".join([record.input, *(st.label for st in record.steps),
                          *(change_line(story, state, c) for st in record.steps for c in st.changes),
                          *(change_line(story, state, c) for c in record.changes)])
        drafts: list[tuple[int, int, str, dict[str, str]]] = []
        for attempt in range(1, ATTEMPTS + 1):
            tags = TagFilter(tag_ids)
            text = ""
            seed = random.randrange(2**31)
            async for chunk in self.qwen.stream(messages(story, style, state, record, feedback), self.max_tokens, seed):
                shown = tags.feed(chunk)
                if shown:
                    text += shown
                    yield {"type": "delta", "text": shown}
            text = ko.polite(tags.scrub(text + tags.finish()).strip(), QUOTED)
            text = without_ending(story, state, text)
            problems = form_problems(text, previous, must, unearned, held, items, said, alone, no_she) if text else []
            if text and (problems or attempt == ATTEMPTS):
                # Only drafts Kev has not rejected: form failures never reached the check.
                drafts.append((len(problems), attempt, text, tags.names))
            if not text:
                feedback = ko.FEEDBACK["contradicts"]
            elif problems and attempt < ATTEMPTS:
                feedback = " ".join(problems)
            else:
                # A clean draft goes to Kev as it is. Out of attempts, keep the draft with the fewest form
                # problems (the last one wins ties); either way stray foreign script is dropped.
                if attempt == ATTEMPTS:
                    _, _, text, tags.names = min(drafts, key=lambda d: (d[0], -d[1]))
                text = re.sub(r" {2,}", " ", HAN.sub("", text))
                feedback = await self.check(story, state, record, text)
            if not feedback:
                yield {"type": "done", "text": text, "tags": tags.names}
                return
            yield {"type": "reset"}
        yield {"type": "error", "retry": True}
