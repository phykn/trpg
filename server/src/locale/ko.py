STATS = {"charm": "매력", "might": "완력", "wit": "재치", "skill": "솜씨"}
METHODS = {"soothe": "달랜다", "press": "몰아세운다", "trick": "속인다", "sneak": "몰래 연다", "force": "힘으로 연다"}
JUDGED = {"lying": "숨기는 것이 있다", "true": "거짓이 아니다"}
UNVISITED = "안 가 봄"
OPENED = "열었다"
GONE = "떠났다"


def has_batchim(word):
    code = ord(word[-1]) - 0xAC00
    return 0 <= code <= 11171 and code % 28 != 0


def eul(word):
    return f"{word}{'을' if has_batchim(word) else '를'}"


def ga(word):
    return f"{word}{'이' if has_batchim(word) else '가'}"


def eun(word):
    return f"{word}{'은' if has_batchim(word) else '는'}"


def withheld(topic):
    return f"{eun(topic)} 말을 아낀다"


def hint(text):
    return f"실마리: {text}"


def present_to(person):
    return f"{person}에게 내민다 · 틀리면 1턴"


def use_item(item):
    return f"{eul(item)} 쓴다 · 틀리면 1턴"


def use_on(lock):
    return f"{lock}에 쓴다 · 틀리면 1턴"


def bet(method, chance, topic=None):
    return f"{topic + ' · ' if topic else ''}{METHODS[method]} · {chance}% · 1턴"


def said(person, text):
    return f'{person} "{text}"'


def clock(minutes):
    hour, minute = divmod(minutes % (24 * 60), 60)
    part = "새벽" if 1 <= hour < 5 else "오전" if 5 <= hour < 12 else "오후" if 12 <= hour < 18 else "밤"
    return f"{part} {hour % 12 or 12}시" + (f" {minute}분" if minute else "")


def time_bar(clock_text, left):
    return f"{clock_text} · {left}턴" if clock_text else f"{left}턴"


def divider(place, cells):
    return f"── {place} · {cells}턴 ──"


def roll(method, eyes, total):
    return f"{METHODS[method]} · {eyes[0]}, {eyes[1]} · {total}"


def note(text):
    return f"수첩 · {text}"


def heard(person):
    return f"{person}의 말 적음"


def broke(person):
    return f"{person}의 말 — 앞의 말에 줄을 긋고 새 말 적음"


def wrote(names):
    return f"{', '.join(names)} 적음"


def held(person, topic):
    return f"{person} — {withheld(topic)}"


def judged(person, verdict):
    return f"{person}의 말 — {JUDGED[verdict]}"


def hinted(name):
    return f"{name} — 실마리"


def opened(name):
    return f"{name} — {OPENED}"


def missed_topic(person, topic):
    return f"{person} — {topic}"


GUIDE = {
    "talk": "곁에 {name} 있습니다. 무엇이든 물어보십시오.",
    "move": "이곳에는 아무도 없습니다. 다른 곳으로 가 보는 건 어떻습니까?",
    "notebook": "들은 말은 수첩에 남습니다. 다른 사람들의 이야기도 들어 보십시오. 다만 길을 나설 때마다 시간이 흐릅니다.",
    "present": "두 사람의 말이 서로 맞는지 견주어 보십시오. 맞지 않는 데가 있다면 그 말을 내밀어 따질 수 있습니다.",
    "held": "{name} 무언가 아는 눈치지만 입을 다뭅니다. 마음을 움직일 무언가가 필요해 보입니다.",
    "broke": "거짓말이 무너졌습니다. 새로 들은 말이 다음 길을 열어 줄 것입니다.",
    "lock": "잠겨 있습니다. 맞는 도구를 찾거나, 힘이나 솜씨를 믿어 볼 수도 있습니다.",
    "omen": "무언가 벌어지려 합니다. 서두르면 막을 수 있을지도 모릅니다.",
    "conclude": "시간이 다 됐습니다. 누가, 어떻게, 왜. 당신의 결론을 들려주십시오.",
    "unvisited": "아직 {name}에는 가 보지 않았습니다.",
    "ask": "{name}에게 다른 것을 물어보거나, 지금까지 알아낸 것을 내밀어 보십시오.",
    "look": "수첩을 다시 훑어보십시오. 서로 어긋나는 줄이 있을지 모릅니다.",
}


def guide(key, name=None):
    return GUIDE[key].format(name=ga(name) if key in ("talk", "held") else name)
