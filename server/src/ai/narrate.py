import re
from difflib import SequenceMatcher

from .jobs import VOICE
from .mbti import MBTI

MEANING = 0.5
ADDED = 0.15
QUIET = 0.5
OUTCOME = 0.5
REWRITES = 2
# An answer may end on a question back and the DM on a dry joke (game/04 3절, game/07 2절), a sentence each.
MAX_SENTENCES = {"answer": 5, "scene": 7, "ending": 12, "dm": 6}
MAX_TOKENS = {"answer": 200, "scene": 300, "ending": 700, "dm": 200}
# Players found long, ornate sentences hard to follow; 60 letters is past nine in ten of the sentences written before.
LONG = 60
SHORT = ("문장은 짧게 쓴다. 한 문장에 한 가지만 말하고 '-고', '-며', '-는데'로 길게 잇지 않는다. 어려운 한자말이나 글말 대신 "
         "누구나 바로 알아듣는 일상의 말을 쓴다.")
# Kanana's meaning check passes answers that drop the line; the share of the line's Hangul syllables in the answer
# catches them (kept lines scored 0.69 and up, dropped or bent ones 0.44 and below).
COVER = 0.5
# An answer this close to one the person already gave says the same thing again; gemma4 did so even when told not to.
REPEAT = 0.8
# Words of the prompt itself; a text that names them is talking about its instructions, not to the player.
# "할 말" alone is everyday speech ("더 할 말 있나?"), so only the label with its colon counts.
PROMPT_WORDS = ("할 말:", "받은 것", "앞서 들려준 글", "지침", "지킬 것", "질문자", "신상", "속사정", "그릴 기척", "지켜본 일", "앞서 나눈 말", "받은 인상")
SCENE_REQUEST = re.compile(r"어떤 장면을 (보여\s*드릴|원하)|마주한 상황을 알려\s*주")
# The narrator and the DM speak 합니다체 (CLAUDE.md); quoted speech inside a scene keeps its own.
HAEYO = re.compile(r"(세요|어요|아요|해요|예요|에요|죠|군요|네요)[.?!…~]*(\s|$)")
# The DM shows a sign instead of advising (game/07 2절); these endings tell the player what to do.
PUSH = re.compile(r"권(합니다|해 드립니다|하고 싶습니다)|(보|가|해|물어|살펴|둘러|찾아|내밀어|따져)\s?보(십시오|세요|시죠|시길|길)|"
                  r"(좋|낫)겠습니다|어떻습니까|어떨까|볼 만합니다|하십시오|가십시오|필요해 보입니다")
# A line said for the first time that the answer calls already said.
AGAIN = re.compile(r"아까 말했|말했잖|말했다니까|말하지 않았")
PLAIN = re.compile(r"(?<!니)다([.!?…]+(\s|$)|$)")   # 해라체, as a story's doing sentence was copied
BRACKET = re.compile(r"[()（）]")   # gemma4 wrote stage directions and copied name(doing) in brackets
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")
REASONS = {"added": "받은 것에 없는 사람, 물건, 때, 곳을 더했다", "meaning": "할 말의 뜻이 빠졌거나 바뀌었다",
           "case": "사건에 적힌 피해 또는 조사 기한이 빠졌거나 바뀌었다",
           "ending": "결말이나 진실 풀이에서 지목된 사람, 실제 범인, 각자가 한 일 또는 그 결과가 바뀌었다",
           "quiet": "말하지 않아야 할 내용을 말했다", "outcome": "주사위의 결과가 대답에 드러나지 않는다", "length": "너무 길다",
           "prompt": "이야기 밖의 지시나 안내를 말했다. 인물이나 진행자의 말만 쓴다",
           "style": "합니다체가 아닌 문장이 있다. 문장을 모두 '-습니다', '-ㅂ니까'로 맺는다",
           "push": "플레이어에게 할 일을 권했다. 권하지 말고 소리, 빛, 냄새, 몸짓 같은 기척만 그린다",
           "speech": "인물의 대사를 지어냈다. 따옴표 없이 몸짓만 그린다",
           "repeat": "앞서 한 대답을 되풀이했다. 플레이어가 방금 한 말에 맞춰 다르게 받아친다",
           "again": "처음 하는 말인데 아까 말했다고 했다. 처음 말하듯 쓴다",
           "bracket": "괄호를 썼다. 괄호 없이 글로만 쓴다",
           "lead": "운을 떼야 할 화제의 이름을 그대로 말하지 않았다",
           "long": "문장이 길다. 한 문장에 한 가지만 담아 짧게 끊어 쓴다",
           "unknown": "받은 것에 없는 이 이야기의 사람, 곳, 물건을 말했다. 받은 것에 나온 것만 쓴다"}


class Narrator:
    def __init__(self, llm, decision):
        self.llm = llm
        self.decision = decision

    async def write(self, job):
        messages = make_messages(job)
        chunks = []
        async for chunk in self.llm.stream(messages, MAX_TOKENS[job["kind"]]):
            chunks.append(chunk)
            yield {"type": "delta", "text": chunk}
        text = first = "".join(chunks)
        checks = []
        for attempt in range(REWRITES + 1):
            failed, probs = await self.check(job, text)
            checks.append({"text": text, "failed": failed, "probs": probs})
            if not failed or attempt == REWRITES:
                break
            note = "이 글은 " + ", ".join(REASONS[f] for f in failed) + ". 지킬 것을 지켜 다시 쓴다."
            if "repeat" in failed:   # gemma4 wrote the same sentence again three times when only told why
                note += f' "{text}"와 겹치는 말은 쓰지 않는다.'
            if "lead" in failed:
                note += " " + ", ".join(f'"{name}"' for name in job["leads"]) + "라는 말을 그대로 넣는다."
            messages = [*messages, {"role": "assistant", "content": text}, {"role": "user", "content": note}]
            text = "".join([chunk async for chunk in self.llm.stream(messages, MAX_TOKENS[job["kind"]])])
        text = pick_best(checks)
        yield {"type": "result", "text": text, "checks": checks, "revised": text != first}

    async def check(self, job, text):
        state = "받은 것:\n" + "\n".join(list_given(job)) + f"\n\n쓴 글:\n{text}"
        answers = await self.decision.decide(state, make_checks(job))
        return judge(job, answers, text)


def pick_best(checks):
    factual = {"meaning", "case", "ending", "quiet", "unknown", "outcome", "prompt"}
    return min(checks, key=lambda c: (len(factual.intersection(c["failed"])), "repeat" in c["failed"],
                                      "lead" in c["failed"], len(c["failed"])))["text"]


def make_messages(job):
    given = "\n".join(g for g in list_given(job) if not g.startswith("플레이어의 말"))
    head, rules, user = {"dm": make_dm_prompt, "answer": make_answer_prompt}.get(job["kind"], make_scene_prompt)(job)
    # Left out of what Kanana checks against: it is what not to write again, not a fact the text may use.
    narrated = "".join(f"\n  {t}" for t in job.get("narrated", []))
    if narrated:
        given += f"\n앞서 들려준 글:{narrated}"
        rules = [*rules, ("앞서 들려준 글의 감각과 표현을 되풀이하지 않는다. 같은 냄새, 소리, 비유, 농담을 다시 쓰지 말고 "
                          "다른 감각과 다른 말을 고른다.")]
    system = f"{head}\n\n받은 것:\n{given}\n\n지킬 것:\n" + "\n".join(f"- {r}" for r in rules)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def list_given(job):
    if job["kind"] == "dm":
        return list_dm_given(job)
    if job["kind"] == "answer":
        given = [f"신상: {job['bio']}"] + ([show_mbti(job["mbti"])] if job.get("mbti") else [])
        given += [f"태도: {job['attitude']}"]
        given += [f"사건(글의 '당신'은 플레이어다): {job['case']}"] if job.get("case") else []
        given += [f"곳: {job['where']}"] if job.get("where") else []
        given += [f"지금 하는 일: {job['doing']}"] if job.get("doing") else []
        if job.get("recent"):
            given.append("앞서 나눈 말:\n" + "\n".join(f"  플레이어: {r['said'] or '(말없이 기다렸다)'}\n  {job['person']}: {r['answer']}"
                                                   for r in job["recent"]))
        given += [f"이미 한 말: {' / '.join(job['told'])}"] if job.get("told") else []
        given += [f"플레이어도 아는 일: {' / '.join(job['knows'])}"] if job.get("knows") else []
        given += [f"지켜본 일(플레이어가 한 일): {' / '.join(job['saw'])}"] if job.get("saw") else []
        given += [f"플레이어에게 받은 인상: {' / '.join(job['impressions'])}"] if job.get("impressions") else []
        given += [f"플레이어에 관한 소문: {' / '.join(job['rumors'])}"] if job.get("rumors") else []
        given += [f"속사정: {' / '.join(job['inner'])}"] if job.get("inner") else []
        return given + [f"할 말: {' / '.join(job['says']) or '없다'}", f"플레이어의 말: {job['said'] or '없다'}"]
    given = [f"분위기: {job['mood']}"] if job.get("mood") else []
    given += [f"시각: {job['time']}"] if job.get("time") else []
    if job.get("place"):
        given.append(f"곳: {job['place']}" + (f". 모습: {job['desc']}" if job.get("desc") else ""))
    given += [f"이번에 눈에 띈 것: {', '.join(job['written'])}"] if job.get("written") else []
    if job["kind"] == "ending":
        verdict, *events, truth = job["happening"]
        given.extend([f"플레이어가 지목한 사람: {job.get('accused') or '없다'}", f"지목의 결과: {verdict}"])
        if events:
            given.append(f"그사이 번진 일: {' '.join(events)}")
        given.append(f"사건의 진실: {truth}")
    elif job.get("happening"):
        given.append(f"{'당신이 없는 곳에서 그 사이 벌어진 일' if job.get('far') else '일어난 일'}: {' '.join(job['happening'])}")
    given += [f"이곳의 사람: {', '.join(job['people'])}"] if job.get("people") else []
    given += [f"사람이 하는 일: {' '.join(d + '.' for d in job['doing'])}"] if job.get("doing") else []
    return given


def show_mbti(mbti):
    return f"성격 유형(MBTI): {mbti}. {MBTI[mbti]}"


def list_dm_given(job):
    given = [f"상황: {job['situation']}"]
    given += [f"분위기: {job['mood']}"] if job.get("mood") else []
    given += [f"도입: {job['intro']}"] if job["intro"] else []
    given += [f"시각: {job['time']}"] if job["time"] else []
    given += [f"이곳: {job['here']}"] if job["here"] else []
    if job["person"]:
        person = job["person"]
        doing = f" 지금 하는 일: {person['doing']}." if person.get("doing") else ""
        mbti = f" {show_mbti(person['mbti'])}" if person.get("mbti") else ""
        given.append(f"인물: {person['name']}. 신상: {person['bio']}{mbti}{doing} 플레이어를 대하는 태도: {person['attitude']}")
    given += [f"가 보지 않은 곳: {job['far']}"] if job["far"] else []
    given += [f"짚을 것: {job['point']}"] if job.get("point") else []
    return given + [f"그릴 기척: {job['cue']}"]


def make_dm_prompt(job):
    rules = ["플레이어를 \"당신\"이라 부르고 합니다체로 짧은 문장 서너 개만 쓴다. '-세요', '-군요' 같은 해요체는 쓰지 않는다.",
             "플레이어를 이름이나 3인칭으로 부르지 않는다.",
             ("진행자는 세계의 기척을 보여 줄 뿐이고, 무엇을 할지는 플레이어가 고른다. 가 보라, 물어보라, 살펴보라처럼 "
              "권하거나 시키지 않는다." if job["key"] != "conclude" else "결론을 들려 달라는 말만 직접 한다."),
             "지어내는 것은 소리, 빛, 냄새, 몸짓뿐이다. 받은 것에 없는 사람, 물건, 흔적, 벌어진 일은 더하지 않는다.",
             ("인물의 몸짓은 신상, 성격 유형, 지금 하는 일, 태도에서만 짐작한다. 사건의 진실, 단서, 누가 거짓말하는지는 "
              "말하지 않는다."),
             VOICE,
             SHORT,
             "인물의 대사를 지어내지 않는다. 따옴표를 쓰지 않는다.",
             "화면, 단추, 누르는 법은 말하지 않는다.",
             "신상이 플레이어를 이름으로 가리켜도 플레이어는 \"당신\"이라 부른다.",
             "한 문단으로 쓴다."]
    if job.get("point"):
        rules.append("짚을 것은 받은 그대로 쓴다. 따옴표는 쓰지 않는다.")
    return "당신은 추리 TRPG 판을 이끄는 진행자(DM)다.", rules + mood_rule(job), "진행자로서 한마디 한다."


def mood_rule(job):
    # The mood is given too, so the sounds and smells it names pass the check (game/08 5절).
    if not job.get("mood"):
        return []
    # Otherwise gemma4 put the mood's smell into every scene and DM line.
    return [("문체는 분위기를 따른다. 분위기에 나온 냄새와 소리는 바탕일 뿐 글에 옮겨 쓰지 않고, 감각은 이곳의 모습과 일어난 일에서 "
             "고른다. 문장 수는 위의 규칙대로다.")]


def make_answer_prompt(job):
    rules = [f"{job['person']}의 대사만 쓴다. 할 말 하나에 한두 문장이다. 이름, 따옴표, 설명은 붙이지 않는다.",
             SHORT,
             "몸짓, 표정, 행동은 묘사하지 않는다. 입으로 하는 말만 쓴다.",
             ("신상의 말투를 따르고, 성격 유형의 풀이대로 말하는 품과 받아치는 방식을 고른다. 다그치면 어떻게 나오는지, 낯선 사람에게 "
              "얼마나 여는지도 그 풀이를 따른다. 문법에 맞는 한국어로 쓰고, 태도에 맞게 플레이어의 말을 받아친다."),
             "대답 끝에 플레이어에게 되묻거나 재촉하는 짧은 한마디를 붙여도 된다. 받은 것 밖의 일은 묻지도 말하지도 않는다.",
             "플레이어는 지금 마주 보고 말을 건 사람이다. 플레이어에게 직접 말하고, '저 사람', '얘'처럼 남을 가리키듯 부르지 않는다.",
             "할 말이 있으면 그 내용을 빠짐없이 말한다. 태도는 말투에만 드러내고, 모른다고 하거나 피하지 않는다.",
             ("할 말의 뜻을 지킨다. 누가 누구에게 무엇을 했는지, 왜 했는지, 언제 어디서 했는지 그대로 전한다. "
              "인물 이름이 있으면 같은 이름을 써서 서로의 행동이 뒤바뀌지 않게 한다."),
             ("할 말이 없거나 답할 것이 없으면 플레이어의 말 자체에 신상대로 반응한다. 부탁이면 들어주거나 거절하고, "
              "넋두리나 농담이면 맞장구치거나 핀잔하고, 다그치면 발끈하거나 움츠러든다. 사건에 관한 것은 지어내지 않는다."),
             "앞서 나눈 말이 있으면 그 흐름을 이어 받고, 앞서 한 대답을 같은 말로 되풀이하지 않는다. 앞서 한 대답과 같은 부름말이나 첫마디로 시작하지 않는다.",
             "이미 한 말을 다시 물으면 아까 말했다는 투로 짧게 다시 말한다.",
             "지켜본 일이 있으면 그 일을 보고 한마디 얹는다. 곳과 때, 지켜본 일에 없는 일은 더하지 않는다.",
             ("받은 인상과 소문은 말투와 반응에 드러낸다. 여러 번 받은 인상일수록 짙게 드러낸다. 그 일이 언제, 어디서, "
              "어떻게 있었는지는 지어내지 않는다."),
             ("플레이어가 \"~했다면서요?\"처럼 할 말에 없는 일을 사실로 깔고 물으면, 했다고도 안 했다고도 하지 않는다. "
              "그 일을 이어 말하지 말고 누가 그러더냐고 되묻거나 말을 돌린다.")]
    rules += [rule for rule, given in list_answer_rules(job) if given]
    user = f"플레이어: {job['said']}" if job["said"] else "플레이어: (말없이 기다린다)"
    if job.get("hook"):   # the opener calls out as the player comes in
        user = "플레이어: (방금 당신 앞에 왔다)"
    if job.get("saw"):   # in the system prompt alone gemma4 let it pass; next to the line it reacts
        user = f"(플레이어가 방금 {job['person']} 앞에서 한 일: {' / '.join(job['saw'])})\n{user}"
    if job.get("bet") and job["says"]:   # after a typed action gemma4 copied that answer over the line it was given
        user += f"\n(이번에 할 말: {' / '.join(job['says'])})"
    return f"당신은 추리 게임 속 인물 {job['person']}의 목소리다.", rules, user


def list_answer_rules(job):
    """The rules an answer takes only when its job holds what they speak of."""
    leads = ", ".join(f'"{n}"' for n in job.get("leads", []))
    return [
        ("화제의 내용은 한 마디도 말하지 않는다.", job["quiet"]),
        ("플레이어도 아는 일은 플레이어가 꺼낼 때만 받아 말한다. 할 말과 아는 일 말고 사건에 관한 것은 지어내지 않는다.",
         job.get("knows")),
        ("속사정은 말투와 반응에만 묻어나게 한다. 무엇을 감추는지, 거짓말인지는 말하지 않는다.", job.get("inner")),
        (f"운을 떼는 화제의 이름({leads})은 대사에 그대로 넣는다.", leads),
        ("지금 하는 일은 말투와 반응에만 묻어나게 한다.", job.get("doing")),
        ("사건은 당신도 함께 겪는 일처럼 당신의 말로 옮긴다. 사건 글의 '당신'은 플레이어다.", job.get("case")),
        ("첫 대목에 사건의 피해와 조사 기한을 모두 말한다. 그 뒤에 인물이 이번에 할 말을 따로 잇는다.",
         job.get("case") and not job.get("hook")),
        ("할 말은 처음 하는 말이다. 아까 말했다고 하지 않는다.",
         job["lines"] and not set(job["lines"]) & set(job.get("told", []))),
    ]


def make_scene_prompt(job):
    rules = ["플레이어를 \"당신\"이라 부르고 합니다체로 쓴다.",
             "받은 대목과 진실 풀이를 모두 담되 열두 문장을 넘지 않는다." if job["kind"] == "ending"
             else "짧은 문장 너덧 개로 쓴다.",
             "지어내는 것은 날씨, 소리, 빛, 냄새 같은 분위기뿐이다. 받은 것에 없는 사람, 물건, 흔적은 그리지 않는다.",
             "사건의 사실과 결과만 전한다." if job["kind"] == "ending" else VOICE,
             SHORT,
             "분위기는 곳의 모습과 어긋나지 않게 쓴다. '적막', '정적', '어둠' 같은 말을 버릇처럼 넣지 않는다.",
             "한 문단으로 쓴다.",
             ("이번에 눈에 띈 것이 많으면 두드러진 두세 가지만 그린다. 그린 것은 받은 자리와 모양 그대로 쓰고, "
              "여럿을 한 자리에 묶거나 당신이 집어 들었다고 쓰지 않는다.")]
    if job.get("far"):
        rules.append("진행자가 \"그 사이\"로 시작해 다른 곳의 소식을 전하듯 쓴다. 당신은 그 자리에 없으므로 보고 듣는 것처럼 쓰지 않는다.")
    if job["kind"] == "ending":
        rules.extend(["먼저 지목의 결과를 말한다. 그사이 번진 일을 전한 뒤 사건의 진실을 시간 순으로 들려준다.",
                      "지목한 사람과 실제 범인은 주어진 이름으로 각각 부른다. 지목의 결과에서 누가 어떤 일을 겪는지 그대로 전한다.",
                      "사건의 진실에 나온 행동과 원인, 결과를 주어진 그대로 전한다. 옮기는 데 필요한 문장만 쓰고 농담은 넣지 않는다.",
                      "플레이어에게 풀이 점수를 매기거나 맞히고 비운 물음을 언급하지 않는다."])
    if job.get("again"):
        rules.append("이미 와 본 곳이다. 이번에 일어난 일이나 이곳 사람의 지금 모습부터 바로 말한다. "
                     "장소 설명은 한 문장으로 줄인다. 플레이어에게 장소나 상황을 다시 알려 달라고 하지 않는다.")
    if job.get("people"):
        rules.append("마지막 문장에서 이곳에 있는 사람을 이름으로 알린다."
                     + (" 사람이 하는 일은 그 일을 하고 있는 모습으로 그린다." if job.get("doing") else ""))
    head = "당신은 추리 TRPG 판을 이끄는 진행자다." if job["kind"] == "ending" else "당신은 추리 게임의 서술자다."
    return head, rules + mood_rule(job), "결말을 들려준다." if job["kind"] == "ending" else "장면을 들려준다."


def make_checks(job):
    checks = {"added": noul("쓴 글에 받은 것에 없는 사람, 물건, 때, 곳이 나오는가", "나온다", "나오지 않는다")}
    if job["kind"] == "answer" and job["lines"]:
        checks["meaning"] = noul("쓴 글이 할 말의 뜻을 모두 담고, 누가 누구에게 무엇을 했는지를 그대로 옮겼는가",
                                 "모두 옮겼다", "빠졌거나 바뀌었다")
    if job["kind"] == "answer" and job.get("case") and not job.get("hook"):
        checks["case"] = noul("쓴 글이 사건에 적힌 피해와 조사 기한을 둘 다 정확히 알리는가", "둘 다 알린다", "빠졌거나 바뀌었다")
    if job["kind"] == "ending":
        checks["ending"] = noul("쓴 글에서 지목의 결과와 사건의 진실에 나온 사람이 각각 한 일 및 그 결과가 그대로인가",
                                "그대로다", "사람, 한 일 또는 결과가 바뀌었다")
    if job["kind"] == "answer" and job["quiet"]:
        checks["quiet"] = noul("쓴 글이 사건에 관한 내용을 알려 주지 않는가", "알려 주지 않는다", "알려 준다")
    if job["kind"] == "answer" and job.get("outcome"):
        checks["outcome"] = noul(f"쓴 글에서 말하는 사람이 {job['outcome']} 티가 나는가", "난다", "나지 않는다")
    return checks


def noul(instructions, yes, no):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


def judge(job, answers, text):
    probs = {key: answers[key]["noul"] for key in make_checks(job)}
    least = {"added": ADDED, "meaning": MEANING, "case": MEANING, "ending": MEANING, "quiet": QUIET, "outcome": OUTCOME}
    failed = [key for key, p in probs.items() if (1 - p if key == "added" else p) < least[key]]
    if job["kind"] == "answer" and "meaning" not in failed and any(cover(line, text) < COVER for line in job["lines"]):
        failed.append("meaning")
    return failed + list_faults(job, text), probs


def cover(say, text):
    letters = set(re.sub(r"[^가-힣]", "", say))
    return len(letters & set(text)) / len(letters) if letters else 1


def list_faults(job, text):
    kind, unquoted, sentences = job["kind"], QUOTED.sub("", text), split_sentences(text)
    told_first = kind == "answer" and job.get("lines") and not set(job["lines"]) & set(job.get("told", []))
    faults = {
        "length": len(sentences) > MAX_SENTENCES[kind] + 2 * max(0, len(job.get("lines", [])) - 1),
        "long": any(len(s) > LONG for s in sentences),
        "prompt": any(word in text for word in PROMPT_WORDS) or (kind == "scene" and SCENE_REQUEST.search(text)),
        "bracket": BRACKET.search(text),
        "style": kind != "answer" and (HAEYO.search(unquoted) or PLAIN.search(unquoted)),
        "push": kind == "dm" and job.get("key") not in ("conclude", "ready") and PUSH.search(unquoted),
        "speech": kind == "dm" and re.search("[\"“”‘’]", text),
        "lead": any(name.replace(" ", "") not in text.replace(" ", "") for name in job.get("leads", [])),
        "repeat": any(SequenceMatcher(None, r["answer"], text).ratio() >= REPEAT for r in job.get("recent", [])),
        "again": told_first and AGAIN.search(text),
        "unknown": names_unknown(job, text),
    }
    return [name for name, found in faults.items() if found]


def names_unknown(job, text):
    named = [name for name in job.get("unknown", []) if name in text]
    given = "\n".join(list_given(job)) + (job.get("said") or "") if named else ""
    return any(name not in given for name in named)


def split_sentences(text):
    # A trailing-off "그... 그래요" is one sentence, so an ellipsis ends none
    return [s for s in re.split(r"(?<=[^.…][.!?])\s+", text.strip()) if s]

