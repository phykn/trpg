from ..game.names import show_line, show_name
from ..locale import ko
from ..rules.state import judge_ending, list_people_here, list_rumors

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
    # Help for a player stuck long (game/07 2절): one thing to do, named outright, never the answer.
    "hint_topic": ("오래도록 새로 알아낸 것이 없다. 인물은 플레이어 곁에 있다.",
                   "인물이 짚을 것의 이야기를 꺼내고 싶어 하는 눈치를 몸짓으로 그리고, 짚을 것의 이름을 따옴표 없이 그대로 쓴다"),
    "hint_line": ("오래도록 새로 알아낸 것이 없다.",
                  "당신이 수첩에 적어 둔 짚을 것을 문득 다시 떠올린다고 쓴다. 그것을 어디에 쓸지는 말하지 않는다"),
    "hint_place": ("오래도록 새로 알아낸 것이 없다.", "당신의 머리에 아직 가 보지 않은 짚을 것의 이름이 자꾸 떠오른다고 쓴다"),
    "ready": ("플레이어가 누가, 어떻게, 왜를 밝힐 조각을 다 모았지만 아직 결론을 내지 않았다.",
              "조각이 다 모인 것 같은 기분, 이제 한번 따져 볼 때라는 느낌을 당신의 속마음으로 그린다. 무엇이 답인지는 말하지 않는다"),
}
PERSON_KEYS = ("open", "meet", "held", "doubt", "ask", "warm", "cold", "shaken", "hint_topic")
# The narrator's voice: the scene, the DM and the ending (game/07 2절).
VOICE = ("시각, 소리, 냄새, 맛, 촉감 가운데 하나만 살려 감각적으로 그리고, 건조한 블랙 조크는 문장 끝에 짧게 얹는다. 농담도 "
         "'-습니다', '-ㅂ니다'로 맺고 '-군요'는 쓰지 않는다. 크게 웃기지 않는다. 비유와 농담에도 받은 것에 없는 사람, 물건, 일은 넣지 않는다.")
CAUGHT = "남을 속이려다 들켰다"   # 들킴 comes from a deed, so it has no meaning for Kanana in ko.IMPRESSIONS
RECENT = 3   # turns of talk with a person, and turns of the player's deeds they watched, an answer gets (game/04 3절)
# The narrator's own last texts it gets, so it stops reaching for the same smell every turn (game/07 2절)
NARRATED = 4


def list_slots(story, turn):
    """A turn's text slots in the order the feed numbers them (engine/02 4절)."""
    do = turn["action"]["do"]
    slots = []
    if do == "conclude":
        who = turn["action"]["who"]
        slots += [{"kind": "text", "person": who, "job": "confront"}] if who else []
        slots.append({"kind": "ending"})
    elif do not in ("face", "read"):
        slots.append({"kind": "text", "person": find_speaker(story, turn["talk"])})
    # The opener calls out to the player as the game starts (game/04 5절); older saves have no hook.
    slots += [{"kind": "text", "person": item["hook"], "job": "hook"} for item in turn["talk"] if "hook" in item]
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
        if kind == "refuse":
            return story.lines[value].name
        if kind in ("case", "pass", "done", "chat", "unsure") or kind == "try" and value in story.people:
            return value
    return None


def make_jobs(story, before, after, turn, past=()):
    """`past` holds each earlier turn with the state after it, oldest first."""
    return [make_job(story, before, after, turn, slot, past) for slot in list_slots(story, turn)]


def make_job(story, before, after, turn, slot, past):
    opening = story.head.opening
    if opening and turn["action"]["do"] == "stats" and slot["kind"] == "text":
        # The author wrote the first turn, so the game opens without waiting on a model (game/08 2절).
        return {"kind": "written", "text": opening.first if slot.get("job") == "hook" else opening.scene}
    job = make_slot_job(story, before, after, turn, slot, past)
    if job["kind"] == "answer":
        return job
    # The story's voice for the narrator alone; people speak in their own (game/08 2절)
    return {**job, **({"mood": story.head.mood} if story.head.mood else {}), "narrated": list_narrated(story, past)}


def is_narrator(slot):
    return slot["kind"] != "text" or not slot["person"]


def list_narrated(story, past):
    """The narrator's texts of the last turns, oldest first; a person's lines are theirs, not the narrator's."""
    texts = []
    for turn, _ in reversed(past):
        texts = [t["text"] for slot, t in zip(list_slots(story, turn), turn["text"] or [], strict=False)
                 if is_narrator(slot)] + texts
        if len(texts) >= NARRATED:
            break
    return texts[-NARRATED:]


def make_slot_job(story, before, after, turn, slot, past):
    if slot["kind"] == "ending":
        return make_ending(story, after)
    if slot["kind"] == "guide":
        return make_dm(story, after, slot["guide"])
    if slot["kind"] in ("omen", "event"):
        return make_happening(story, before, after, slot["happened"])
    if slot.get("job") == "hook":
        return make_hook(story, before, after, turn, slot["person"], past)
    if slot.get("job") == "confront":
        return make_confront(story, before, after, turn, slot["person"], past)
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


def make_hook(story, before, after, turn, person, past):
    """The opener's first call as the game starts: the case in a cry, no details and no topic names (game/04 5절)."""
    job = make_answer(story, before, after, turn, person, past)
    return {**job, "says": ["사건을 한마디로 외치며 당신에게 먼저 말을 건다. 무엇이, 언제까지인지와 자세한 것은 아직 말하지 않는다"],
            "case": story.head.intro, "quiet": False, "leads": [], "hook": True}


def make_confront(story, before, after, turn, person, past):
    """The one the player named as the culprit answers it (game/07 4절); the ending tells the rest."""
    job = make_answer(story, before, after, turn, person, past)
    reaction = ("궁지에 몰린 사람처럼 반응한다. 발뺌하다 무너지거나, 뻔뻔하게 버틴다" if person == story.head.truth.who
                else "억울해서 펄쩍 뛴다")
    # Kanana took the accusation itself for told case content (opening-fix text-after 대면 한스), so it is not asked.
    return {**job, "says": [f"당신이 자기를 범인으로 지목했다. {reaction}. 사건의 내용은 말하지 않는다"], "quiet": False,
            "said": f"(당신이 {ko.eul(show_name(story, '사람', person))} 범인으로 지목한다)"}


def make_answer(story, before, after, turn, person, past):
    says, case, leads, named = [], None, [], []
    for item in turn["talk"]:
        if "case" in item:   # the first talk with the opener tells the case and ends naming topics (game/04 5절)
            case = story.head.intro
            says.append("당신이 처음 말을 걸어왔으니 사건을 들려준다. 사건에 적힌 무엇이 어떻게 됐고 기한이 언제인지만 말한다")
            named = item["leads"]
        elif say := tell_item(story, turn, item):
            says.append(say)
            leads += [item["lead"].split(".", 1)[1]] if "lead" in item else []
            if item.get("point"):   # gemma4 left the place out (qa_test/runs/opening-fix-play 7턴), so it is checked too
                line = story.lines[item["point"]]
                leads.append(show_name(story, line.kind, line.name))
    says += [tell_lead(t) for t in named]
    leads += named
    lines = [story.lines[item["say"]].text for item in turn["talk"] if "say" in item]
    attitude = after["attitudes"][person]
    told = [story.lines[a].text for a in before["notebook"]
            if story.lines[a].kind == "말" and story.lines[a].name == person and a not in before["struck"]]
    return {"kind": "answer", "person": show_name(story, "사람", person), "bio": story.people[person].bio,
            "mbti": story.people[person].mbti, "case": case,
            "attitude": f"믿음 {LEVELS[attitude['trust']]}, 두려움 {LEVELS[attitude['fear']]}",
            "said": find_said(story, turn), "says": says, "lines": lines, "quiet": not lines and bool(says) and not case,
            "leads": leads, "bet": turn["action"]["do"] == "bet",
            # A bet on a person must show in the answer whether they gave way (engine/01 4절)
            **({"outcome": ko.OUTCOMES[turn["dice"]["won"]]} if turn["dice"] else {}),
            "where": show_name(story, "곳", after["place"]),
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


def find_last_said(story, person, turns):
    """The last text the person said on screen, or None before it is written."""
    for turn in reversed(turns):
        said = [i for i, slot in enumerate(list_slots(story, turn)) if slot["kind"] == "text" and slot["person"] == person]
        if said and turn["text"]:
            return turn["text"][said[-1]]["text"]
    return None


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
    dice = turn["dice"]
    method = turn["action"].get("method")
    if kind == "say":
        if dice and turn["action"]["target"] == value:
            # Older saves told a failed bet the line as well; a won bet shows the person give way (game/05 3절)
            lead = ("이 말을 짧게 되풀이한다: " if not dice["won"] else
                    f"{ko.GAVE[method]} 이 말을 다시 하지만, 말끝이 흔들리고 무언가 숨기는 티가 난다: "
                    if story.lines[value].branch == "거짓말" else f"{ko.GAVE[method]} 이 말이 참이라고 흔들림 없이 힘주어 다시 말한다: ")
        else:
            lead = ("거짓말이 들통나 앞의 말을 거두고 털어놓는다: " if value.endswith(".깨진 뒤") else
                    f"{ko.GAVE[method]} 숨기던 것을 털어놓는다: " if dice and value.endswith(".풀린 뒤") else
                    "마음이 풀려 숨기던 것을 털어놓는다: " if value.endswith(".풀린 뒤") else "")
        return lead + story.lines[value].text
    if kind == "refuse":
        return f"{ko.HELD[method]}. 새로 털어놓는 것은 없고, 그 말에 대해서는 더 말하지 않겠다고 한다"
    if kind == "withhold" and dice:
        return f"{ko.HELD[method]}. 그 화제는 끝내 말해 주지 않는다. 말하지 않는 까닭은 지어내지 않는다"
    if kind == "pass":
        return "내민 것이 자기와 무슨 상관이냐는 듯 받아넘긴다" if turn["action"]["do"] == "present" else "답할 것이 없다"
    if kind == "lead":
        return tell_lead(value.split(".", 1)[1])
    if kind == "unsure":
        return f"무엇을 묻는지 되묻는다: {' / '.join(item['topics'])}"
    if kind == "try":   # a guessed action only offers buttons; the answer is the reading's
        return None if item.get("guess") else (f"{ko.TRIES[item['method']]}. 그 행동에 반응하되, 결과는 아직 모르므로 "
                                               "털어놓거나 굴복하지 않는다")
    if kind == "done" and item.get("point"):
        kind_, name = story.lines[item["point"]].kind, story.lines[item["point"]].name
        return (f"더 말할 것은 없다. 대신 {ko.eul(show_name(story, kind_, name))} 제 짐작처럼 넌지시 입에 올린다. "
                "가 보라거나 만나 보라고 시키지는 않고, 그곳이나 그 사람에 관해 지어내지 않는다")
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
    # The bar shows the time; the scene tells it only at the start and when the deadline draws near (game/07 2절).
    timed = clock and (turn["action"]["do"] == "stats" or story.head.cells - after["spent"] <= 3)
    return {"kind": "scene",
            "time": ko.clock(clock.start + after["spent"] * clock.step) if timed else None,
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
           "here": None, "intro": None, "time": None, "point": None, "leads": []}
    # The ready cue drew the waiting room from the intro while the player stood in the arena (opening-fix-play 29턴).
    if key in ("open", "around", "unvisited", "ready"):
        job["here"] = f"{show_name(story, '곳', place)}. 모습: {story.places[place].desc}"
    if key == "unvisited":
        job["far"] = f"{show_name(story, '곳', name)}. 모습: {story.places[name].desc}"
    if key == "hint_topic":
        job["point"], job["leads"] = guide["topic"], [guide["topic"]]
    if key == "hint_line":
        job["point"] = show_line(story, guide["line"])
    if key == "hint_place":
        job["point"] = show_name(story, "곳", name)
    if key in ("look", "conclude", "ready"):
        clock = story.head.clock
        job["intro"] = story.head.intro
        job["time"] = ko.clock(clock.start + after["spent"] * clock.step) if clock else None
    if key in PERSON_KEYS and name:
        attitude = after["attitudes"][name]
        job["person"] = {"name": show_name(story, "사람", name), "bio": story.people[name].bio,
                         "mbti": story.people[name].mbti,
                         "doing": find_doing(story, after, name),
                         "attitude": f"믿음 {LEVELS[attitude['trust']]}, 두려움 {LEVELS[attitude['fear']]}"}
    return job
