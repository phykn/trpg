from __future__ import annotations

import asyncio
import random
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import pairwise

from .lang.claims import accepts, claims, subjects
from .lang.context import fact_line, render, scene
from .lang.polite import QUOTED, plain, polite
from .locale import ko
from .models.decision import ModelUnavailable, choice, probs_of
from .onto.atoms import PLAYER
from .onto.view import Obs
from .view import name

ATTEMPTS = 3                 # one draft and two rewrites
SENTENCES, CHARS = 4, 200
SHORT_CHARS, RECAP_CHARS, RECAP_SENTENCES = 160, 100, 2
GROWN_SENTENCES, GROWN_CHARS = 2, 100
# A greeting got four sentences that opened on scenery (qa_test/runs/typed-1/base-summary.md); engine.md 5.2.
REPLY_SIZE = {"talk": (3, 150), "muse": (2, 110)}
TAG_CHARS = 12
MAX_TOKENS = 500
THETA_N = 0.5
REPEAT_CHARS = 10                    # about three words: shorter shared stretches are ordinary phrasing

TAG_LINE = re.compile(r"['\"“]?태그\s*[:：]\s*([^\n'\"”]+?)['\"”]?\s*(?=$|\n)")
ECHO = re.compile(r"^\s*\[[^\]\n]{1,20}\]")
ADDRESS = re.compile("(?<![가-힣])(" + "|".join(ko.ADDRESS) + r")(?=\s*[,!?…~.\"”]|$)")
PAREN = re.compile(r"[()（）]")
# Markdown emphasis reached the screen as "\*컥\*" (qa_test/runs/play-4-talker 24); a bullet's "* " stays for the list check.
EMPHASIS = re.compile(r"\\(?=[*_`])|\*+(?=\S)|(?<=\S)\*+|`+")
LIST_LINE = re.compile(r"^\s*(?:[-•*]|\d+[.)]|[①-⑩])\s")
HAN = re.compile(r"[㐀-鿿Ѐ-ӿ]|[A-Za-z]{2,}")
DIGIT = re.compile(r"[0-9０-９]")
SECOND = re.compile(r"(?<![가-힣])(너|너의|너는|너를|너에게|네가|그대|자네|플레이어)(?![가-힣])")
# A quoted line stays inside its sentence, so dialogue counts, checks and drops as one sentence.
SENTENCE = re.compile(r"(?:\"[^\"]*\"|“[^”]*”|[^.?!…])+(?:[.?!…]+[\"'”’]?|$)")


@dataclass
class Job:
    """Everything one narration reads: the narrator never reads S, and acceptance reads only V (engine.md 5.1)."""
    u: object
    o: Obs
    p: dict                          # presentation, read only: tag names and previous narration
    happened: list[str]
    delta: list[str]                 # change lines alone: the fallback when every sentence is dropped
    focus: set
    text: str | None = None
    tags: list[dict] = field(default_factory=list)   # new tags: {slot, owner, name (default)}
    previous: list[str] = field(default_factory=list)
    ending: str | None = None
    chars: int = CHARS
    sentences: int = SENTENCES
    task: str | None = None          # a recap's task line instead of the turn
    speakers: list[str] = field(default_factory=list)   # people here that this turn's actions name
    left: dict[str, str] = field(default_factory=dict)   # companions this turn left behind: person → place
    joined: tuple[str, ...] = ()     # people who began to follow the player this turn
    unfinished: str | None = None    # the sentence's next action when the turn stopped before it ("" when unnamed)
    grown: bool = False              # the turn only spent growth
    progress: dict[str, bool] = field(default_factory=dict)   # obstacles this turn moved forward: id → overcome
    blocked: tuple[str, ...] = ()    # labels of steps something hidden stopped
    struck: tuple[str, ...] = ()     # clocks and threats that came to pass this turn
    missed: tuple[str, ...] = ()     # deadlines that ran out this turn
    relied: tuple[str, ...] = ()     # what this turn's rolls leaned on
    looked: tuple[str, ...] = ()     # things and obstacles this turn looked at
    asked: tuple[tuple[str, ...], ...] = ()   # choice names of the forks that came this turn; engine.md 5.2
    reply: str = "act"               # act, talk (only small talk) or muse (only try(player)); engine.md 5.2
    said: dict = field(default_factory=dict)   # speaker → [(player sentence, [their lines])] before previous; 5.1
    shared: dict = field(default_factory=dict)  # speaker → step lines of what they lived through with you; 5.1
    hint: tuple[str, str] | None = None   # a muse's way forward: (action, its button label); 5.2
    arrived: bool = False            # the player came to this place this turn: its scenery is new
    paced: tuple[str, ...] = ()      # clocks and deadlines whose pace word this turn changed


def sentences_of(text: str) -> list[str]:
    out: list[str] = []
    for s in SENTENCE.findall(" ".join(text.split())):
        s = s.strip()
        # A bare quoted line belongs to the sentence that says who speaks it.
        if out and QUOTED.fullmatch(s):
            out[-1] += " " + s
        elif s:
            out.append(s)
    return out


def repeated(sentence: str, previous: list[str], story: list[str] = (), who: list[str] = ()) -> str | None:
    """The longest stretch, spaces aside, that this sentence copies from recent narration, if long enough once the
    story's own wording, names and 당신 are left out: those say what the story wrote and who, not how, and counted,
    "\"윤슬이 고개를 저으며 당신" and a person's 아는 것 retold were sent back for rewriting (qa_test/runs/loop-1)."""
    a, b = squash(sentence), squash(" ".join(previous))
    blocks = SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    for m in sorted(blocks, key=lambda m: -m.size):
        if m.size < REPEAT_CHARS:
            break
        span = a[m.a:m.a + m.size]
        if len(own(span, story, who)) >= REPEAT_CHARS:
            return span
    return None


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def own(span: str, story: list[str], who: list[str]) -> str:
    """What is left of a span without punctuation, names and 당신, and without any stretch of 4+ characters it
    shares with the story's wording."""
    rest = re.sub(r"[^\w]", "", span)
    for w in sorted((squash(w) for w in who), key=len, reverse=True):
        rest = rest.replace(w, "")
    for t in story:
        while (m := SequenceMatcher(None, rest, t, autojunk=False).find_longest_match(0, len(rest), 0, len(t))).size >= 4:
            rest = rest[:m.a] + rest[m.a + m.size:]
    return rest


def either(names) -> str:
    return " 또는 ".join(f"'{n}'" for n in names)


def change_line(u, c: dict) -> str | None:
    k = c["kind"]
    if k == "fill":
        done = c["to"] >= u.boxes(c["id"])
        return ko.fill(ko.CHANGE["fill_done" if done else "fill" if c["to"] > c["from"] else "fill_back"], name=c["name"])
    if k == "clock" and c["to"] < c["from"]:
        return ko.fill(ko.CHANGE["recede"], name=c["name"])
    if k == "arrival" and c["id"].startswith("deadline."):
        return ko.fill(ko.CHANGE["deadline"], name=c["name"])
    if k == "fork":
        return ko.fill(ko.CHANGE["fork"], choices=either(c["choices"]))
    if k in ("clock", "crisis", "arrival", "chapter", "ending"):
        return ko.fill(ko.CHANGE[k], name=c["name"])
    if k in ("tag_add", "tag_remove"):
        owner = name(u, c["owner"])
        agent = k == "tag_add" and (c["owner"] == PLAYER or u.kind(c["owner"]) == "agent")
        return ko.fill(ko.CHANGE["tag_add_agent" if agent else k], owner=owner, name=c["name"])
    if k == "scar":
        return ko.fill(ko.CHANGE["scar"], name=c["name"])
    if k == "wound":
        return ko.CHANGE["wound_up" if c["to"] > c["from"] else "wound_down"]
    if k == "move":
        to = c["to"]
        if to == PLAYER or u.kind(to) == "agent":
            return ko.fill(ko.CHANGE["move_get"], to=c["to_name"], name=c["name"])
        if c["from"] == PLAYER:
            return ko.fill(ko.CHANGE["move_lose"], **{"from": ko.YOU}, name=c["name"])
        return ko.fill(ko.CHANGE["move_with" if c.get("with") else "move_place"], name=c["name"], to=c["to_name"])
    if k == "follow":
        # Agreeing to come while still avoiding a place read as a broken promise at the next move card
        # (play-3-talker 27, 32; play-3-explorer 21).
        avoids = c["state"] == "start" and u.agents[c["id"]].avoids
        if avoids:
            return ko.fill(ko.CHANGE["follow_start_bounded"], name=c["name"], places=", ".join(map(u.name, avoids)))
        return ko.fill(ko.CHANGE[f"follow_{c['state']}"], name=c["name"])
    if k == "reveal":
        return ko.fill(ko.CHANGE["reveal"], text=c["text"]) if c.get("text") else \
            ko.fill(ko.CHANGE["reveal_hidden"], name=c["name"])
    if k == "link":
        return ko.fill(ko.CHANGE["link_open" if c["open"] else "link_close"], name=c["name"])
    if k == "regards":
        return ko.fill(ko.CHANGE["regards_up" if c["to"] > c["from"] else "regards_down"], name=c["name"])
    if k == "promise":
        if c["state"] == "made":
            key = "promise_made" if c["owes"] == "promise" else "kindness_made"
            return ko.fill(ko.CHANGE[key], name=c["name"], promise=c["promise"])
        return ko.fill(ko.CHANGE[f"promise_{c['state']}"], name=c["name"])
    return None


def change_lines(u, changes: list[dict]) -> list[str]:
    """A way cut both ways is one line: "등대 앞으로 가는 길이 끊겼습니다" read oddly while standing there
    (qa_test/runs/play-4-talker 40)."""
    links = {(c["from"], c["to"], c["open"]) for c in changes if c["kind"] == "link"}
    out = []
    for c in changes:
        if c["kind"] == "link" and (c["to"], c["from"], c["open"]) in links:
            if c["from"] < c["to"]:
                out.append(ko.fill(ko.CHANGE["between_open" if c["open"] else "between_close"],
                                   a=u.name(c["from"]), b=c["name"]))
        elif line := change_line(u, c):
            out.append(line)
    return out


def step_lines(u, record: dict) -> tuple[list[str], list[str]]:
    result = ko.RESULTS.get(record["result"], "")
    head = ko.fill(ko.STEP_LINE, label=record["label"], result=result) if result else record["label"]
    changes = change_lines(u, record["changes"])
    return [head, *changes], changes


def change_ids(record: dict) -> set:
    return {c[k] for c in record["changes"] for k in ("id", "owner", "to", "from") if isinstance(c.get(k), str)}


def forbidden(u, o: Obs) -> dict[str, str]:
    seen = set(o.seen)
    hidden = {x for x in u.shows if x not in seen}
    hidden |= {b for lat in u.latents.values() for b in lat.brings if b not in seen}
    return {w: x for x in hidden for w in u.terms(x) if len(w) >= 2}


def absent(job: Job) -> set:
    """A recap tells past scenes, so everyone may act in it. A change naming someone elsewhere (their regard, a thing
    they got) does not bring them here."""
    if job.task:
        return set()
    u, o = job.u, job.o
    return {x for x in u.agents if o.facts.where(x) != o.here or o.here is None}


def legacy(u, o: Obs) -> list[tuple]:
    """What the player leaves behind for the ending to pick up: trust that moved with someone they met, debts,
    things they saw go to someone, and companions. Without them every ending was one or two lines about the lamp
    (qa_test/runs/play-1-talker 30, 46). Met and handed over come from memory: at the ending those people are
    rarely in sight (play-2-talker 48)."""
    met = {w for s in o.memory for w in s.witnesses if w in u.agents}
    last = {a[1]: a for s in o.memory for a in sorted(s.delta.add, key=str) if a[0] == "at" and a[1] in u.things}

    def left(a) -> bool:
        if a[0] == "regards":
            return a[2] == PLAYER and a[3] == "trust" and a[1] in met and a[4] != u.agents[a[1]].regards.get("trust", 0)
        if a[0] == "owes":
            return PLAYER in a[1:3]
        return a[0] == "follows"
    out = [a for a in o.facts.atoms() if left(a)]
    out += [a for a in last.values() if a[2] in u.agents and u.things[a[1]].at != a[2]]
    return sorted(out, key=lambda a: (a[0], str(a[1:])))


def parting(job: Job, x: str, sentence: str) -> bool:
    """Someone left behind this turn may stand in a sentence that tells the parting."""
    return x in job.left and any(w in sentence for w in (*ko.PARTING, job.u.name(job.left[x])))


def afar(job: Job, x: str, sentence: str) -> bool:
    """At the ending, someone the legacy names may stand in a sentence set far off. Without the distance word they
    were put beside the player or on the wrecked boat (qa_test/runs/play-2-reending-2.txt)."""
    return (bool(job.ending) and any(w in sentence for w in ko.AFAR)
            and any(x in a[1:3] for a in legacy(job.u, job.o)))


def legacy_lines(job: Job) -> list[str]:
    """Each person the legacy names away from here also gets where they are: told only what they hold or feel,
    the narrator set them beside the player and every attempt failed (qa_test/runs/narr-3/refactor-after 16)."""
    u, o = job.u, job.o
    kept = legacy(u, o)
    out = [x for a in kept if (x := fact_line(u, job.p, a))]
    gone = absent(job)
    for x in dict.fromkeys(y for a in kept for y in a[1:3] if y in gone):
        place = o.facts.where(x)
        out.append(ko.fill(ko.AWAY["place" if place in o.seen else "unknown"], name=u.name(x),
                           place=u.name(place) if place in o.seen else ""))
    return out


WORD = re.compile(r"[가-힣]+")
WORN = 3


def pairs(text: str) -> dict[tuple[str, str], str]:
    """Two-word phrases within a sentence, keyed loosely so 집어삼킬 듯/듯한 count as one."""
    out = {}
    for sent in re.split(r"[.?!…\"“”]", text):
        ws = WORD.findall(sent)
        for a, b in pairwise(ws):
            if len(a) >= 2:
                out.setdefault((a[:2], b[:1]), f"{a} {b}")
    return out


def names_of(u) -> list[str]:
    return [n for x in (*u.places, *u.agents, *u.things, *u.obstacles) for n in u.terms(x)]


def story_wording(u) -> list[str]:
    """The story's text that the narrator's context lists: senses, looks and what people know."""
    texts = [*(c for q in u.places.values() for c in q.senses), *(k for a in u.agents.values() for k in a.knows),
             *(x.look for x in (*u.things.values(), *u.obstacles.values()) if x.look)]
    return [re.sub(r"[^\w]", "", t) for t in texts]


def worn(u, previous: list[str]) -> list[str]:
    """Phrases in two of the recent narrations. Below the repetition check's 10 characters, "집어삼킬 듯" came back in
    nearly every turn (qa_test/runs/play-1-*). Part of a name or of a place's senses is the story's wording, and names
    and 당신 alone say who, not how; a phrase that only shares a word with them is the narration's own: when it was
    skipped, "젖은 손" came three turns running (play-5-talker 28–30)."""
    names = names_of(u)
    story = {k for t in (*names, *(c for q in u.places.values() for c in q.senses)) for k in pairs(t)}
    who = {ko.YOU, *(w for n in names for w in n.split() if len(w) >= 2)}
    seen = [pairs(t) for t in previous]
    count: dict = {}
    for d in seen:
        for k in d:
            count[k] = count.get(k, 0) + 1
    latest = {k: v for d in seen for k, v in d.items()}
    twice = [latest[k] for k, n in count.items() if n >= 2 and k not in story]
    return [ph for ph in twice if not all(any(w.startswith(x) for x in who) for w in ph.split())][:WORN]


def fresh_cue(senses: list[str], previous: list[str]) -> str | None:
    """The first sensory cue of the place that recent narration has not yet shown, if any."""
    seen = [squash(t) for t in previous]

    def shown(cue: str) -> bool:
        c = squash(cue)
        grams = {c[i:i + 2] for i in range(len(c) - 1)}
        return any(sum(g in t for g in grams) * 2 >= len(grams) for t in seen)
    return next((c for c in senses if not shown(c)), None)


def steering(job: Job, lines) -> list[str]:
    u, out = job.u, []
    for x in job.speakers:
        a = u.agents[x]
        out.append(ko.fill(ko.NOW["speaker"], x=a.name, persona=ko.PERSONAS[a.persona], voice=a.voice))
    for x, q in job.left.items():
        out.append(ko.fill(ko.NOW["left"], name=u.name(x), place=u.name(q), fear=u.agents[x].fear.rstrip(".")))
    for x in job.joined:
        if avoids := u.agents[x].avoids:
            out.append(ko.fill(ko.NOW["bounded"], name=u.name(x), places=", ".join(map(u.name, avoids)),
                               fear=u.agents[x].fear.rstrip(".")))
    if job.grown:
        # A growth pick is a menu choice; told as a turn, it replayed the last scene or only the scenery
        # (qa_test/runs/play-3-talker 24, play-3-explorer 30, play-3-bold 7).
        return [f"- {x}" for x in (*out, ko.NOW["grown"])]
    tired = worn(u, job.previous)
    if job.ending:
        # The usual cue, pace and close ("end on someone's reaction") outweighed the frame, so no ending told
        # whether the boats came home, and with a cue the legacy never fit in 160 characters (play-2-explorer 44,
        # play-2-talker 48).
        kept = legacy_lines(job)
        if tired:
            out.append(ko.fill(ko.NOW["worn"], words=", ".join(tired)))
        if kept:
            out.append(ko.fill(ko.NOW["legacy"], items=" / ".join(kept)))
        close = ko.fill(ko.NOW["ending_legacy" if kept else "ending"], frame=job.ending)
        return [*(f"- {x}" for x in out), f"- {close}"]
    if job.reply != "act":
        # Small talk and musing change nothing, so no place cue, pace or close: the reply opens on the person
        # (engine.md 5.2).
        names = ", ".join(u.name(x) for x in job.speakers)
        reply = ko.fill(ko.NOW[job.reply], names=names) if names or job.reply == "talk" else ko.NOW["muse_alone"]
        if tired:
            out.append(ko.fill(ko.NOW["worn"], words=", ".join(tired)))
        if job.text and names:
            out.append(ko.fill(ko.NOW["presumed"], names=names))
        hint = [ko.fill(ko.NOW["hint" if names else "hint_alone"], hint=job.hint[1], names=names)] if job.hint else []
        return [*(f"- {x}" for x in [*out, *kept_word(job)]), f"- {reply}", *(f"- {x}" for x in hint)]
    here = job.o.facts.where(PLAYER)
    # Asked for people where nobody stood, the narrator brought back whoever the last turns told (qa_test/runs/narr-3/
    # ending-after game 0, 12–15).
    alone = "" if any(job.o.facts.where(x) == here for x in u.agents) else "_alone"
    # Scenery and time are told when they change; asked every turn, the weather filled every narration (engine.md 5.1).
    cue = fresh_cue(list(u.places[here].senses), job.previous) if job.arrived and here in u.places else None
    out.append(ko.fill(ko.NOW["cue"], cue=cue) if cue else ko.NOW["no_cue" + alone])
    pace = [ln.text for ln in lines if ln.atom and ln.atom[0] == "fill" and ln.atom[1] in job.paced]
    if pace:
        out.append(ko.fill(ko.NOW["pace"], text=", ".join(pace)))
    elif not (job.struck or job.missed):
        # Without it the story's style ("어두워지는 하늘로 시간이 흐르는 것") still filled half the sentences
        # (qa_test/runs/loop-1/weather-after).
        out.append(ko.NOW["still" + alone])
    # A lamp at 1/4 already pushed back the dark (qa_test/runs/play-2-bold 6–7, play-4-odd 28).
    for x, done in job.progress.items():
        out.append(ko.fill(ko.NOW["done" if done else "partial"], name=u.name(x)))
    # A bridge collapse and a missed sunset went untold behind the turn's other changes (qa_test/runs/play-4-talker 28,
    # 40; play-4-odd 29; play-4-explorer 29).
    if job.struck:
        out.append(ko.fill(ko.NOW["struck"], names=", ".join(job.struck)))
    if job.missed:
        out.append(ko.fill(ko.NOW["missed"], names=", ".join(job.missed)))
    for names in job.asked:
        out.append(ko.fill(ko.NOW["asked"], choices=either(names)))
    # A blocked talk was still answered in full, so the testers could not tell what had stopped it
    # (qa_test/runs/play-4-explorer 10, play-4-talker 21).
    for label in job.blocked:
        out.append(ko.fill(ko.NOW["blocked"], label=label))
    # A leaned-on letter never appeared in the prose (qa_test/runs/play-4-talker 6, play-4-odd 4).
    for x in job.relied:
        out.append(ko.fill(ko.NOW["relied"], rely=x))
    # A letter was read and none of its words were told; its look sat among every other entity's (qa_test/runs/
    # play-5-talker 35).
    for x in job.looked:
        if text := (u.things[x].look if x in u.things else u.obstacles[x].look if x in u.obstacles else ""):
            out.append(ko.fill(ko.NOW["looked"], name=u.name(x), text=text))
    # The player's sentence reaches the narrator whole, so a look before a roll card was told as the lamp already lit
    # (qa_test/runs/play-3-odd 18, play-3-explorer 41).
    if job.unfinished is not None:
        out.append(ko.fill(ko.NOW["waits"], label=job.unfinished) if job.unfinished else ko.NOW["waits_rest"])
    # A question to 도해 became a failed detour roll, and he answered it anyway (qa_test/runs/loop-1/detour.json).
    if job.text and (silent := [x for x in sorted(job.o.seen, key=u.rank) if x in u.agents and x not in job.speakers
                                and job.o.facts.where(x) == here]):
        out.append(ko.fill(ko.NOW["unaddressed"], names=", ".join(map(u.name, silent))))
    if tired:
        out.append(ko.fill(ko.NOW["worn"], words=", ".join(tired)))
    close = ko.NOW["close_asked"] if job.asked else ko.NOW["close" + alone]
    return [*(f"- {x}" for x in [*out, *kept_word(job)]), f"- {close}"]


def kept_word(job: Job) -> list[str]:
    out = [ko.fill(ko.NOW["shared"], names=", ".join(job.u.name(x) for x in job.shared))] if job.shared else []
    return out + ([ko.fill(ko.NOW["said"], names=", ".join(job.u.name(x) for x in job.said))] if job.said else [])


def shared_lines(job: Job) -> list[str]:
    return [f"- {ko.fill(ko.SHARED_LINE, x=job.u.name(x), line=line)}" for x, lines in job.shared.items() for line in lines]


def spoken(u, speakers: list[str], said: list[str]) -> dict[str, list[str]]:
    """Each quote goes to the speaker its sentence names, or to the only speaker when it names no one (engine.md 6)."""
    out: dict[str, list[str]] = {}
    for s in said:
        quotes = [q[1:-1] for q in QUOTED.findall(s)]
        if not quotes:
            continue
        bare = QUOTED.sub(" ", s)
        named = [x for x in u.agents if any(w in bare for w in u.terms(x))]
        who = [x for x in named if x in speakers] if named else speakers
        if len(who) == 1:
            out.setdefault(who[0], []).extend(quotes)
    return out


def messages(job: Job, draft: list[str] | None = None, problems: list[str] | None = None) -> list[dict]:
    u = job.u
    system = ko.fill(ko.NARRATOR, sentences=job.sentences, chars=job.chars)
    lines = scene(u, job.o, job.focus, job.p)
    blocks = [ko.HEAD["context"], render(lines)]
    if job.task:
        blocks += ["", ko.HEAD["notable"], job.task, *(f"- {x}" for x in job.happened)]
    else:
        blocks += ["", ko.HEAD["happened"], *(f"- {x}" for x in job.happened)]
        if job.shared:
            blocks += ["", ko.HEAD["shared"], *shared_lines(job)]
        if job.said:
            blocks += ["", ko.HEAD["said"], *(f"- {ko.fill(ko.SAID_LINE if t else ko.SAID_ALONE, text=t, x=u.name(x),
                                                             lines=' '.join(q))}"
                                               for x, rows in job.said.items() for t, q in rows)]
        if job.previous:
            blocks += ["", ko.HEAD["previous"], *job.previous]
        if job.text:
            blocks += ["", ko.HEAD["player"], job.text]
        if job.ending:
            blocks += ["", ko.HEAD["ending"], ko.fill(ko.ENDING_FRAME, frame=job.ending)]
        if job.tags:
            blocks += ["", ko.HEAD["tags"], ko.fill(ko.NAMING, names=", ".join(t["name"] for t in job.tags))]
    if u.style:
        blocks += ["", ko.STYLE, u.style.strip()]
    if not job.task:
        blocks += ["", ko.HEAD["now"], *steering(job, lines)]
    if draft:
        blocks += ["", ko.HEAD["feedback"], ko.REWRITE, *(f"- {s}" for s in draft), *problems]
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(blocks)}]


def split(raw: str) -> tuple[str, list[str]]:
    """An echoed prompt header ends the text."""
    lines, names = [], []
    for line in raw.splitlines():
        if ECHO.match(line):
            break
        for m in TAG_LINE.finditer(line):
            names.append(m[1].strip().rstrip("."))
        line = EMPHASIS.sub("", TAG_LINE.sub("", line)).strip()
        if line:
            lines.append(line)
    return polite(" ".join(lines)), names


class Narrator:
    def __init__(self, llm, decision, theta: float = THETA_N, timeout: float = 60.0, check_timeout: float = 10.0):
        self.llm, self.decision, self.theta = llm, decision, theta
        self.timeout, self.check_timeout = timeout, check_timeout

    async def write(self, job: Job, draft=None, problems=None) -> str:
        async def run():
            out = ""
            async for chunk in self.llm.stream(messages(job, draft, problems), MAX_TOKENS,
                                                seed=random.randrange(2**31)):
                out += chunk
            return out
        return await asyncio.wait_for(run(), self.timeout)

    def rules(self, job: Job, said: list[str]) -> tuple[dict[int, list[str]], list[str]]:
        u, facts = job.u, job.o.facts
        bad = forbidden(u, job.o)
        gone = absent(job)
        story, who = story_wording(u), [ko.YOU, *names_of(u)]
        per: dict[int, list[str]] = {}
        for i, s in enumerate(said):
            bare = QUOTED.sub(" ", s)
            why = []
            if plain(s):
                why.append(ko.FEEDBACK["plain"])
            if SECOND.search(bare):
                why.append(ko.FEEDBACK["you"])
            if LIST_LINE.match(s):
                why.append(ko.FEEDBACK["list"])
            if DIGIT.search(s) or any(w in bare for w in ko.RULE_WORDS):
                why.append(ko.FEEDBACK["number"])
            if PAREN.search(s):
                why.append(ko.FEEDBACK["paren"])
            if HAN.search(s):
                why.append(ko.FEEDBACK["foreign"])
            hidden = [w for w in bad if w in s]
            if hidden:
                why.append(ko.fill(ko.FEEDBACK["hidden"], names=", ".join(hidden)))
            away = [x for x in subjects(u, bare) if x in gone and not parting(job, x, bare) and not afar(job, x, bare)]
            if away:
                # at the ending the plain verdict left no way to keep the person, so drafts kept them beside the player
                key = "afar" if job.ending and all(afar(job, x, ko.AFAR[0]) for x in away) else "absent"
                why.append(ko.fill(ko.FEEDBACK[key], names=", ".join(u.name(x) for x in away)))
            wrong = [(pos, atom) for pos, atom in claims(u, s) if not accepts(facts, pos, atom)]
            for pos, atom in wrong:
                if atom[0] == "at" and atom[1] == PLAYER:
                    why.append(ko.fill(ko.FEEDBACK["where"], place=u.name(facts.where(PLAYER))))
                elif atom[0] == "at" and atom[1] in u.things and atom[2] == PLAYER:
                    key = "unearned" if pos else "handed"
                    why.append(ko.fill(ko.FEEDBACK[key], names=u.name(atom[1])))
                else:
                    why.append(ko.fill(ko.FEEDBACK["claim"], facts=s))
            span = repeated(s, job.previous + [q for x in job.speakers for q in QUOTED.findall(u.agents[x].voice)]
                            + [q for rows in job.said.values() for _, qs in rows for q in qs], story, who)
            if span:
                why.append(ko.fill(ko.FEEDBACK["repeat"], span=span))
            for q in QUOTED.findall(s):
                for m in ADDRESS.finditer(q):
                    why.append(ko.fill(ko.FEEDBACK["address"], word=m[1]))
            if why:
                per[i] = why
        whole = []
        if len(said) > job.sentences:
            whole.append(ko.fill(ko.FEEDBACK["sentences"], n=job.sentences))
        if len(" ".join(said)) > job.chars:
            whole.append(ko.fill(ko.FEEDBACK["chars"], n=job.chars))
        return per, whole

    def tag_names(self, job: Job, names: list[str]) -> list[dict]:
        bad = forbidden(job.u, job.o)
        out = []
        for i, t in enumerate(job.tags):
            given = names[i] if i < len(names) else ""
            ok = 0 < len(given) <= TAG_CHARS and not any(w in given for w in bad) and not DIGIT.search(given)
            out.append({**t, "name": given if ok else t["name"]})
        return out

    async def judge(self, job: Job, said: list[str], skip: set[int]) -> dict[int, list[str]]:
        state = render(scene(job.u, job.o, job.focus, job.p))
        if job.shared:
            state += "\n" + "\n".join([ko.HEAD["shared"], *shared_lines(job)])
        if job.happened:
            state += "\n" + ko.HEAD["happened"] + "\n" + "\n".join(f"- {x}" for x in job.happened)
        if job.ending:
            kept = legacy_lines(job)
            state += "\n" + "\n".join([ko.HEAD["ending"], job.ending, *(f"- {x}" for x in kept)])
        qs = {}
        for i, s in enumerate(said):
            if i not in skip:
                qs[str(i)] = choice(ko.fill(ko.CHECK_QUESTION, text=s), ko.CHECK)
        if not qs:
            return {}
        try:
            answers = await asyncio.wait_for(self.decision.decide(state, qs), self.check_timeout)
        except (ModelUnavailable, TimeoutError):
            answers = {}
        out: dict[int, list[str]] = {}
        for i in qs:
            probs = probs_of(answers.get(i))
            # An unreadable check answer cannot clear a sentence.
            if probs.get("fine", 0.0) > 1 - self.theta:
                continue
            flaws = [k for k in ("contradicts", "invents") if k in probs]
            worst = max(flaws, key=lambda k: probs[k]) if flaws else None
            out[int(i)] = [ko.FEEDBACK[worst]] if worst else [ko.FEEDBACK[k] for k in ("contradicts", "invents")]
        return out

    async def narrate(self, job: Job) -> AsyncIterator[dict]:
        """The last event is always {"type": "result", ...} or {"type": "error"} (api.md 4)."""
        draft, problems, last = None, None, None
        for attempt in range(1, ATTEMPTS + 1):
            yield {"type": "stage", "stage": "writing"} if attempt == 1 else \
                {"type": "stage", "stage": "rewriting", "attempt": attempt}
            try:
                raw = await self.write(job, draft, problems)
            except (ModelUnavailable, TimeoutError, OSError):
                continue
            text, names = split(raw)
            said = sentences_of(text)
            if not said:
                continue
            yield {"type": "stage", "stage": "checking"}
            per, whole = self.rules(job, said)
            per2 = await self.judge(job, said, set(per))
            for i, why in per2.items():
                per.setdefault(i, []).extend(why)
            # The kept draft is the one with the fewest bad sentences, so a worse rewrite cannot replace it.
            if last is None or len(per) <= len(last[1]):
                last = (said, per, names)
            if not per and not whole:
                yield self.result(job, said, attempt, 0, names)
                return
            draft = [said[i] for i in sorted(per)] or said
            problems = [w for i in sorted(per) for w in per[i]] + whole
        if last is None:
            yield {"type": "error", "message": ko.NARRATION_ERROR}
            return
        said, per, names = last
        kept = [s for i, s in enumerate(said) if i not in per]
        while kept and (len(kept) > job.sentences or len(" ".join(kept)) > job.chars):
            kept.pop()
        dropped = len(said) - len(kept)
        if not kept:
            kept = list(job.delta) or [ko.NOTHING_CHANGED]
        yield self.result(job, kept, ATTEMPTS, dropped, names)

    def result(self, job: Job, said: list[str], attempts: int, dropped: int, names: list[str]) -> dict:
        return {"type": "result", "text": " ".join(said), "attempts": attempts, "dropped": dropped,
                "tags": self.tag_names(job, names), "said": spoken(job.u, job.speakers, said),
                "hint": job.hint and job.hint[0]}


__all__ = ["Job", "Narrator", "change_ids", "change_line", "change_lines", "messages", "sentences_of", "split", "step_lines"]
