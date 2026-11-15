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
    "talk": "곁에 {name} 있습니다. 아래 입력란에 묻고 싶은 것을 써서 말을 걸어 보세요.",
    "move": "위 띠의 곳 이름을 누르면 다른 곳으로 옮겨 갈 수 있습니다.",
    "notebook": "들은 말과 본 것은 수첩에 적힙니다. 위 띠의 곳 이름을 누르면 다른 곳으로 옮겨 갈 수 있고, 옮길 때마다 턴이 지납니다.",
    "present": "말이 서로 어긋난다 싶으면, 수첩 알림이나 수첩의 줄을 눌러 그 줄을 상대에게 내밀어 보세요.",
    "held": "{name} 말을 아낍니다. 그 마음을 움직일 만한 줄을 수첩에서 골라 내밀어 보세요.",
    "broke": "거짓말을 깼습니다. 앞의 말에 줄이 그어지고, 새로 들은 말이 다음 길을 엽니다.",
    "lock": "잠긴 것이 있습니다. 수첩에서 그 줄을 누르면 가진 물건을 쓰거나 손을 써서 열어 볼 수 있습니다.",
    "omen": "무언가 벌어지려 합니다. 턴이 더 지나기 전에 막을 길이 있을지도 모릅니다.",
    "conclude": "턴이 다 됐습니다. 수첩에서 누가, 어떻게, 왜를 골라 결론을 내세요.",
    "unvisited": "아직 {name}에는 가 보지 않았습니다.",
    "ask": "{name}에게 다른 것을 물어보세요. 수첩의 줄을 내밀어 봐도 좋습니다.",
    "look": "수첩을 다시 훑어보세요. 서로 어긋나는 줄이 있을지 모릅니다.",
}


def guide(key, name=None):
    return GUIDE[key].format(name=ga(name) if key in ("talk", "held") else name)
