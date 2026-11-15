# API

서버와 클라이언트가 주고받는 형식이다.

## 한눈에

- 클라이언트는 명령을 보내고, 서버는 결과와 새 화면 상태(`view`)를 돌려준다. 클라이언트는 받은 `view`를 그대로 쓴다.
- 응답에 든 한국어 문장은 서버가 만든다. 클라이언트는 고치지 않고 보여 준다.
- `GET /health`만 빼고 모든 경로에 Basic Auth가 필요하다(`--local`이면 `local/local`).
- 서술은 따로 받는다. 검사를 통과한 글만 온다.
- `/games/*` 경로, 저장의 `schema_version`, 요청 영수증(`request_id`), 브라우저의 `trpg.game_id`는 바꾸지 않는다. 바꾸려면 옮기는 작업(migration)을 따로 요청받아야 한다.

## 1. 경로

| 경로 | 보내는 것 | 받는 것 |
|---|---|---|
| `GET /health` | | `{ok: true, mode: "engine"}`. 인증 없이 된다 |
| `GET /stories` | | 이야기 목록: `id`, 제목, 소개, 능력치 값, 고를 수 있는 특성, `pick` |
| `POST /games` | `{request_id, story, creation}` | `{game_id, view}` |
| `GET /games/{id}` | | `view` |
| `POST /games/{id}/commands` | 2절 | `CommandResult` |
| `GET /games/{id}/turns/{n}/narration` | | NDJSON (4절) |
| `GET /games/{id}/chapters/{k}/recap` | | NDJSON (4절) |

- `creation`은 `{name, approaches, traits}`다. `name`은 앞뒤 공백을 뺀 1~10자다.
- `request_id`는 클라이언트가 명령마다 새로 만드는 문자열이다(UUID, 64자까지).
- `game_id`는 `request_id`에서 만든다. 그래서 같은 요청을 다시 보내면 이미 만든 게임의 같은 응답이 온다. 같은 `request_id`인데 내용이 다르면 409다.

| 오류 | 언제 | 내용 |
|---|---|---|
| 404 | 그런 게임이 없다 | |
| 409 | `revision`이 낡았다. 또는 같은 `request_id`인데 내용이 다르다 | `{view}`. 클라이언트는 이 `view`를 쓴다 |
| 409 | 저장이 맞지 않는다(`schema_version`이나 이야기 `digest`가 다르다) | `{reason: "incompatible"}`. `view`는 없다 |
| 422 | 요청 형식이 틀렸다 | `{reason}` |

- 판단 모델이 답하지 않는 것은 오류가 아니다. 알아듣지 못한 문장으로 다룬다(engine.md의 해석).
- 서술 모델이 실패하면 스트림에 `error`가 온다.

## 2. 명령

`POST /games/{id}/commands`에는 `{request_id, revision}`과 아래 중 하나를 보낸다.

| 보내는 것 | 뜻 |
|---|---|
| `text` | 플레이어가 쓴 문장 |
| `action` | 버튼의 행동 id (`view.buttons`, `view.growth`) |
| `card, pick` | 카드에 답한다. `pick`은 그 카드 `options`의 id다 |
| `card, cancel: true` | 카드를 버린다 |

```
CommandResult
{ "kind": "turn" | "card" | "refused",
  "turn": 12 | null,          실행한 단계가 있을 때의 턴 번호 (서술 경로의 {n})
  "steps": [단계 기록, …],     실행한 단계. 카드에서 멈췄어도 그 앞 단계는 여기 있다
  "reason": "…" | null,       거절한 까닭 (한국어)
  "view": GameView }
```

- **`card`**: 카드가 명령을 멈췄다. `steps`가 있어도 `card`다. 클라이언트는 `steps`가 있으면 결과를 보여 주고, `view.card`가 있으면 카드를 보여 준다.
- **`refused`**: 상태도 `revision`도 바뀌지 않는다. 다음일 때 온다.
  - 규칙만으로 걸러진 문장.
  - 지금 할 수 없는 행동을 바라는 문장. 엔진이 까닭을 알면 함께 알려 준다(막는 장애물, 여기 없는 사람, 갖지 않은 물건).
  - 이미 있는 곳으로 가려는 문장.
  - 지금 할 수 있는 행동에 없는 `action`.
  - 같은 `revision`에서 선택지에 없는 `pick`, 또는 낡은 카드 id.
- 카드를 받아들여 실행한 단계는 `steps[0]`이다.

거절과 카드가 언제 나오는지는 engine.md의 해석과 카드에 있다.

## 3. 단계 기록

실행한 단계마다 하나씩 있다. 플레이어가 볼 수 있는 것만으로 만든다. 숨은 변화는 들어가지 않는다.

```json
{
  "t": 7, "action": "try:door:finesse;rely=thing:key", "label": "열쇠로 자물쇠를 연다",
  "result": "success", "risk": "normal", "dc": 8,
  "roll": {"d1": 4, "d2": 3},
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2},
           {"kind": "help", "label": "윤슬의 도움", "value": 1},
           {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "total": 9, "decisive": [0],
  "changes": [{"kind": "fill", "id": "door", "name": "녹슨 등대 문", "from": 0, "to": 1}]
}
```

### 3.1 굴림

- `dc`는 목표 숫자, `roll`은 주사위 두 개의 눈, `total`은 눈과 `mods`를 더한 값이다.
- `total`이 `dc` 이상이면 `result`는 `success`, 아니면 `fail`이다.
- `total`과 `decisive`는 서버(`view.py`)만 계산한다.
- `decisive`는 결과를 가른 칩의 번호다(`mods`에서 0부터 센다). 그 칩이 없었다면 결과가 뒤집혔을 칩이다. 위 예에서 솜씨 2가 없으면 합이 7이라 목표 숫자 8에 못 미친다.
- 굴리지 않은 단계는 `dc: null`, `roll: null`, `mods: []`, `total: null`, `decisive: []`이고 `result`는 `none`이다.
- 숨어 있던 것에 막힌 단계는 `result: "blocked"`다. `changes`는 `{kind: "reveal", id: <장애물 id>, name}`으로 시작한다. 그 뒤에 그 시간 한 칸이 불러온 것이 이어진다(장면 끝의 시계와 태그, 위협이 닥침, 장 전환, 결말).
- 주사위의 `u`와 `seed`는 보내지 않는다. `u`는 사고 하나를 뽑는 데만 쓰인다.

### 3.2 `mods` (칩)

- 순서는 `stat`, 그다음 `help` 또는 `guard`, 그다음 `hinder`다.
- `stat` 칩은 값이 0이어도 있다. `help`와 `hinder`는 0이면 칩이 없다.
- 방해가 여러 개여도 `hinder` 칩은 하나다. 값은 −1이고 이름을 `·`로 잇는다.
- `guard` 칩은 쓰고 나면 없어지는 것에 기댔을 때 붙는다(rule.md의 기대기). 값은 언제나 0이다. 합을 올리지 않고 실패의 대가를 줄인다.
- 카드의 `preview.mods`와 모양도 순서도 같다. 클라이언트는 같은 번호끼리 짝지어 칩을 옮긴다.

### 3.3 `changes` (바뀐 것)

바뀐 것을 종류별로 묶는다. `from`과 `to`는 플레이어가 보는 값이다.

| `kind` | 뜻 | 더 붙는 것 |
|---|---|---|
| `fill` | 장애물을 넘었다 | `from: 0, to: 1`. `fit` 필드는 없다 |
| `closed` | 실패해서 그 방법이 그 장애물에 닫혔다 | 장애물의 `id`와 `name`, `approach`(방법 이름) |
| `clock` | 위험 시계가 찼다 | |
| `crisis` | 위기가 터졌다 | `name`은 시계 이름 |
| `tag_add` | 태그가 붙었다 | `replaced`: 자리가 꽉 차서 밀려난 태그 이름 |
| `tag_remove` | 태그가 떨어졌다 | |
| `wound` | 상처가 생겼다 | `tag_add`와 같은 필드 |
| `heal` | 상처가 나았다 | `tag_remove`와 같은 필드 |
| `scene_end` | 장면이 끝났다 | 이 때문에 움직인 시계들보다 앞에 온다 |
| `move` | 자리를 옮겼다 | `with: true`: 동행이 같이 움직였다 |
| `follow` | 동행이 시작되거나 끝났다 | `state`: `start` 또는 `stop`, 그 사람의 `id`와 `name` |
| `reveal` | 무언가 드러났다 | |
| `forget` | 눈앞의 사람이 믿던 것을 버렸다 | `text`: 그 믿음 |
| `consume` | 물건이 세계에서 사라졌다 | |
| `flag` | 문장이 딸린 표시가 값을 얻었다 | `text`: 그 문장 |
| `link` | 길이 바뀌었다 | |
| `regards` | 신뢰나 두려움이 바뀌었다 | |
| `promise` | 약속이 바뀌었다 | |
| `arrival` | 위협이 닥쳤다 | `name`은 위협 이름 |
| `fork` | 갈림길이 플레이어 앞에 왔다 | `choices`: 선택지 이름들 |
| `chapter` | 장이 바뀌었다 | `from: k, to: k+1` |
| `ending` | 결말이 났다 | `id` |

시간 칸은 `changes`에 없다. `view.player`로만 간다.

## 4. 서술 스트림

`GET /games/{id}/turns/{n}/narration`은 NDJSON이다. 검사를 통과하기 전에는 글을 보내지 않는다. 그래서 클라이언트는 지어낸 문장을 보여 줄 일이 없다.

```
{"type": "stage", "stage": "writing"}      초안을 쓰는 중
{"type": "stage", "stage": "checking"}     검사하는 중
{"type": "stage", "stage": "rewriting", "attempt": 2}
{"type": "text", "text": "…"}              통과한 서술 전체
{"type": "done", "tags": [{"slot": 1, "owner": "player", "name": "젖은 발"}]}
{"type": "error", "message": "…"}          모델이 답하지 않았다. 새로 요청하면 처음부터 다시 한다
```

- 이미 만든 서술이 있으면 `text`와 `done`만 바로 온다.
- 같은 턴을 동시에 여러 번 요청해도 서술은 한 번만 만든다. 나머지는 그 결과를 기다린다.
- `GET /games/{id}/chapters/{k}/recap`도 같은 형식이다.
- `k`는 이렇게 정한다. 단계 기록의 `changes`에 `chapter`가 있으면 그 `from`이다. `ending`이 있으면 `view.chapter.k`다.

## 5. `GameView`

화면에 필요한 것 전부다. 플레이어가 볼 수 있는 것만 담는다.

| 필드 | 내용 |
|---|---|
| `revision` | 다음 명령에 함께 보낼 값 |
| `story` | 이 게임의 이야기 `{id, title, premise}`. 첫 턴에는 서술 자리에 `premise`를 보여 준다 |
| `chapter` | `{k, title, aim}`: 장 번호, 제목, 목표 문장 |
| `scene` | 장소 이름, 감각 단서, 보이는 사람(이름, 태도를 나타내는 말, 동행이면 `with`), 물건, 장애물(이름, 넘었는지, 닫힌 방법들의 이름, 무엇을 막는지), 나가는 길 |
| `player` | 이름(`creation.name`. 옛 저장에서는 빈 문자열), 능력치 넷, 특성(이름, 이번 장에 썼는지), 태그(자리, 종류, 수명, 이름), 가진 물건(이름, 이번 장에 썼는지), `wounds`(상처 태그)와 `wound_boxes`(자리 수, 언제나 3), 쓴 시간 칸과 장면 길이 `B`, 성장 |
| `clocks` | 지금 도는 위험 시계, 기한, 위협, 갈림길 (이름, `fill`, 칸 수, 종류) |
| `journal` | 아는 사실(알게 된 순서, 지금 장면의 것을 가리키는지, 이번 장에 썼는지), 약속과 신세(`owes`), 사람별 관계, 갈림길에서 고른 것(이름, 장) |
| `buttons` | 추천(rule.md의 추천): 행동 id, 이름, 굴리는지 |
| `growth` | 성장 행동 `[{action, label, kind, name, text}]`. 성장이 1 이상일 때 있다 |
| `card` | 답을 기다리는 카드(5.1절). 없으면 없다 |
| `last` | 마지막 턴의 번호, 단계 기록, 서술이 만들어져 있는지 |
| `recaps` | 요약이 있는 장 번호들 |
| `ending` | 결말의 id와 제목. 없으면 없다 |
| `ledger` | 게임이 끝난 뒤, 장마다 플레이어와 사람들 사이에 오간 것. 결말 전에는 비어 있다 |

- **`growth`**: `kind`는 `approach`, `trait`, `wound` 중 하나다. `name`은 그 갈래 아래에 쓰는 짧은 이름이다("뱃사람 → 토박이"). `text`는 특성을 바꿀 때 새 특성의 설명이고, 아니면 비어 있다.
- **`ledger`**: `[{chapter, lines: [{kind, state?, text}]}]`. `text`는 그대로 보여 준다. `kind`는 넷이다.
  - `give`: 물건이 어느 쪽으로든 건너갔다.
  - `promise`: `state`는 `made`, `kept`, `broken`, `closed` 중 하나다.
  - `follow`: `state`는 `start` 또는 `stop`이다.
  - `regards`: 신뢰가 장을 시작할 때와 다르게 끝났다.

### 5.1 카드

카드는 넷이다: 굴림 카드(`roll`), 되묻기 카드(`clarify`), 확인 카드(`confirm`), 이동 카드(`move`). 언제 나오는지는 engine.md의 카드에 있다.

```
{ "id": "c42", "kind": "roll" | "clarify" | "confirm" | "move",
  "echo": {"text": "열쇠로 살살 돌려 본다", "slots": [{"slot": "approach", "label": "솜씨"}, {"slot": "strain", "label": "자연스럽게"}]},
  "plan": {"step": {"action": "try:door:finesse", "label": "녹슨 등대 문을 솜씨로 다룬다", "target": {"id": "door", "name": "녹슨 등대 문"}},
           "rest": ["등대 꼭대기로 간다"]},
  "options": [{"id": "try:door:finesse;rely=thing:key", "label": "등대 열쇠", "consumed": true, "note": "이번 장 1번",
               "rely": "thing:key", "forced": false, "preview": {…}},
              {"id": "try:door:finesse", "label": "기대지 않음", "consumed": false, "note": null, "rely": null, "forced": false,
               "preview": {…}}],
  "selected": "try:door:finesse;rely=thing:key" }
```

**굴림 카드의 선택지**

| 필드 | 뜻 |
|---|---|
| `rely` | 기댈 것. 기대지 않으면 `null` |
| `consumed` | 기대면 써 버리는지 |
| `note` | 써 버릴 때 보여 줄 글. 태그는 "1번 남음", 특성·물건·아는 사실은 "이번 장 1번" |
| `forced` | 그 방법이 그 장애물에 닫혀 있어 무리해서 하는지. 한 카드의 모든 선택지에서 같다 |
| `preview` | 굴리기 전에 보여 줄 값(5.2절) |

**되묻기 카드**

- `options`는 `{id: 행동 id, label}`이다.
- 선택지가 장애물에 굴리는 것이면(지키는 것을 돌아가는 길) `preview`에서 가져온 `dc`와 `risk`가 붙는다.

**확인 카드와 이동 카드**

- `options`는 `[{id: 행동 id, label, effects: [이름]}]`이다.
- 건네기의 확인 카드에는 둘째 선택지가 있다. 같은 물건을 보여 주기만 하는 것이다.
- 이동 카드에서 누군가에게 먼저 같이 가자고 묻는 선택지에는 `with`(그 사람 이름)가 있다. 이 선택지의 id는 계획의 행동 id들을 `+`로 이은 것이다. 다른 `pick`과 똑같이 받는다.
- 이동 카드의 `selected`는 문장이 고른 목적지이고, 첫 선택지다.
- 문장이 그 장소만 말했다면, 이동 카드는 남겨질 동행이 있을 때만 나온다. 이때 선택지는 그 장소 하나뿐이다.

되묻기, 확인, 이동 카드에는 `preview`가 없다.

### 5.2 `preview`

굴림 카드가 굴리기 전에 보여 주는 값이다. 여기 나온 숫자가 실제 숫자다.

```
{ "risk": "normal",
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2}, {"kind": "guard", "label": "등대 열쇠", "value": 0}, {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "z": 1, "dc": 8,
  "stakes": {"clock": 1, "weight": "light" | "heavy" | null},
  "clock": {"id": "clock.1", "name": "몰려오는 폭풍", "boxes": 4, "fill": 1},
  "gain": {"kind": "fill"} | {"kind": "tag", "remove": "젖은 발" | null}
        | {"kind": "topic"} | {"kind": "favor", "effects": ["등대 열쇠를 받음"]} | {"kind": "follow"} }
```

| 필드 | 뜻 |
|---|---|
| `risk` | 위험: `low`, `normal`, `high` |
| `mods` | 칩. 단계 기록의 `mods`와 같다 |
| `z` | 칩 값을 다 더한 것 |
| `dc` | 목표 숫자 |
| `stakes` | 실패하면 치를 대가. `clock`은 위험 시계가 찰 칸 수, `weight`는 사고의 크기(작은 사고 `light`, 큰 사고 `heavy`, 없으면 `null`) |
| `clock` | 지금의 위험 시계 |
| `gain` | 성공하면 얻는 것 |

`gain`의 종류:

| `kind` | 뜻 |
|---|---|
| `fill` | 장애물을 넘는다 |
| `tag` | 나쁜 태그를 뗀다(`remove`가 그 이름). 뗄 것이 없으면 `remove`는 `null`이고 좋은 태그를 얻는다 |
| `topic` | 물은 것을 알게 된다 |
| `favor` | 부탁을 들어준다. `effects`가 얻는 것이다 |
| `follow` | 같이 가 준다 |

목표 숫자와 대가를 정하는 규칙은 rule.md의 주사위에 있다. 잘 맞는 방법(`fits`)이면 목표 숫자가 한 단계 내려가고, 안 맞는 방법(`clashes`)이면 한 단계 올라간다. 닫힌 방법은 무리해서만 쓸 수 있고 위험이 한 단계 올라간다.
