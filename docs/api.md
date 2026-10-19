# API

서버와 화면의 경계입니다. 모든 경로는 Basic Auth를 거칩니다(`--local`이면 `local/local`). 응답의 한국어 문장은 서버가 만들고 화면은 그대로 보입니다. `/games/*` 경로, 저장의 `schema_version`, 요청 영수증, 브라우저의 `trpg.game_id`는 이행 요청이 없는 한 바꾸지 않습니다.

## 1. 경로

| 경로 | 본문 | 응답 |
|---|---|---|
| `GET /stories` | | 이야기 목록: `id`, 제목, 전제, 방식 값들, 특성 후보와 `pick` |
| `POST /games` | `{request_id, story, creation}`. `creation`은 `{name, approaches, traits}`이고 `name`은 앞뒤 공백을 뺀 1~10자 | `{game_id, view}`. `game_id`는 `request_id`의 해시라서 같은 요청을 다시 보내면 이미 만든 게임의 같은 응답을 줌(본문이 다르면 409) |
| `GET /games/{id}` | | `view` |
| `POST /games/{id}/commands` | 2절 | `CommandResult` |
| `GET /games/{id}/turns/{n}/narration` | | NDJSON(4절) |
| `GET /games/{id}/chapters/{k}/recap` | | NDJSON(4절) |

`request_id`는 화면이 명령마다 새로 만드는 문자열(UUID, 64자 이하)입니다.

| 오류 | 때 | 본문 |
|---|---|---|
| 404 | 없는 게임 | |
| 409 | 낡은 `revision`, 같은 `request_id`에 다른 본문 | `{view}` — 화면은 이 `view`를 받아들임 |
| 409 | 호환되지 않는 저장(`schema_version`이나 원고 `digest`가 다름) | `{reason: "incompatible"}`, `view` 없음 |
| 422 | 형식 오류 | `{reason}` |

모델이 응답하지 않는 것은 오류가 아니라 읽을 수 없는 답이고(engine.md 3.5), 서술 모델의 실패는 스트림의 `error`입니다.

## 2. 명령

`POST /games/{id}/commands`의 본문은 `{request_id, revision}`에 다음 중 하나를 더한 것입니다.

| 본문 | 뜻 |
|---|---|
| `text` | 플레이어의 문장 |
| `action` | 버튼의 행동 id(`view.buttons`, `view.due`, `view.growth`) |
| `card, pick` | 카드의 답. `pick`은 그 카드 `options`의 id |
| `card, cancel: true` | 카드를 버림 |

```
CommandResult
{ "kind": "turn" | "card" | "refused",
  "turn": 12 | null,          steps가 있으면 그 턴 번호(서술 경로의 {n})
  "steps": [단계 기록, …],     실행한 단계. 카드로 멈춰도 그 앞의 단계는 있음
  "reason": "…" | null,       refused의 이유(한국어)
  "view": GameView }
```

- `kind`는 `steps`가 있어도 카드로 멈췄으면 `card`입니다. 화면은 `steps`의 유무로 드러남을, `view.card`로 카드를 정합니다.
- `refused`: 0층의 거절, 후보 밖 `action`, 같은 `revision`에서 선택지 밖의 `pick`이나 낡은 카드 id. 상태와 `revision`은 바뀌지 않습니다.
- 카드를 수락한 단계는 `steps[0]`입니다.

## 3. 단계 기록

실행한 단계마다 하나이고, `Step`(결과, 위험, `mods`)과 사건의 플레이어 투영 `seen[player]`, `λ`, 표현층의 이름으로만 만듭니다. 숨은 변경은 들어 있지 않습니다.

```json
{
  "t": 7, "action": "try:door:finesse;rely=thing:key", "label": "열쇠로 자물쇠를 연다",
  "result": "mixed", "risk": "normal",
  "roll": {"d1": 4, "d2": 3},
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2},
           {"kind": "help", "label": "등대 열쇠", "value": 1},
           {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "total": 9, "decisive": [2],
  "changes": [{"kind": "fill", "id": "door", "name": "녹슨 등대 문", "from": 0, "to": 2, "fit": 1},
              {"kind": "clock", "id": "clock.1", "name": "몰려오는 폭풍", "from": 1, "to": 2}]
}
```

- `mods`는 칩의 목록입니다. `stat`, 도움, 방해 차례이고, 방해의 원자가 여럿이어도 방해 하나(값 −1, 이름을 `·`로 이어 씀)입니다. `stat` 칩은 값이 0이어도 있고, 도움과 방해는 0이면 칩이 없습니다. 카드의 `preview.mods`와 같은 모양, 같은 차례라 화면은 번호로 짝지어 칩을 옮깁니다.
- `total`과 `decisive`는 서버(`view.py`)만 계산합니다. `decisive`는 빼면 결과가 바뀌는 칩의 `mods` 안 번호(0부터)들입니다. 위 예에서 물보라의 −1이 없었다면 10으로 성공이었습니다.
- `changes`는 `δ`의 원자를 화면의 종류로 묶은 것이고 `from`, `to`는 보이는 값입니다. 종류: `fill`(장애물 칸, `fit`은 어울리는 방식으로 더 찬 칸 수), `clock`, `crisis`(`name`은 시계 이름), `tag_add`, `tag_remove`, `wound`, `scar`, `move`, `reveal`, `link`, `regards`, `promise`, `arrival`(`name`은 위협 이름), `chapter`(`from: k, to: k+1`), `ending`(`id`). 박자는 `view.player`로만 갑니다.
- 굴리지 않은 단계는 `roll: null`, `mods: []`, `total: null`, `decisive: []`이고 `result`는 `none`입니다. 숨은 막힘은 `result: "blocked"`에 `changes`가 `[{kind: "reveal", id: <장애물 id>, name}]`입니다.
- 주사위의 `u`와 `seed`는 보내지 않습니다. `u`는 복잡화를 고르는 수일 뿐 플레이어의 경험에 쓰이지 않습니다.

## 4. 서술 스트림

`GET /games/{id}/turns/{n}/narration`은 NDJSON입니다. 검사 전의 글은 보내지 않으므로 화면은 지어낸 문장을 한 번도 보이지 않습니다.

```
{"type": "stage", "stage": "writing"}      초안을 쓰는 중
{"type": "stage", "stage": "checking"}     검사 중
{"type": "stage", "stage": "rewriting", "attempt": 2}
{"type": "text", "text": "…"}              받아들인 서술 전체
{"type": "done", "tags": [{"slot": 1, "owner": "player", "name": "젖은 발"}]}
{"type": "error", "message": "…"}          모델이 응답하지 않음. 다시 요청하면 처음부터
```

캐시가 있으면 `text`와 `done`만 바로 보냅니다. 같은 턴의 요청이 겹치면 하나만 만들고 나머지는 그 결과를 기다립니다. `GET /games/{id}/chapters/{k}/recap`은 같은 형식입니다. `k`는 단계 기록의 `changes`에 `chapter`가 있으면 그 `from`, `ending`이 있으면 `view.chapter.k`입니다.

## 5. `GameView`

모두 `Obs`와 표현층에서 만듭니다.

| 필드 | 내용 |
|---|---|
| `revision` | 다음 명령에 넣을 값 |
| `story` | `{id, title, premise}` 이 판의 이야기. 첫 턴의 서술 자리에는 `premise`를 보임 |
| `chapter` | `{k, title, aim}` 장 번호, 제목, 목표 문장 |
| `scene` | 장소 이름, 감각 단서, 보이는 인물(이름, 태도 낱말), 물건, 장애물(이름, 칸, 막는 것), 갈 곳 |
| `player` | 이름(`creation.name`, 옛 저장은 빈 글), 방식 넷, 특성(이름, 이번 장에 썼는지), 태그(슬롯, 종류, 수명, 이름), 상처/칸, 박자/`B`, 성장 |
| `clocks` | 지닌 위험 시계, 마감, 활성 위협과 갈림(이름, `fill`, 칸 수, 종류) |
| `journal` | 믿는 것(`B`의 문장, 믿게 된 차례, 지금 장면의 개체를 말하는지), 약속과 신세(`owes`), 인물별 관계, 고른 대가와 갈림의 선택(이름, 장) |
| `buttons` | 추천(rule.md 9절): 행동 id, 이름, 굴리는지 |
| `due` | 고를 대가 `[{action, name, weight}]`, `pool`의 차례 |
| `growth` | 성장 행동 `[{action, label}]`(성장이 1 이상일 때) |
| `card` | 기다리는 카드(아래) 또는 없음 |
| `last` | 마지막 턴의 번호, 단계 기록, 서술이 캐시되었는지 |
| `recaps` | 되돌아보기가 있는 장 번호들 |
| `bands` | `{"mixed": 7, "success": 10, "min": 1, "max": 16}` 결과 경계와 눈금. 화면은 그리기에만 씀 |
| `ending` | 결말 id와 제목, 또는 없음 |

카드(engine.md 4절):

```
{ "id": "c42", "kind": "roll" | "clarify" | "confirm",
  "echo": {"text": "열쇠로 살살 돌려 본다", "slots": [{"slot": "approach", "label": "솜씨"}, {"slot": "strain", "label": "자연스럽게"}]},
  "plan": {"step": {"action": "try:door:finesse", "label": "녹슨 등대 문에 솜씨로 맞선다", "target": {"id": "door", "name": "녹슨 등대 문", "fill": 0, "boxes": 3}},
           "rest": ["등대 꼭대기로 간다"]},
  "options": [{"id": "try:door:finesse;rely=thing:key", "label": "등대 열쇠", "consumed": false, "preview": {…}},
              {"id": "try:door:finesse", "label": "기대지 않음", "consumed": false, "preview": {…}}],
  "selected": "try:door:finesse;rely=thing:key" }
```

되묻기의 `options`는 `{id: 행동 id, label}`, 확인의 `options`는 `[{id: 행동 id, label, effects: [이름]}]`이고 둘 다 `preview`가 없습니다. 굴림 카드의 `preview`는 rule.md 3.4의 필드입니다.

```
{ "risk": "normal",
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2}, {"kind": "help", "label": "등대 열쇠", "value": 1}, {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "z": 2, "odds": {"fail": 0.167, "mixed": 0.417, "success": 0.417},
  "stakes": {"mixed": {"clock": 1, "weight": "light"}, "fail": {"clock": 1, "weight": "heavy"}},
  "clock": {"id": "clock.1", "name": "몰려오는 폭풍", "boxes": 4, "fill": 1},
  "gain": {"kind": "fill", "boxes": 2, "fit": 1} | {"kind": "tag", "remove": "젖은 발" | null}
        | {"kind": "topic"} | {"kind": "favor", "effects": ["등대 열쇠를 받음"]} }
```
