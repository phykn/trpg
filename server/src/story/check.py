import re
from pathlib import Path

from ..rules.act import Turn, does_fit, list_blocks_here, list_topics
from ..rules.state import is_shown, list_people_here, start_state
from .load import Story, StoryError, find_missing, read_story


def load_stories(root):
    stories = {}
    for folder in sorted(p for p in Path(root).iterdir() if (p / "story.yaml").is_file()):
        results, story = check_story(read_story(folder))
        failed = [f"{name}  {detail}" for verdict, name, detail in results if verdict == "떨어짐"]
        if failed:
            raise StoryError(f"{folder}: " + "; ".join(failed))
        stories[story.head.name] = story
    return stories


def report_checks(folder):
    try:
        results, _ = check_story(read_story(folder))
    except StoryError as exc:
        results = [("떨어짐", "읽기", str(exc))]
    for verdict, name, detail in results:
        print(f"{verdict}  {name}  {detail}".rstrip())
    return 1 if any(verdict == "떨어짐" for verdict, _, _ in results) else 0


def check_story(raw):
    missing = find_missing(raw)
    if missing:
        return [("떨어짐", "가리키는 것이 있다", m) for m in missing], None
    story = Story(raw)
    return [("통과", "가리키는 것이 있다", ""), *Checker(story).run()], story


class Checker:
    def __init__(self, story):
        self.story = story
        self.start = start_state(story, 0)
        self.half = story.head.cells // 2

    def run(self):
        return [
            self.check_lies(), self.check_holds(), self.check_truth(), self.check_reach(), self.check_time(),
            self.check_events(), self.check_first(), self.check_unreached(), self.check_intros(),
            *self.alert_size(), *self.alert_long(), *self.alert_asks(), *self.alert_necks(),
        ]

    def check_lies(self):
        failed = []
        for block in (b for b in self.story.blocks.values() if b.kind == "거짓말"):
            end = self.sweep_all(self.start, {block.addr})
            places = list(dict.fromkeys(self.story.lines[a].place for a in self.list_clues(end, block)))
            if len(places) < 2:
                failed.append(f"{block.addr}: 곳이 {'하나뿐이다' if places else '없다'}"
                              + (f" ({places[0]})" if places else ""))
        return judge("거짓말의 길", failed)

    def check_holds(self):
        failed = [b.addr for b in self.story.blocks.values() if b.kind != "거짓말"
                  and not self.list_clues(self.sweep_all(self.start, {b.addr}), b)]
        return judge("꺼림과 잠김의 길", failed)

    def check_truth(self):
        end = self.sweep_all(self.start)
        failed = []
        for question, fact in (("어떻게", self.story.head.truth.how), ("왜", self.story.head.truth.why)):
            found = self.list_showing(end, fact)
            if len(found) < 2:
                failed.append(f"{question} {fact}: 단서가 {'하나뿐이다 (' + found[0] + ')' if found else '없다'}")
        return judge("진실의 길", failed)

    def check_reach(self):
        return judge("주사위 없이 닿는다", self.list_unanswered(self.sweep_all(self.start)))

    def check_time(self):
        cells = self.find_shortest()
        if cells is None:
            return ("떨어짐", "시간 안에 닿는다", "길이 없다")
        return ("통과" if cells <= self.half else "떨어짐", "시간 안에 닿는다", f"{cells}칸 / {self.story.head.cells}칸")

    def check_events(self):
        order = sorted(range(len(self.story.events)), key=lambda i: self.story.events[i].at)
        failed = []
        for k in range(1, len(order) + 1):
            broken = self.list_broken_after(order[:k])
            if broken:
                failed.append(f"번진 일 {self.story.events[order[k - 1]].at}칸째: {', '.join(broken)}")
        return judge("번진 뒤에도 닿는다", failed)

    def list_broken_after(self, forced):
        turn = Turn(self.story, self.start)
        turn.forced = forced
        for i in forced:
            turn.settle(i, self.story.events[i])
        world = turn.state
        end = self.sweep_all(world)
        broken = [b.addr for b in self.story.blocks.values()
                  if (b.kind == "잠김" or b.name not in world["gone"]) and b.name not in world["lost"]
                  and not self.list_clues(self.sweep_all(world, {b.addr}), b)]
        broken += [q for q, fact in (("어떻게", self.story.head.truth.how), ("왜", self.story.head.truth.why))
                   if not self.list_showing(end, fact)]
        if self.list_unanswered(end):
            broken.append("주사위 없이 닿는다")
        cells = self.find_shortest(forced)
        if cells is None or cells > self.half:
            broken.append("시간 안에 닿는다")
        return broken

    def check_first(self):
        start = self.story.head.start
        count = len([p for p in self.story.links[start] if f"곳 {p}" in self.start["notebook"]]) + len(
            list_people_here(self.story, self.start))
        return judge("첫걸음", [] if count >= 2 else [f"{count}"])

    def check_unreached(self):
        book = self.sweep_all(self.start, free=True)["notebook"]
        missing = [f"곳 {p}" for p in self.story.places if f"곳 {p}" not in book]
        missing += [f"볼 것 {t}" for t in self.story.things if f"볼 것 {t}" not in book]
        missing += [f"화제 {p}.{t}" for p, person in self.story.people.items() for t in person.topics
                    if not any(a.startswith(f"말 {p}.{t}.") for a in book)]
        return judge("닿지 않는 것", missing)

    def check_intros(self):
        missing = [f"사람 {p}" for p, person in self.story.people.items() if not person.intro]
        missing += [f"볼 것 {t}" for t, thing in self.story.things.items() if thing.item and not thing.intro]
        return judge("소개", missing)

    def alert_size(self):
        counts = {"막힘": len(self.story.blocks), "사람": len(self.story.people), "곳": len(self.story.places)}
        sizes = {"막힘": (7, 9), "사람": (4, 5), "곳": (4, 6)}   # game/02 6절
        if all(low <= counts[k] <= high for k, (low, high) in sizes.items()):
            return []
        return [("알림", "크기", ", ".join(f"{k} {n}" for k, n in counts.items()))]

    def alert_long(self):
        return [("알림", "긴 할 말", a) for a, line in self.story.lines.items() if line.kind == "말"
                and len([s for s in re.split(r"[.?!]", line.text) if s.strip()]) >= 3]

    def alert_asks(self):
        # Three asks or more, not all built on the topic's own name (game/08 5절).
        return [("알림", "묻는 말", f"{p}.{t}") for p, person in self.story.people.items()
                for t, topic in person.topics.items()
                if len(topic.asks) < 3 or all(t in ask for ask in topic.asks)]

    def alert_necks(self):
        return [("알림", "한 막힘의 목", b) for b in self.story.blocks
                if self.list_unanswered(self.sweep_all(self.start, {b}))]

    def sweep_all(self, state, blocked=(), free=False):
        while True:
            size = (len(state["notebook"]), len(state["opened"]))
            for place in self.story.places:
                if f"곳 {place}" in state["notebook"] and is_shown(self.story, state, f"곳 {place}"):
                    turn = Turn(self.story, state)
                    turn.change("move", place=place)
                    state = self.sweep(turn.state, blocked, free)
            if (len(state["notebook"]), len(state["opened"])) == size:
                return state

    def sweep(self, state, blocked=(), free=False):
        turn = Turn(self.story, state)
        while True:
            size = (len(turn.state["notebook"]), len(turn.state["opened"]))
            turn.look_around()
            turn.write_up()
            for person in list_people_here(self.story, turn.state):
                for topic in list_topics(self.story, turn.state, person):
                    turn.ask_topic(person, topic)
            turn.write_up()
            for block in list_blocks_here(self.story, turn.state):
                if block.addr not in blocked and (free and block.kind != "거짓말" or self.list_clues(turn.state, block)):
                    turn.open_block(block)
                    turn.write_up()
            if (len(turn.state["notebook"]), len(turn.state["opened"])) == size:
                return turn.state

    def find_shortest(self, forced=()):
        first = self.sweep(self.start)
        if not self.list_unanswered(first):
            return 0
        frontier, seen = [first], {}
        for cells in range(1, self.story.head.cells + 1):
            ahead = []
            for state in frontier:
                for new in self.list_steps(state, forced):
                    if not self.list_unanswered(new):
                        return cells
                    known = frozenset(new["notebook"]) | frozenset(new["opened"])
                    olds = seen.setdefault((new["place"], tuple(sorted(new["events"].items()))), [])
                    if not any(known <= old for old in olds):
                        olds.append(known)
                        ahead.append(new)
            frontier = ahead
        return None

    def list_steps(self, state, forced):
        for place in self.story.links[state["place"]]:
            if f"곳 {place}" in state["notebook"] and is_shown(self.story, state, f"곳 {place}"):
                turn = Turn(self.story, state)
                turn.forced = forced
                turn.change("move", place=place)
                turn.write_up()
                turn.spend()
                yield self.sweep(turn.state)

    def list_clues(self, state, block):
        return [a for a in state["notebook"] if self.story.lines[a].kind in ("볼 것", "말") and a not in block.opens
                and does_fit(self.story, a, block)]

    def list_showing(self, state, fact):
        return [a for a in state["notebook"] if self.story.lines[a].shows == fact]

    def list_unanswered(self, state):
        truth = self.story.head.truth
        asked = (("누가", f"사람 {truth.who}" in state["notebook"]), ("어떻게", self.list_showing(state, truth.how)),
                 ("왜", self.list_showing(state, truth.why)))
        return [q for q, found in asked if not found]


def judge(name, failed):
    return ("떨어짐", name, "; ".join(failed)) if failed else ("통과", name, "")
