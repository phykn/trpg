STATS = {"charm": "매력", "might": "완력", "wit": "재치", "skill": "솜씨"}
# What each common impression means, for Kanana to recognize in a sentence (game/04 4절). 들킴 comes from deeds only.
IMPRESSIONS = {"다정": "다정하게 부르거나 안부를 묻는다", "위로": "처지를 헤아려 달래거나 편들어 준다",
               "칭찬": "추켜세우거나 솜씨를 알아준다", "선물": "무언가를 건네거나 대접하겠다고 한다",
               "무례": "깔보거나 하인처럼 부리거나 욕한다", "의심": "범인이라거나 무언가 숨긴다고 몬다. 으르는 말은 위협이다",
               "위협": "말하지 않으면 해치거나 고발하거나 망하게 하겠다고 으른다"}
METHODS = {"soothe": "달랜다", "press": "몰아세운다", "trick": "속인다", "sneak": "몰래 연다", "force": "힘으로 연다"}
JUDGED = {"lying": "숨기는 것이 있다", "true": "거짓이 아니다"}
UNMET = {"lies": "듣지 못함", "held": "꺼내지 못함", "locks": "찾지 못함"}
UNVISITED = "안 가 봄"
OPENED = "열었다"
GONE = "떠났다"


def has_batchim(word):
    code = ord(word[-1]) - 0xAC00
    return 0 <= code <= 11171 and code % 28 != 0


def eul(word):
    return f"{word}{'을' if has_batchim(word) else '를'}"


def ro(word):
    # ㄹ (final 8) takes 로, like a word without a final consonant.
    code = ord(word[-1]) - 0xAC00
    return f"{word}{'으로' if has_batchim(word) and code % 28 != 8 else '로'}"


def clock(minutes):
    hour, minute = divmod(minutes % (24 * 60), 60)
    if (hour, minute) == (0, 0):
        return "자정"
    part = "새벽" if 1 <= hour < 5 else "오전" if 5 <= hour < 12 else "오후" if 12 <= hour < 18 else "밤"
    return f"{part} {hour % 12 or 12}시" + (f" {minute}분" if minute else "")


def time_bar(clock_text, left):
    return f"{clock_text} · {left}턴" if clock_text else f"{left}턴"


def withheld(topic):
    return f"{topic} 이야기에는 말을 아낀다"


def hint(text):
    return f"실마리: {text}"


def said(person, text):
    return f'{person} "{text}"'


def cost(tried):
    return "아까 통하지 않았다 · 1턴" if tried else "틀리면 1턴"


def present_to(person, tried=False):
    return f"{person}에게 내민다 · {cost(tried)}"


def use_item(item, tried=False):
    return f"{eul(item)} 쓴다 · {cost(tried)}"


def use_on(lock, tried=False):
    return f"{lock}에 쓴다 · {cost(tried)}"


# What a typed action tries, as the person's answer or the scene is told it (game/04 2절).
TRIES = {"press": "플레이어가 거칠게 몰아붙이려 든다", "soothe": "플레이어가 다독이며 마음을 열려 든다",
         "trick": "플레이어가 거짓으로 꾀어 떠보려 든다"}


def try_lock(method, thing):
    return f"당신이 {eul(thing)} {'억지로 비틀어 열려' if method == 'force' else '몰래 따려'} 든다"


def bet(method, chance, topic=None, person=None):
    act = f"{eul(person)} {METHODS[method]}" if person else METHODS[method]
    return f"{topic + ' · ' if topic else ''}{act} · {chance}% · 1턴"


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


def missed_topic(person, topic):
    return f"{person} — {topic}"
