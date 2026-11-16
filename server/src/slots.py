from .locale import ko
from .names import show_line, show_name
from .rules.state import judge_ending, list_people_here, list_rumors

LEVELS = {-1: "낮음", 0: "보통", 1: "높음"}
# The DM shows signs in the world and leaves the choice to the player (game/07 2절): a sound, a light, a smell or a
# gesture, never advice. Only "conclude" asks outright, since the game cannot end without the player's answer.
DM = {
    "open": ("판이 막 시작되었다. 인물은 플레이어 곁에 있다.",
             "이곳의 모습에서 눈길을 끄는 것 하나와, 인물이 당신을 두고 보이는 몸짓이나 눈길 하나를 그린다"),
    "around": ("플레이어가 이곳을 아직 찬찬히 둘러보지 않았다.",
               ("이곳의 모습에 나온 것 가운데 하나에 당신의 눈길이 머문다고 그린다. 그곳에 무엇이 있는지는 말하지 않고, "
                "'무언가'로 얼버무리지도 않는다")),
    "meet": ("플레이어가 아직 말을 나눠 보지 않은 인물 곁에 왔다.", "인물이 당신을 알아채고 보이는 몸짓이나 눈길 하나를 그린다"),
    "held": ("인물이 어떤 이야기에 입을 다물었다.",
             "인물이 그 이야기를 꺼리는 기색을 몸짓으로 그린다. 두려움이 높으면 겁먹은 기색, 믿음이 낮으면 경계하는 기색이다"),
    "doubt": ("인물의 말에 숨기는 것이 있다는 것이 드러났다.",
              "인물의 말끝이나 눈길에 스친 틈 하나를 그린다. 무엇을 숨기는지는 말하지 않는다"),
    "unvisited": ("한동안 새로 알아낸 것이 없다.",
                  ("당신은 이곳에 그대로 있다. 가 보지 않은 곳 쪽에서 이곳까지 닿는 기척 하나를 그린다. 그곳의 모습에 나온 것에서 "
                   "나는 소리, 빛, 냄새만 쓰고, 그곳에서 무슨 일이 벌어졌다고 쓰지 않는다")),
    "ask": ("한동안 새로 알아낸 것이 없다. 인물은 플레이어 곁에 있다.", "인물이 무언가 더 말할 듯 머뭇거리는 몸짓 하나를 그린다"),
    "warm": ("플레이어가 거듭 남긴 인상에 인물의 마음이 조금 풀렸다.", "인물이 누그러진 기색을 보이는 몸짓 하나를 그린다"),
    "cold": ("플레이어가 거듭 남긴 인상에 인물이 마음을 닫았다.", "인물이 굳은 기색을 보이는 몸짓 하나를 그린다"),
    "shaken": ("플레이어가 거듭 남긴 인상에 인물이 겁을 먹었다.", "인물이 움츠러드는 몸짓 하나를 그린다"),
    "look": ("한동안 새로 알아낸 것이 없다.",
             "도입의 기한이 다가오는 기척 하나를 그리고, 당신이 지금까지 듣고 본 것을 하나씩 되짚는다고 쓴다. 어느 것인지는 말하지 않는다"),
    "conclude": ("시간이 다 되었다.", "도입의 기한이 닥쳤음을 그리고, 누가, 어떻게, 왜, 당신의 결론을 들려 달라고 한다"),
}
PERSON_KEYS = ("open", "meet", "held", "doubt", "ask", "warm", "cold", "shaken")
CAUGHT = "남을 속이려다 들켰다"   # 들킴 comes from a deed, so it has no meaning for Kanana in ko.IMPRESSIONS
RECENT = 3   # turns of talk with a person, and turns of the player's deeds they watched, an answer gets (game/04 3절)


def list_slots(story, turn):
    """A turn's text slots in the order the feed numbers them (engine/02 4절)."""
    do = turn["action"]["do"]
    slots = []
    if do == "conclude":
        slots.append({"kind": "ending"})
    elif do not in ("face", "read"):
        slots.append({"kind": "text", "person": find_speaker(story, turn["talk"])})
    for happened in turn["happened"]:
        if happened.get("result") != "prevented":   # it passes quietly; the ending tells it (game/06 2절)
            slots.append({"kind": "omen" if "omen" in happened else "event", "happened": happened})
    if turn.get("guide"):
        slots.append({"kind": "guide", "guide": turn["guide"]})
    return slots


def find_speaker(story, talk):
    for item in talk:
        kind, value = next(iter(item.items()))
        if kind == "say":
            return story.lines[value].name
        if kind == "withhold":
            return story.blocks[value].name
        if kind == "lead":
            return value.split(".")[0]
        if kind in ("pass", "done", "chat", "unsure") or kind == "try" and value in story.people:
            return value
    return None


def make_jobs(story, before, after, turn, past=()):
    """`past` holds each earlier turn with the state after it, oldest first."""
    return [make_job(story, before, after, turn, slot, past) for slot in list_slots(story, turn)]


def make_job(story, before, after, turn, slot, past):
    job = make_slot_job(story, before, after, turn, slot, past)
    # The story's voice for the narrator alone; people speak in their own (game/08 2절)
    return job if job["kind"] == "answer" or not story.head.mood else {**job, "mood": story.head.mood}


def make_slot_job(story, before, after, turn, slot, past):
    if slot["kind"] == "ending":
        return make_ending(story, after)
    if slot["kind"] == "guide":
        return make_dm(story, after, slot["guide"])
    if slot["kind"] in ("omen", "event"):
        return make_happening(story, before, after, slot["happened"])
    if slot["person"]:
        return make_answer(story, before, after, turn, slot["person"], past)
    return make_scene(story, before, after, turn)


def make_ending(story, after):
    ending = judge_ending(story, after)
    events = [getattr(story.events[i], result) for i, result in ending["events"]]
    clock, cells = story.head.clock, story.head.cells
    marks = {True: "맞혔다", False: "틀렸다", None: "비워 두었다"}
    return {"kind": "ending", "time": ko.clock(clock.start + cells * clock.step) if clock else None,
            "answers": ", ".join(f"{q} {marks[ending['answers'][k]]}" for k, q in
                                 (("who", "누가"), ("how", "어떻게"), ("why", "왜"))),
            "happening": [getattr(story.endings, ending["verdict"]), *events, story.endings.explain]}


def make_happening(story, before, after, happened):
    if "omen" in happened:
        return {"kind": "scene", "happening": [story.events[happened["omen"]].omen], "far": False}
    event = story.events[happened["event"]]
    return {"kind": "scene", "happening": [getattr(event, happened["result"])],
            "far": not is_here(story, before, after, event)}


def is_here(story, before, after, event):
    """Whether an event touches the place the player stands in, so it is seen rather than told as news."""
    place = after["place"]
    return any(a.vanish and story.lines[f"볼 것 {a.vanish}"].place == place
               or (a.leave or (a.move and a.move[0])) and before["where"][a.leave or a.move[0]] == place
               for a in event.acts)


def find_doing(story, state, person):
    """What the person is doing by now (game/04 1절): the latest entry at or before the spent cells."""
    doing = story.people[person].doing
    return doing[max(at for at in doing if at <= state["spent"])] if doing else None


def list_doing(story, state, people):
    # A sentence each: given as name(doing), gemma4 copied the brackets into the scene
    return [f"{ko.eun(show_name(story, '사람', p))} {doing}" for p in people if (doing := find_doing(story, state, p))]


def make_answer(story, before, after, turn, person, past):
    says = [say for item in turn["talk"] if (say := tell_item(story, turn, item))]
    lines = [story.lines[item["say"]].text for item in turn["talk"] if "say" in item]
    attitude = after["attitudes"][person]
    clock = story.head.clock
    told = [story.lines[a].text for a in before["notebook"]
            if story.lines[a].kind == "말" and story.lines[a].name == person and a not in before["struck"]]
    return {"kind": "answer", "person": show_name(story, "사람", person), "bio": story.people[person].bio,
            "attitude": f"믿음 {LEVELS[attitude['trust']]}, 두려움 {LEVELS[attitude['fear']]}",
            "said": find_said(story, turn), "says": says, "lines": lines, "quiet": not lines and bool(says),
            "leads": [item["lead"].split(".", 1)[1] for item in turn["talk"] if "lead" in item],
            "bet": turn["action"]["do"] == "bet",
            "where": ", ".join(filter(None, [show_name(story, "곳", after["place"]),
                                             ko.clock(clock.start + after["spent"] * clock.step) if clock else None])),
            "doing": find_doing(story, after, person),
            "recent": list_recent(story, person, past), "told": told, "saw": list_seen(story, person, past),
            "impressions": list_impressions(story, after, person),
            "rumors": [f"{show_name(story, '사람', r['about'])}에게 {r['impression']}({'직접 봄' if r['seen'] else '전해 들음'})"
                       for r in list_rumors(after, person)]}


def list_impressions(story, state, person):
    meanings = {**ko.IMPRESSIONS, "들킴": CAUGHT, **story.people[person].impressions}
    return [f"{name}({meanings[name]}): {'한 번' if n == 1 else '여러 번'}"
            for name, n in state["impressions"][person].items()]


def spoke(story, person, turn):
    slots = list_slots(story, turn)
    return bool(slots) and slots[0]["kind"] == "text" and slots[0]["person"] == person


def list_recent(story, person, past):
    """The last exchanges with this person, as the screen showed them."""
    recent = []
    for turn, _ in reversed(past):
        if turn["text"] and spoke(story, person, turn):
            recent.insert(0, {"said": find_said(story, turn), "answer": turn["text"][0]["text"]})
            if len(recent) == RECENT:
                break
    return recent


def list_seen(story, person, past):
    """What the player did where this person stood and could watch since they last spoke, in the last few turns."""
    seen = []
    last = max((i + 1 for i, (turn, _) in enumerate(past) if spoke(story, person, turn)), default=0)
    for turn, after in past[max(last, len(past) - RECENT):]:
        if after["where"][person] != after["place"] or person in after["gone"]:
            continue
        speaker = find_speaker(story, turn["talk"])
        for item in turn["talk"]:
            seen += ["이곳을 둘러봤다"] if "look" in item else [x.removeprefix("당신이 ") for x in tell_lock(story, turn, after, item)]
        if turn["action"]["do"] == "present" and speaker and speaker != person:
            seen.append(f"{show_name(story, '사람', speaker)}에게 {ko.eul(show_line(story, turn['action']['line']))} 내밀었다")
        if turn["action"]["do"] == "bet" and speaker and speaker != person:
            seen.append(f"{ko.eul(show_name(story, '사람', speaker))} {ko.METHODS[turn['action']['method']]}")
    return seen


def tell_item(story, turn, item):
    kind, value = next(iter(item.items()))
    if kind == "say":
        repeat = turn["dice"] is not None and turn["action"]["target"] in story.lines
        lead = ("이 말을 짧게 되풀이한다: " if repeat else
                "거짓말이 들통나 앞의 말을 거두고 털어놓는다: " if value.endswith(".깨진 뒤") else
                "마음이 풀려 숨기던 것을 털어놓는다: " if value.endswith(".풀린 뒤") else "")
        return lead + story.lines[value].text
    if kind == "pass":
        return "내민 것이 자기와 무슨 상관이냐는 듯 받아넘긴다" if turn["action"]["do"] == "present" else "답할 것이 없다"
    if kind == "lead":
        return tell_lead(value.split(".", 1)[1])
    if kind == "unsure":
        return f"무엇을 묻는지 되묻는다: {' / '.join(item['topics'])}"
    if kind == "try":   # a guessed action only offers buttons; the answer is the reading's
        return None if item.get("guess") else f"{ko.TRIES[item['method']]}. 그 행동에 반응한다"
    return {"withhold": "이 화제는 얼버무리며 말해 주지 않는다. 말하지 않는 까닭은 지어내지 않는다",
            "done": "더 말할 것이 없다"}.get(kind)


def tell_lead(topic):
    # Told only to hint, gemma4 dropped the name every time (2026-11-16); the check now asks for it word for word.
    return f'"{topic}"라는 말을 그대로 넣어, 그 일이라면 아는 게 있다는 듯 운을 뗀다. 내용은 말하지 않는다'


def find_said(story, turn):
    action = turn["action"]
    if action.get("text"):
        return action["text"]
    if action["do"] == "present":
        return f"(당신이 {ko.eul(show_line(story, action['line']))} 내민다)"
    if action["do"] == "bet":
        return f"(당신이 {ko.METHODS[action['method']]})"
    return None


def make_scene(story, before, after, turn):
    place = after["place"]
    looking = any("look" in item for item in turn["talk"])
    first = turn["action"]["do"] == "stats" or place not in before["visited"] or (
        looking and place not in before["looked"])   # the first look takes the place in properly
    writes = [c["line"] for c in turn["changes"] if c["op"] == "write"]
    happening = ["당신이 주위를 찬찬히 둘러본다"] if looking else []
    for item in turn["talk"]:
        if item.get("thing"):
            happening += tell_thing(story, item["thing"])
    for item in turn["talk"]:
        happening += tell_lock(story, turn, after, item)
        if "try" in item and not item.get("guess"):
            happening.append(ko.try_lock(item["method"], show_name(story, "볼 것", story.blocks[item["try"]].name)))
    clock, people = story.head.clock, list_people_here(story, after)
    return {"kind": "scene", "intro": story.head.intro if turn["action"]["do"] == "stats" else None,
            "time": ko.clock(clock.start + after["spent"] * clock.step) if clock else None,
            "place": show_name(story, "곳", place), "desc": story.places[place].desc, "again": not first,
            "written": [show_line(story, a) for a in writes if story.lines[a].kind == "볼 것"], "happening": happening,
            "people": [show_name(story, "사람", p) for p in people], "doing": list_doing(story, after, people)}


def tell_thing(story, addr):
    line = story.lines[addr]
    intro = story.things[line.name].intro if line.name in story.things else None
    return [f"당신이 {ko.eul(show_line(story, addr))} 눈여겨본다", *filter(None, [line.text, intro])]


def tell_lock(story, turn, after, item):
    kind, value = next(iter(item.items()))
    if kind not in ("open", "shut"):
        return []
    thing = show_line(story, f"볼 것 {story.blocks[value].name}")
    used = turn["action"].get("line")
    by = f"{ko.ro(show_line(story, used))} " if used else ""
    if kind == "shut":
        return [f"{by}{ko.eul(thing)} 열려 했지만 열리지 않는다"]
    inside = story.things[story.blocks[value].name].lock.contents
    return [f"당신이 {by}{ko.eul(thing)} 연다"] + (["그런데 안은 텅 비어 있다"] if all(n in after["lost"] for n in inside) else [])


def make_dm(story, after, guide):
    key, name = guide["key"], guide.get("name")
    situation, cue = DM[key]
    if key == "open" and not name:
        situation, cue = "판이 막 시작되었다. 곁에 아무도 없다.", "이곳의 모습에서 눈길을 끄는 것 하나를 그린다"
    place = after["place"]
    job = {"kind": "dm", "key": key, "situation": situation, "cue": cue, "person": None, "far": None,
           "here": None, "intro": None, "time": None}
    if key in ("open", "around", "unvisited"):
        job["here"] = f"{show_name(story, '곳', place)}. 모습: {story.places[place].desc}"
    if key == "unvisited":
        job["far"] = f"{show_name(story, '곳', name)}. 모습: {story.places[name].desc}"
    if key in ("look", "conclude"):
        clock = story.head.clock
        job["intro"] = story.head.intro
        job["time"] = ko.clock(clock.start + after["spent"] * clock.step) if clock else None
    if key in PERSON_KEYS and name:
        attitude = after["attitudes"][name]
        job["person"] = {"name": show_name(story, "사람", name), "bio": story.people[name].bio,
                         "doing": find_doing(story, after, name),
                         "attitude": f"믿음 {LEVELS[attitude['trust']]}, 두려움 {LEVELS[attitude['fear']]}"}
    return job
