from __future__ import annotations

import asyncio
import random
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .lang.claims import accepts, claims, mentioned, subjects
from .lang.context import render, scene
from .lang.polite import QUOTED, plain, polite
from .locale import ko
from .models.decision import ModelUnavailable
from .onto.atoms import PLAYER
from .onto.view import Obs

ATTEMPTS = 3                 # one draft and two rewrites
SENTENCES, CHARS = 4, 200
SHORT_CHARS, RECAP_CHARS, RECAP_SENTENCES = 160, 100, 2
TAG_CHARS = 12
MAX_TOKENS = 500
THETA_N = 0.5
REPEAT_CHARS = 10                    # about three words: shorter shared stretches are ordinary phrasing

TAG_LINE = re.compile(r"['\"“]?태그\s*[:：]\s*([^\n'\"”]+?)['\"”]?\s*(?=$|\n)")
ECHO = re.compile(r"^\s*\[[^\]\n]{1,20}\]")
ADDRESS = re.compile("(?<![가-힣])(" + "|".join(ko.ADDRESS) + r")(?=\s*[,!?…~.\"”]|$)")
PAREN = re.compile(r"[()（）]")
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


def repeated(sentence: str, previous: list[str]) -> str | None:
    """The longest stretch, spaces aside, that this sentence copies from recent narration, if long enough."""
    a, b = re.sub(r"\s+", "", sentence), re.sub(r"\s+", "", " ".join(previous))
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size] if m.size >= REPEAT_CHARS else None


def change_line(u, c: dict) -> str | None:
    k = c["kind"]
    if k == "fill":
        done = c["to"] >= u.boxes(c["id"])
        return ko.fill(ko.CHANGE["fill_done" if done else "fill"], name=c["name"])
    if k == "clock" and c["to"] < c["from"]:
        return ko.fill(ko.CHANGE["crisis"], name=c["name"])
    if k in ("clock", "crisis", "arrival", "chapter", "ending"):
        return ko.fill(ko.CHANGE[k], name=c["name"])
    if k in ("tag_add", "tag_remove"):
        owner = "당신" if c["owner"] == PLAYER else u.name(c["owner"])
        return ko.fill(ko.CHANGE[k], owner=owner, name=c["name"])
    if k == "scar":
        return ko.fill(ko.CHANGE["scar"], name=c["name"])
    if k == "wound":
        return ko.CHANGE["wound_up" if c["to"] > c["from"] else "wound_down"]
    if k == "move":
        to = c["to"]
        if to == PLAYER or u.kind(to) == "agent":
            return ko.fill(ko.CHANGE["move_get"], to="당신" if to == PLAYER else c["to_name"], name=c["name"])
        if c["from"] == PLAYER:
            return ko.fill(ko.CHANGE["move_lose"], **{"from": "당신"}, name=c["name"])
        return ko.fill(ko.CHANGE["move_with" if c.get("with") else "move_place"], name=c["name"], to=c["to_name"])
    if k == "follow":
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


def step_lines(u, record: dict) -> tuple[list[str], list[str]]:
    result = ko.RESULTS.get(record["result"], "")
    head = ko.fill(ko.STEP_LINE, label=record["label"], result=result) if result else record["label"]
    changes = [line for c in record["changes"] if (line := change_line(u, c))]
    return [head, *changes], changes


def change_ids(record: dict) -> set:
    return {c[k] for c in record["changes"] for k in ("id", "owner", "to", "from") if isinstance(c.get(k), str)}


def forbidden(u, o: Obs) -> dict[str, str]:
    seen = set(o.seen)
    hidden = {x for x in u.shows if x not in seen}
    hidden |= {b for lat in u.latents.values() for b in lat.brings if b not in seen}
    return {w: x for x in hidden for w in (u.name(x), *u.aliases(x)) if len(w) >= 2}


def absent(job: Job) -> set:
    """A recap tells past scenes, so everyone may act in it."""
    if job.task:
        return set()
    u, o = job.u, job.o
    named = {x for line in job.delta for _, x in mentioned(u, line)}
    return {x for x in u.agents if o.facts.where(x) != o.here or o.here is None} - named


def fresh_cue(senses: list[str], previous: list[str]) -> str | None:
    """The first sensory cue of the place that recent narration has not yet shown, if any."""
    seen = [re.sub(r"\s+", "", t) for t in previous]

    def shown(cue: str) -> bool:
        c = re.sub(r"\s+", "", cue)
        grams = {c[i:i + 2] for i in range(len(c) - 1)}
        return any(sum(g in t for g in grams) * 2 >= len(grams) for t in seen)
    return next((c for c in senses if not shown(c)), None)


def steering(job: Job, lines) -> list[str]:
    u, out = job.u, []
    for x in job.speakers:
        a = u.agents[x]
        out.append(ko.fill(ko.NOW["speaker"], x=a.name, persona=ko.PERSONAS[a.persona], voice=a.voice))
    here = job.o.facts.where(PLAYER)
    cue = fresh_cue(list(u.places[here].senses), job.previous) if here in u.places else None
    out.append(ko.fill(ko.NOW["cue"], cue=cue) if cue else ko.NOW["no_cue"])
    pace = [ln.text for ln in lines if ln.atom and ln.atom[0] == "fill" and ln.atom[1] in u.obstacles
            and u.obstacles[ln.atom[1]].sub in ("clock", "deadline")]
    if pace:
        out.append(ko.fill(ko.NOW["pace"], text=", ".join(pace)))
    return [*(f"- {x}" for x in out), f"- {ko.NOW['close']}"]


def messages(job: Job, draft: list[str] | None = None, problems: list[str] | None = None) -> list[dict]:
    u = job.u
    system = ko.fill(ko.NARRATOR, sentences=job.sentences, chars=job.chars)
    lines = scene(u, job.o, job.focus, job.p)
    blocks = [ko.HEAD["context"], render(lines)]
    if job.task:
        blocks += ["", ko.HEAD["notable"], job.task, *(f"- {x}" for x in job.happened)]
    else:
        blocks += ["", ko.HEAD["happened"], *(f"- {x}" for x in job.happened)]
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
        line = TAG_LINE.sub("", line).strip()
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

    def rules(self, job: Job, said: list[str], names: list[str]) -> tuple[dict[int, list[str]], list[str]]:
        u, facts = job.u, job.o.facts
        bad = forbidden(u, job.o)
        gone = absent(job)
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
            away = [x for x in subjects(u, bare) if x in gone]
            if away:
                why.append(ko.fill(ko.FEEDBACK["absent"], names=", ".join(u.name(x) for x in away)))
            wrong = [(pos, atom) for pos, atom in claims(u, s) if not accepts(facts, pos, atom)]
            for pos, atom in wrong:
                if atom[0] == "at" and atom[1] == PLAYER:
                    why.append(ko.fill(ko.FEEDBACK["where"], place=u.name(facts.where(PLAYER))))
                elif atom[0] == "at" and atom[1] in u.things and atom[2] == PLAYER:
                    key = "unearned" if pos else "handed"
                    why.append(ko.fill(ko.FEEDBACK[key], names=u.name(atom[1])))
                else:
                    why.append(ko.fill(ko.FEEDBACK["claim"], facts=s))
            span = repeated(s, job.previous + [q for x in job.speakers for q in QUOTED.findall(u.agents[x].voice)])
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
            name = names[i] if i < len(names) else ""
            ok = 0 < len(name) <= TAG_CHARS and not any(w in name for w in bad) and not DIGIT.search(name)
            out.append({**t, "name": name if ok else t["name"]})
        return out

    async def judge(self, job: Job, said: list[str], skip: set[int]) -> dict[int, list[str]]:
        state = render(scene(job.u, job.o, job.focus, job.p))
        if job.happened:
            state += "\n" + ko.HEAD["happened"] + "\n" + "\n".join(f"- {x}" for x in job.happened)
        qs = {}
        for i, s in enumerate(said):
            if i not in skip:
                qs[str(i)] = {"type": "choice", "instructions": f"{ko.CHECK_QUESTION}\n문장: {s}", "criteria": ko.CHECK}
        if not qs:
            return {}
        try:
            answers = await asyncio.wait_for(self.decision.decide(state, qs), self.check_timeout)
        except (ModelUnavailable, TimeoutError):
            answers = {}
        out: dict[int, list[str]] = {}
        for i in qs:
            a = answers.get(i)
            probs = dict(a.probabilities) if a is not None and a.probabilities else {}
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
            per, whole = self.rules(job, said, names)
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
                "tags": self.tag_names(job, names)}


__all__ = ["Job", "Narrator", "change_ids", "change_line", "messages", "sentences_of", "split", "step_lines"]
