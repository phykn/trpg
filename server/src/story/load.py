import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationError,
    model_validator,
)

STANCE_NEEDS = {
    "숨기지 않는다": {"truth"},
    "꺼린다": {"opened", "wants", "hint"},
    "거짓말한다": {"lie", "broken", "breaks"},
}
CASE = "사건"   # the line the opener's telling of the case leaves (game/04 5절)
ADDRESS_PARTS = {"곳": 1, "사람": 1, "볼 것": 1, "말": 3, "거짓말": 2, "꺼림": 2, "잠김": 1}


class StoryError(ValueError):
    pass


def to_bool(value):
    if value not in ("예", "아니오"):
        raise ValueError("write 예 or 아니오")
    return value == "예"


def to_minutes(value):
    # YAML 1.1 reads an unquoted 20:00 as the base-60 number 1200, which is already the minutes.
    if isinstance(value, str):
        hours, _, mins = value.partition(":")
        return int(hours) * 60 + int(mins)
    return value


YesNo = Annotated[bool, BeforeValidator(to_bool), PlainSerializer(lambda value: "예" if value else "아니오")]


# A save keeps the story as these models dump it and checks it by the dump's hash, so the fields keep their order.
class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Branch(Shape):
    text: str = Field(alias="말")
    shows: str | None = Field(None, alias="보여 주는 사실")
    tells: list[str] = Field([], alias="알리는 것")

    @model_validator(mode="before")
    @classmethod
    def from_text(cls, value):
        return {"말": value} if isinstance(value, str) else value


class Topic(Shape):
    stance: Literal["숨기지 않는다", "꺼린다", "거짓말한다"] = Field(alias="자세")
    truth: Branch | None = Field(None, alias="참말")
    opened: Branch | None = Field(None, alias="풀린 뒤")
    lie: Branch | None = Field(None, alias="거짓말")
    broken: Branch | None = Field(None, alias="깨진 뒤")
    wants: str | None = Field(None, alias="바라는 것")
    hint: str | None = Field(None, alias="실마리")
    breaks: str | list[str] | None = Field(None, alias="깨는 사실")
    asks: list[str] = Field([], alias="묻는 말")
    cond: str | None = Field(None, alias="나오는 조건")
    unlock: str | None = Field(None, alias="풀리는 인상")
    unlock_count: int | None = Field(None, alias="풀리는 횟수", ge=1)

    @model_validator(mode="after")
    def fit_stance(self):
        given = {k for k in ("truth", "opened", "lie", "broken", "wants", "hint", "breaks") if getattr(self, k)}
        needs = STANCE_NEEDS[self.stance]
        if given != needs:
            names = sorted(Topic.model_fields[k].alias for k in needs)
            raise ValueError(f"자세 {self.stance} takes exactly {', '.join(names)}")
        if self.lie and self.lie.shows:
            raise ValueError("거짓말 shows no fact")
        if self.unlock and self.stance == "숨기지 않는다":
            raise ValueError("풀리는 인상 is for 꺼린다 or 거짓말한다")
        if self.unlock_count and not self.unlock:
            raise ValueError("풀리는 횟수 needs 풀리는 인상")
        return self

    def list_branches(self):
        pairs = (("참말", self.truth), ("풀린 뒤", self.opened), ("거짓말", self.lie), ("깨진 뒤", self.broken))
        return {name: branch for name, branch in pairs if branch}

    def list_breaks(self):
        return [self.breaks] if isinstance(self.breaks, str) else list(self.breaks or [])


class Attitude(Shape):
    trust: int = Field(0, alias="믿음", ge=-1, le=1)
    fear: int = Field(0, alias="두려움", ge=-1, le=1)


class Person(Shape):
    bio: str = Field(alias="신상")
    mbti: str | None = Field(None, alias="MBTI", pattern=r"^[EI][SN][TF][JP]$")   # the check asks for it, like 소개
    intro: str | None = Field(None, alias="소개")   # the check asks for it; saves made before it have none
    place: str = Field(alias="있는 곳")
    attitude: Attitude = Field(Attitude(), alias="처음 태도")
    topics: dict[str, Topic] = Field({}, alias="화제")
    display: str | None = Field(None, alias="화면 이름")
    impressions: dict[str, str] = Field({}, alias="인상")   # the person's own, beside the common ones
    close: list[str] = Field([], alias="가까운 사람")
    doing: dict[int, str] = Field({}, alias="하는 일")   # from which spent cell each holds (game/08 2절)


class Lock(Shape):
    weak: str = Field(alias="약점")
    hard: YesNo = Field(False, alias="단단한가")
    owner: str | None = Field(None, alias="주인")
    hint: str = Field(alias="실마리")
    contents: list[str] = Field(alias="안에 든 것", min_length=1)


class Thing(Shape):
    place: str | None = Field(None, alias="곳")
    text: str | None = Field(None, alias="줄")
    item: YesNo = Field(False, alias="물건인가")
    props: list[str] = Field([], alias="성질")
    intro: str | None = Field(None, alias="소개")
    shows: str | None = Field(None, alias="보여 주는 사실")
    tells: list[str] = Field([], alias="알리는 것")
    lock: Lock | None = Field(None, alias="잠김")
    cond: str | None = Field(None, alias="나오는 조건")
    display: str | None = Field(None, alias="화면 이름")

    @model_validator(mode="after")
    def fit_kind(self):
        if not self.item and not self.text:
            raise ValueError("줄 is required unless 물건인가 is 예")
        if (self.props or self.intro) and not self.item:
            raise ValueError("only an item (물건인가: 예) has 성질 and 소개")
        if self.item and self.lock:
            raise ValueError("a locked thing is not an item")
        return self


class Place(Shape):
    desc: str = Field(alias="모습")
    links: list[str] = Field([], alias="이어진 곳")
    cond: str | None = Field(None, alias="나오는 조건")
    display: str | None = Field(None, alias="화면 이름")


class Act(Shape):
    leave: str | None = Field(None, alias="떠난다")
    move: tuple[str, str] | None = Field(None, alias="옮긴다")
    vanish: str | None = Field(None, alias="없어진다")

    @model_validator(mode="after")
    def fit_one(self):
        if len(self.model_fields_set) != 1:
            raise ValueError("an act is one of 떠난다, 옮긴다, 없어진다")
        return self


class Event(Shape):
    at: int = Field(alias="때", ge=1)
    acts: list[Act] = Field(alias="일", min_length=1)
    guard: str | None = Field(None, alias="막는 조건")
    omen: str | None = Field(None, alias="조짐")
    happened: str = Field(alias="벌어졌을 때")
    prevented: str | None = Field(None, alias="막았을 때")

    @model_validator(mode="after")
    def fit_time(self):
        if (self.omen is None) == (self.at >= 4):
            raise ValueError("조짐 is required from 때 4 on and absent before it")
        if (self.prevented is None) != (self.guard is None):
            raise ValueError("막았을 때 goes with 막는 조건")
        return self


class Clock(Shape):
    start: Annotated[int, BeforeValidator(to_minutes)] = Field(alias="시작", ge=0, lt=24 * 60)
    step: int = Field(alias="한 칸", ge=1)


class Truth(Shape):
    who: str = Field(alias="누가")
    how: str = Field(alias="어떻게")
    why: str = Field(alias="왜")


class Opening(Shape):
    """The first turn's text, written by the author so the game opens at once (game/08 2절)."""
    scene: str = Field(alias="장면")
    first: str = Field(alias="첫마디")


class Head(Shape):
    name: str = Field(alias="이름", pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(alias="제목")
    intro: str = Field(alias="도입")
    start: str = Field(alias="시작하는 곳")
    cells: int = Field(alias="칸 수", ge=1)
    clock: Clock | None = Field(None, alias="시각")
    mood: str | None = Field(None, alias="분위기")   # the voice of scenes and the DM (game/08 2절)
    opening: Opening | None = Field(None, alias="여는 글")   # optional so old saves' story copies still open
    truth: Truth = Field(alias="진실")


class Endings(Shape):
    solved: str = Field(alias="다 밝혔다")
    who_only: str = Field(alias="누구인지는 밝혔다")
    wrong: str = Field(alias="엉뚱한 사람을 짚었다")
    unsolved: str = Field(alias="밝히지 못했다")
    explain: str = Field(alias="진실 풀이")


class StoryFile(Shape):
    head: Head = Field(alias="머리")
    facts: dict[str, str] = Field(alias="사실", min_length=1)
    props: list[str] = Field([], alias="성질")
    places: dict[str, Place] = Field(alias="곳", min_length=1)
    things: dict[str, Thing] = Field({}, alias="볼 것")
    people: dict[str, Person] = Field({}, alias="사람")
    events: list[Event] = Field([], alias="번진 일")
    endings: Endings = Field(alias="결말")

    @model_validator(mode="after")
    def fit_names(self):
        seen = {}
        groups = (("사실", self.facts), ("성질", self.props), ("곳", self.places), ("볼 것", self.things),
                  ("사람", self.people))
        for group, names in groups:
            for name in names:
                if "." in name:
                    raise ValueError(f"{group} {name}: a name has no '.'")
                if name in seen:
                    raise ValueError(f"{name} names both {seen[name]} and {group}")
                seen[name] = group
        for person, p in self.people.items():
            for topic in p.topics:
                if "." in topic:
                    raise ValueError(f"화제 {person}.{topic}: a name has no '.'")
        return self

    @model_validator(mode="after")
    def fit_cells(self):
        for person, p in self.people.items():
            if p.doing and (0 not in p.doing or any(not 0 <= at <= self.head.cells for at in p.doing)):
                raise ValueError(f"사람 {person}의 하는 일: 칸 {sorted(p.doing)} must start at 0 and end by {self.head.cells}")
        for event in self.events:
            if event.at > self.head.cells:
                raise ValueError(f"번진 일 때 {event.at} is past 칸 수 {self.head.cells}")
        return self


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(k, deep=deep) for k, _ in node.value]
        for key in keys:
            if keys.count(key) > 1:
                raise yaml.constructor.ConstructorError(None, None, f"key {key!r} appears twice", node.start_mark)
        return super().construct_mapping(node, deep)


def load_story(folder):
    raw = read_story(folder)
    missing = find_missing(raw)
    if missing:
        raise StoryError(f"{folder}: " + "; ".join(missing))
    return Story(raw)


def read_story(folder):
    path = Path(folder) / "story.yaml"
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        return StoryFile.model_validate(data)
    except (OSError, yaml.YAMLError) as exc:
        raise StoryError(f"{path}: {exc}") from None
    except ValidationError as exc:
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise StoryError(f"{path}: {errors}") from None


def parse_address(text):
    for kind, count in ADDRESS_PARTS.items():
        if text.startswith(kind + " "):
            parts = [p.strip() for p in text[len(kind) + 1:].split(".")]
            if len(parts) == count and all(parts):
                return kind, parts
    return None, []


def format_address(kind, parts):
    return f"{kind} {'.'.join(parts)}"


def find_missing(raw):
    refs = References(raw)
    refs.check_head()
    for name, place in raw.places.items():
        refs.check_place(name, place)
    for name, thing in raw.things.items():
        refs.check_thing(name, thing)
    refs.check_holders()
    for name, person in raw.people.items():
        refs.check_person(name, person)
    for event in raw.events:
        refs.check_event(event)
    return refs.missing


class References:
    def __init__(self, raw):
        self.raw = raw
        self.groups = {"사실": raw.facts, "성질": raw.props, "곳": raw.places, "볼 것": raw.things, "사람": raw.people}
        self.lines = set(self.list_lines())
        self.blocks = set(self.list_blocks())
        self.holders = {}
        self.missing = []

    def list_lines(self):
        raw = self.raw
        yield from (format_address("곳", [p]) for p in raw.places)
        yield from (format_address("사람", [p]) for p in raw.people)
        yield from (format_address("볼 것", [t]) for t in raw.things)
        for person, p in raw.people.items():
            for topic, t in p.topics.items():
                yield from (format_address("말", [person, topic, b]) for b in t.list_branches())

    def list_blocks(self):
        for person, p in self.raw.people.items():
            for topic, t in p.topics.items():
                if t.stance != "숨기지 않는다":
                    yield format_address("거짓말" if t.stance == "거짓말한다" else "꺼림", [person, topic])
        yield from (format_address("잠김", [t]) for t, thing in self.raw.things.items() if thing.lock)

    def need(self, where, name, *kinds):
        if not any(name in self.groups[k] for k in kinds):
            self.missing.append(f"{where}: {name}")

    def need_address(self, where, text, known):
        kind, parts = parse_address(text)
        if format_address(kind, parts) not in known:
            self.missing.append(f"{where}: {text}")
        elif kind == "말" and parts[2] == "거짓말":
            self.missing.append(f"{where}: {text} (거짓말 갈래)")

    def check_head(self):
        head = self.raw.head
        self.need("머리의 시작하는 곳", head.start, "곳")
        self.need("머리의 누가", head.truth.who, "사람")
        self.need("머리의 어떻게", head.truth.how, "사실")
        self.need("머리의 왜", head.truth.why, "사실")

    def check_place(self, name, place):
        for link in place.links:
            self.need(f"곳 {name}의 이어진 곳", link, "곳")
        if place.cond:
            self.need_address(f"곳 {name}의 나오는 조건", place.cond, self.lines)

    def check_thing(self, name, thing):
        where = f"볼 것 {name}"
        if thing.place:
            self.need(f"{where}의 곳", thing.place, "곳")
        for prop in thing.props:
            self.need(f"{where}의 성질", prop, "성질")
        if thing.shows:
            self.need(f"{where}의 보여 주는 사실", thing.shows, "사실")
        for told in thing.tells:
            self.need(f"{where}의 알리는 것", told, "곳", "사람")
        if thing.cond:
            self.need_address(f"{where}의 나오는 조건", thing.cond, self.lines)
        if thing.lock:
            self.check_lock(name, thing.lock)

    def check_lock(self, name, lock):
        self.need(f"잠김 {name}의 약점", lock.weak, "성질")
        if lock.owner:
            self.need(f"잠김 {name}의 주인", lock.owner, "사람")
        for inner in lock.contents:
            self.need(f"잠김 {name}의 안에 든 것", inner, "볼 것", "곳")
            self.holders.setdefault(inner, []).append(name)

    def check_holders(self):
        for inner, locks in self.holders.items():
            if len(locks) > 1:
                self.missing.append(f"{inner}: 잠긴 것 여럿 안에 들어 있다 ({', '.join(locks)})")
        for name, thing in self.raw.things.items():
            if (thing.place is None) == (name not in self.holders):
                self.missing.append(f"볼 것 {name}의 곳: 놓인 곳과 잠긴 것 가운데 하나만 있어야 한다")

    def check_person(self, name, person):
        self.need(f"사람 {name}의 있는 곳", person.place, "곳")
        for other in person.close:
            self.need(f"사람 {name}의 가까운 사람", other, "사람")
        for topic, t in person.topics.items():
            self.check_topic(name, topic, t)

    def check_topic(self, name, topic, t):
        where = f"화제 {name}.{topic}"
        for branch, b in t.list_branches().items():
            if b.shows:
                self.need(f"말 {name}.{topic}.{branch}의 보여 주는 사실", b.shows, "사실")
            for told in b.tells:
                self.need(f"말 {name}.{topic}.{branch}의 알리는 것", told, "곳", "사람")
        for fact in t.list_breaks():
            self.need(f"{where}의 깨는 사실", fact, "사실")
        if t.wants:
            self.need(f"{where}의 바라는 것", t.wants, "사실", "성질")
        if t.cond:
            self.need_address(f"{where}의 나오는 조건", t.cond, self.lines)

    def check_event(self, event):
        where = f"번진 일 {event.at}칸째"
        for act in event.acts:
            if act.leave:
                self.need(f"{where}의 떠난다", act.leave, "사람")
            if act.move:
                self.need(f"{where}의 옮긴다", act.move[0], "사람")
                self.need(f"{where}의 옮긴다", act.move[1], "곳")
            if act.vanish:
                self.need(f"{where}의 없어진다", act.vanish, "볼 것")
        if event.guard:
            self.need_address(f"{where}의 막는 조건", event.guard, self.blocks)


class Record(BaseModel):
    model_config = ConfigDict(frozen=True)


class Line(Record):
    addr: str
    kind: str
    name: str
    topic: str | None = None
    branch: str | None = None
    text: str | None = None
    shows: str | None = None
    props: list[str] = []
    tells: list[str] = []
    cond: str | None = None
    lock: str | None = None
    place: str | None = None


class Block(Record):
    addr: str
    kind: str
    name: str
    topic: str | None = None
    wants: tuple[str, ...]   # any one of them opens it
    unlock: str | None = None   # an impression that opens it once it has built up to unlock_count
    unlock_count: int = 1
    hint: str | None = None
    hard: bool = False
    owner: str | None = None
    opens: list[str] = []
    cond: str | None = None


class Story:
    def __init__(self, raw):
        self.copy = raw.model_dump(by_alias=True, exclude_unset=True)
        self.mark = hashlib.sha256(json.dumps(self.copy, ensure_ascii=False).encode()).hexdigest()
        self.head, self.places, self.things, self.people = raw.head, raw.places, raw.things, raw.people
        self.events, self.endings = raw.events, raw.endings
        self.links = {name: [] for name in raw.places}
        for name, place in raw.places.items():
            for link in place.links:
                for a, b in ((name, link), (link, name)):
                    if b not in self.links[a]:
                        self.links[a].append(b)
        self.close = {name: sorted({*p.close, *(o for o, q in raw.people.items() if name in q.close)} - {name})
                      for name, p in raw.people.items()}
        self.locked_in = {inner: format_address("잠김", [name])
                          for name, thing in raw.things.items() if thing.lock for inner in thing.lock.contents}
        # The first person at the start opens the game and tells the case (game/04 5절).
        self.opener = next((name for name, p in raw.people.items() if p.place == raw.head.start), None)
        self.lines = {}
        self.blocks = {}
        self.build_lines()
        self.build_blocks()
        self.shows = {fact: [a for a, line in self.lines.items() if line.shows == fact] for fact in raw.facts}
        self.holders = {prop: [a for a, line in self.lines.items() if prop in line.props] for prop in raw.props}

    def build_lines(self):
        for name, place in self.places.items():
            self.add_line("곳", [name], cond=place.cond, lock=self.locked_in.get(name), place=name)
        for name, person in self.people.items():
            self.add_line("사람", [name], place=person.place)
        for name, thing in self.things.items():
            self.add_line("볼 것", [name], text=thing.text, shows=thing.shows, props=thing.props,
                          tells=self.list_told(thing.tells), cond=thing.cond, lock=self.locked_in.get(name),
                          place=self.find_home(name))
        for name, person in self.people.items():
            for topic, t in person.topics.items():
                for branch, b in t.list_branches().items():
                    self.add_line("말", [name, topic, branch], topic=topic, branch=branch, text=b.text,
                                  shows=b.shows, tells=self.list_told(b.tells), cond=t.cond, place=person.place)
        # Not in the story file, so the copies older saves keep still open (data/02 4절).
        self.lines[CASE] = Line(addr=CASE, kind=CASE, name=CASE, text=self.head.intro, place=self.head.start)

    def add_line(self, kind, parts, cond=None, **fields):
        addr = format_address(kind, parts)
        cond = format_address(*parse_address(cond)) if cond else None
        self.lines[addr] = Line(addr=addr, kind=kind, name=parts[0], cond=cond, **fields)

    def list_told(self, names):
        return [format_address("곳" if n in self.places else "사람", [n]) for n in names]

    def find_home(self, name):
        while self.things[name].place is None:
            name = self.locked_in[name].removeprefix("잠김 ")
        return self.things[name].place

    def build_blocks(self):
        for name, person in self.people.items():
            for topic, t in person.topics.items():
                if t.stance == "거짓말한다":
                    self.add_block("거짓말", [name, topic], topic=topic, wants=tuple(t.list_breaks()),
                                   opens=[format_address("말", [name, topic, "깨진 뒤"])], cond=t.cond,
                                   unlock=t.unlock, unlock_count=t.unlock_count or 1)
                elif t.stance == "꺼린다":
                    self.add_block("꺼림", [name, topic], topic=topic, wants=(t.wants,), hint=t.hint,
                                   opens=[format_address("말", [name, topic, "풀린 뒤"])], cond=t.cond,
                                   unlock=t.unlock, unlock_count=t.unlock_count or 1)
        for name, thing in self.things.items():
            if thing.lock:
                kinds = ["볼 것" if inner in self.things else "곳" for inner in thing.lock.contents]
                self.add_block("잠김", [name], wants=(thing.lock.weak,), hint=thing.lock.hint, hard=thing.lock.hard,
                               owner=thing.lock.owner, cond=thing.cond,
                               opens=[format_address(k, [i]) for k, i in zip(kinds, thing.lock.contents, strict=False)])

    def add_block(self, kind, parts, cond=None, **fields):
        addr = format_address(kind, parts)
        cond = format_address(*parse_address(cond)) if cond else None
        self.blocks[addr] = Block(addr=addr, kind=kind, name=parts[0], cond=cond, **fields)
