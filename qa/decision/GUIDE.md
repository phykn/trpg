# Decision-model benchmark: item format and labelling guide

Each genre file `data/<genre>.jsonl` holds one JSON object per line. Korean for all story text. Player-facing narration uses 당신 and 합니다체.

## 1. Sentence items (`"kind": "sentence"`), 36 per genre

```json
{"kind": "sentence", "id": "<genre>-s01", "genre": "<genre>",
 "scene": {
   "place": {"name": "함교", "senses": ["깜빡이는 경고등", "낮게 울리는 엔진음", "식은 커피 냄새"], "rest": false},
   "exits": ["기관실", "격납고"],
   "people": [{"name": "한서진", "aliases": ["부함장"], "look": "…", "voice": "…", "desire": "…", "fear": "…",
               "topics": ["항로 기록"], "favor": "보안 카드를 빌려 달라고 한다", "wants": ["암호 칩"], "trust": 0}],
   "things": [{"name": "암호 칩", "aliases": ["칩"], "look": "…", "where": "player"},
              {"name": "산소통", "aliases": [], "look": "…", "where": "here"}],
   "obstacles": [{"name": "잠긴 격벽", "aliases": ["격벽"], "look": "…", "boxes": 2, "fill": 0}],
   "threats": ["다가오는 보안 드론"],
   "forks": [{"name": "탈출 방법", "options": ["구명정을 띄운다", "본선에 남는다"]}],
   "latents": [{"name": "인연: 옛 동료", "text": "기관실 정비사 마루는 예전에 함께 복무한 동료다"}],
   "claims": ["함장의 명령을 받고 왔다"],
   "player": {"traits": [{"name": "해커", "text": "보안 장치를 다뤄 봤습니다."}],
              "stats": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}},
   "memory": ["어딘가로 간다(함교)"]},
 "text": "부함장에게 항로 기록에 대해 묻는다",
 "gold": {"steps": ["talk"], "detail": {"to": "한서진", "topic": "항로 기록", "tone": "polite", "claim": null}}}
```

- `where` of a thing: `"player"` (carried), `"here"` (lying in this place), or a person's name (that person holds it).
- `favor` is the one thing the person can be asked to do or lend (a label), or null. `wants` lists things the person would welcome.
- `threats`, `forks`, `latents`, `claims`, `memory` may be empty lists. Keep a scene small: 1–3 people, 1–4 things, 0–2 obstacles, 1–3 exits. A scene may be reused by several items (copy it).
- `text` is what a player types. `gold.steps` is the list of 1–3 schemas the sentence asks for, in order. `gold.detail` is the first step's arguments.

### Schemas and their first-step detail

| schema | meaning | detail |
|---|---|---|
| `go` | move to a connected place (one of `exits`) | `{"to": exit}` |
| `look` | observe or read something to learn about it, no attempt to change it; looking around = the place | `{"at": name}` (place, person, thing, obstacle, threat) |
| `take` | pick up a thing lying `here` | `{"thing": name}` |
| `give` | hand a carried thing to a person present | `{"thing": name, "to": person}` |
| `talk` | speak with a person present: about a topic, ask the favor, or just chat | `{"to": person, "topic": topic title \| "favor" \| "chat", "tone": tone, "claim": claim text or null}` |
| `try` | act on an obstacle, person or thing to overcome or change it (a roll); or an action with no target | `{"target": name \| "player", "approach": approach, "strain": strain}` |
| `declare` | the player states a fact about their own past or connections that matches a latent | `{"latent": latent name}` |
| `cut` | let time pass: wait (`pass`) or rest/sleep where `rest` is true (`rest`) | `{"kind": "pass" \| "rest"}` |
| `choose` | pick one option of a fork | `{"fork": name, "option": option label}` |

- **tone** (talk): `polite` asks or requests courteously (the neutral default), `friendly` warm or casual chat, `plead` begs or appeals to feelings, `threaten` intimidates, `deceive` lies. `claim` is set only with `deceive` and only when the lie is one of the scene's `claims`.
- **approach** (try): `force` push, break, endure; `finesse` delicate hands, agility, stealth; `wits` observe, plan, trick, distract; `charm` win someone over with words or manner.
- **strain** (try): `natural` doable here, `forced` doable but reckless or overexerting ("무리해서", "온몸으로", "억지로"), `impossible` cannot be done in this scene's world (flying without means, magic in a world without it).
- `try` with target `"player"`: an action aimed at nobody in the scene (stretching, praying, practising a skill alone).
- Looking closely in order to overcome an obstacle ("문틈을 살펴 녹이 덜 슨 곳을 찾아 꾀를 낸다") is `try` with `wits`; looking to learn ("녹슨 문을 자세히 살펴본다", "문이 왜 안 열려?") is `look`.
- Talking while showing a thing ("편지를 보여 주며 부탁한다") is `talk`; handing it over ("편지를 건넨다") is `give`.
- A sentence that only asks a question about the world ("여기 뭐가 있지?") is `look` at the place.

### Mix per genre (36 items)

go 4, look 5, take 3, give 3, talk 7 (all five tones at least once, favor at least once, one deceive with a claim), try 8 (all four approaches, one `forced`, one `impossible`, one target `player`), declare 2, cut 2, choose 2. Six of the 36 have 2 or 3 steps ("그리고", "-고", "-한 뒤", "-하자마자"). Vary the writing: plain present ("문을 연다"), casual or imperative ("문 열어", "문 좀 열어 볼까"), questions, first person ("나는 …"), aliases and pronouns, long sentences with flavour, chat style or a typo in a few. Every item must have one answer a careful reader would agree on: if two labels are defensible, rewrite or drop it.

## 2. Reliance items (`"kind": "rely"`), 6 per genre

```json
{"kind": "rely", "id": "<genre>-r01", "genre": "<genre>",
 "attempt": {"label": "잠긴 격벽에 재치로 맞선다", "target": {"name": "잠긴 격벽", "look": "…"}},
 "text": "격벽 제어판의 배선을 바꿔 문을 연다",
 "options": [{"kind": "trait", "name": "해커", "text": "보안 장치를 다뤄 봤습니다."},
             {"kind": "thing", "name": "가족사진", "text": "구겨진 사진 한 장"},
             {"kind": "prop", "name": "", "text": "보안 드론은 소음에 반응한다"}],
 "relevant": [0]}
```

- `options` are what the player could lean on for a +1: traits (`text` = the trait text), carried things (`text` = look), known facts (`prop`, `text` = the fact), edge tags (`tag`, `name` only), a person who deeply trusts the player (`bond`, `name` = the person).
- 4–6 options per item; `relevant` lists the indexes that would really help this attempt (0, 1 or 2 of them). Include plausible distractors from the same world, and at least once a known fact about a danger that does not help (like "a fierce dog guards the hut" while fixing a lamp). One item per genre has no relevant option.

## 3. Narration check items (`"kind": "check"`), 10 per genre

```json
{"kind": "check", "id": "<genre>-c01", "genre": "<genre>",
 "facts": ["한서진은 함교에 있습니다", "당신이 암호 칩을 지니고 있습니다", "함교에서 기관실로 갈 수 있습니다", "잠긴 격벽: 0/2"],
 "public": ["함교: 깜빡이는 경고등, 낮게 울리는 엔진음", "한서진의 말투: 짧고 사무적입니다."],
 "happened": ["잠긴 격벽이 조금 풀렸습니다"],
 "sentence": "격벽의 잠금 장치가 덜컹이며 한 칸 물러납니다.",
 "contradicts": false, "invents": false}
```

- `sentence` is one narrator sentence (합니다체, the player is 당신). `contradicts`: it states something the facts or what happened deny (a person who is elsewhere is here, a held thing is lost, a locked obstacle is fully open, a different result than what happened). `invents`: it introduces a person, a usable thing, or a route not in the facts or public lines. Mood, weather, sounds and feelings drawn from the senses are neither.
- Per genre: 4 faithful (both false), 3 contradicting, 3 inventing (one may be both).
