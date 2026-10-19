# 원고 쓰는 법

이 폴더는 가장 작은 원고입니다(장소 3, 인물 2, 장애물 2). 새 이야기는 이 폴더를 `scenarios/<이름>/`으로 복사해서 시작합니다. 코드는 고치지 않습니다. 이름이 `_`로 시작하는 폴더는 목록에 나오지 않습니다.

다 썼으면 검증합니다.

```bash
cd server && ../.venv/bin/python -m src.content validate ../scenarios/<이름>
```

## 파일

- `scenario.json`: 세계와 규칙에 쓰일 모든 것. 형식은 `server/src/content/schema.py`에 있습니다.
- `world.md`: 서술 모델에 그대로 전달되는 문체 안내. 무엇을 쓰지 말지도 여기에 적습니다.

## 엔진이 정해 둔 어휘

이 이름들은 바꿀 수 없고, `labels`로 화면에 보이는 이름만 바꿉니다.

| 어휘 | 값 |
|---|---|
| 방식 | `force` 힘, `finesse` 재주, `wits` 꾀, `charm` 말솜씨 |
| 위험도 | `low`, `normal`, `high` |
| 태그 | `edge` 유리, `snag` 불리, 흔적 `wanted` `suspicion` `reputation` |

## 항목

- **id**: 소문자, 숫자, `_`만 씁니다. 장소·인물·물건·지식·기술·퀘스트 id는 서로 겹치면 안 되고 `player`는 쓸 수 없습니다. `move`, `promise`처럼 엔진이 쓰는 영어 단어는 피합니다.
- **creation**: 시작 방식(+2, +1, +1, 0)과 특성 2개. `choose: true`면 플레이어가 직접 고를 수 있습니다.
- **traits**: 정확히 6개. 플레이어가 문장에서 특성을 살리면 장마다 한 번 판정 +1입니다.
- **places**: `senses` 3~5개는 서술이 장면을 그릴 재료입니다. `exits`의 `open: false`는 효과 `open`으로 엽니다.
- **characters**: `desire`, `fear`, `contradiction`, `voice`, `boundary`로 사람을 만듭니다. 대사는 모델이 씁니다. `knows`는 그 인물이 아는 지식이고, 플레이어의 거짓말을 알아채는 근거가 됩니다. `gifts`는 물건을 받았을 때의 효과입니다. `pronoun`(`그` 또는 `그녀`)을 적으면 서술이 그 인물을 그렇게만 부릅니다.
- **items**: `place`(놓인 곳), `holder`(가진 인물), 둘 다 없으면 무대 밖입니다. `reveals`는 살펴보면 얻는 지식입니다.
- **topics**: 인물이 알려 줄 지식입니다. `free_when`은 판정 없이 알려 주는 조건 묶음이며 2개 이상 둡니다(관계, 다른 지식, 물건 등). 아니면 말솜씨 판정이고, `mods`는 태도별 보정입니다(`polite`, `empathy`, `persuade`, `threaten`, `deceive`).
- **obstacles**: 장면의 목표입니다.
  - `boxes` 2~6칸을 채우면 `on_full`이 한 번 실행됩니다.
  - `fits` 방식이면 효과 +1, `clashes` 방식이면 위험도가 한 단계 오릅니다.
  - `costs`는 대가 후보입니다(`snag`, `gold`, `item`, `wound`).
  - `solutions`는 2개 이상이며 추천 버튼 문장이 됩니다. 문장으로 입력하는 플레이어는 이 목록에 없는 방법도 씁니다.
  - `hidden: true`는 효과 `reveal`로 드러납니다. `guards`의 물건은 다 차기 전까지 집을 수 없습니다. `foe: true`는 전투 상대입니다.
- **chapters**: 장마다 `danger` 하나(6~8칸)를 둡니다. 다 차면 `on_full`(복잡화)이 한 번 실행되며 게임은 끝나지 않습니다. `tick_every`는 n턴마다 +1로, 시한을 만듭니다. `goal`이 맞고 `next`가 있으면 성장 뒤 다음 장으로 갑니다.
- **actions**: 장소에 묶인 원고 행동입니다(선택). `show`가 맞을 때 보이고 `requires`가 맞을 때 할 수 있습니다. `check`가 있으면 판정하고, 실패하면 `miss`를 실행합니다.
- **downed**: 부상 3칸이 찼을 때의 효과입니다. 게임을 끝내지 말고 어렵게 만듭니다.
- **endings**: 위에서부터 처음 맞는 결말을 고릅니다. 실패 결말을 앞에 둡니다.
- **impossible**: 이 세계에서 일어날 수 없는 일을 가리키는 구절입니다(`"용을"`, `"날개를"`). 문장에 들어 있으면 턴을 쓰지 않고 돌려보냅니다. 장소·인물·물건 이름이나 해법·행동 문장과 겹치면 검증이 실패합니다.

## 조건과 효과

조건: `at`, `knows`, `carries`, `relation`, `flag`, `progress`(값 또는 `"full"`), `trace`, `quest`, `turn`, `chapter`, `gold`. `negate: true`로 뒤집습니다. 비교는 `op`(`eq`, `gte`, `lt`)로 정하며, 기본값은 `flag`가 `eq`, 나머지 숫자가 `gte`입니다.

효과: `flag`, `flag_add`, `learn`, `give`, `take`, `move`(인물을 `target: ""`로 옮기면 떠남), `companion`, `relation`, `open`, `close`, `tag`(`key`에 종류, `value`에 이름), `reveal`, `progress`, `danger`, `gold`, `chapter`, `ending`.

## 좋은 원고의 기준

- 장애물마다 서로 다른 방식의 해법이 있습니다. 힘으로도 넘을 수 있지만 비싸게 만듭니다.
- 같은 지식을 얻는 길이 둘 이상 있습니다.
- 실패해도 이야기가 앞으로 갑니다. 막힌 길 대신 대가와 복잡화를 둡니다.
- 버튼만으로 끝까지 가는 길이 둘 이상 있고, 위험이 다 차는 길도 있습니다.
