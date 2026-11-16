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


def eun(word):
    return f"{word}{'은' if has_batchim(word) else '는'}"


def ro(word):
    code = ord(word[-1]) - 0xAC00
    return f"{word}{'으로' if has_batchim(word) and code % 28 != 8 else '로'}"


def withheld(topic):
    return f"{topic} 이야기에는 말을 아낀다"


def hint(text):
    return f"실마리: {text}"


def cost(tried):
    return "아까 통하지 않았다 · 1턴" if tried else "틀리면 1턴"


def present_to(person, tried=False):
    return f"{person}에게 내민다 · {cost(tried)}"


def use_item(item, tried=False):
    return f"{eul(item)} 쓴다 · {cost(tried)}"


def use_on(lock, tried=False):
    return f"{lock}에 쓴다 · {cost(tried)}"


def bet(method, chance, topic=None, person=None):
    act = f"{eul(person)} {METHODS[method]}" if person else METHODS[method]
    return f"{topic + ' · ' if topic else ''}{act} · {chance}% · 1턴"


def said(person, text):
    return f'{person} "{text}"'


def clock(minutes):
    hour, minute = divmod(minutes % (24 * 60), 60)
    if (hour, minute) == (0, 0):
        return "자정"
    part = "새벽" if 1 <= hour < 5 else "오전" if 5 <= hour < 12 else "오후" if 12 <= hour < 18 else "밤"
    return f"{part} {hour % 12 or 12}시" + (f" {minute}분" if minute else "")


def time_bar(clock_text, left):
    return f"{clock_text} · {left}턴" if clock_text else f"{left}턴"


def divider(place, cells):
    return f"── {place} · {cells}턴 ──"


def roll(method, eyes, total, need):
    bonus = total - sum(eyes)
    more = f" {'+' if bonus > 0 else '-'} {abs(bonus)}" if bonus else ""
    return f"{METHODS[method]} · {eyes[0]} + {eyes[1]}{more} = {total} · {need} 이상"


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


UNMET = {"lies": "듣지 못함", "held": "꺼내지 못함", "locks": "찾지 못함"}


def missed_topic(person, topic):
    return f"{person} — {topic}"

