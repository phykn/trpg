# 원고 형식

원고는 이야기의 전부이고 엔진 코드에는 이야기가 없습니다. 이 문서는 `scenarios/<폴더>/`의 파일 형식과 시작 시 검증을 정합니다. 이 형식을 따르는 가장 작은 이야기는 [scenarios/skeleton/story.yaml](../scenarios/skeleton/story.yaml)입니다.

```
scenarios/<폴더>/   폴더 이름은 자유. 이야기 id는 story.yaml의 id
  story.yaml    원고 전체: 세계, 문체, 증인
  evals.yaml    해석 평가 문장(원고가 아닌 시험 자료)
```

## 1. 원칙

원고가 쓰면 안 되는 것은 쓸 자리를 두지 않습니다. 장 전환, 결말, 시계와 마감, 위협의 등장, 잠재의 개체는 원고 효과가 손댈 수 없는 필드이고, 엔진이 그 필드에서 방아쇠와 효과를 만듭니다. 원고는 세계를 2.4의 효과 연산으로만 바꾸고, 원고 행동은 `try`에 이름과 조건을 붙인 해법뿐입니다. 그래서 규칙이 요구하는 구조의 대부분이 문법에서 성립하고, 검사로 남는 것은 4절입니다. 원고 하나는 파일 하나, 형식 하나입니다.

## 2. 공통

### 2.1 파일

- YAML 1.2의 부분집합으로 씁니다. 앵커, 별칭, 태그를 쓰지 않고, 스칼라는 스키마가 정한 종류로만 읽습니다(`no`, `on`은 문자열). **맵의 차례는 형식의 일부**이고 로더는 문서의 차례를 지킵니다. 방아쇠, 결말, 복잡화의 차례가 여기서 옵니다. 주석은 한국어로 씁니다.
- **id는 맵의 키입니다.** id가 있는 것(장소, 인물, 물건, 장애물, 위협, 갈림, 해법, 복잡화, 화제, 믿음, 주장, 잠재, 선택지, 방아쇠, 결말, 특성)은 모두 맵의 키로 쓰고 따로 `id` 필드를 두지 않습니다. id는 소문자, 숫자, `_`이고 이야기 전체에서 서로 다릅니다. 예약 id는 `player`(`p★`), `chat`, `favor`, `come`, `stay`, `pass`, `rest`, `chapter`, `ending`, `collapse`(결말 절에서만), `promise`, `kindness`, `full`, 그리고 `fired_`로 시작하는 것입니다.
- 장소, 인물, 물건, 장애물, 위협, 갈림마다 `name`을 두고 `aliases`는 선택입니다. 엔진의 틀 표가 이 이름으로 사실과 변화를 쓰고 읽습니다(engine.md 1절). 별칭은 이야기 전체에서 겹치지 않습니다.
- 명제의 문장(2.5)을 뺀 모든 글은 **공개 매개변수**입니다: `premise`, `style`, 이름과 별칭, `senses`, `look`, `voice`, `desire`, `fear`, 특성의 `text`, 화제의 `title`, `label`, 복잡화·선택지·기본 선택지·약속·잠재·시계·마감의 `name`, 주장의 `text`, 결말의 `title`과 `frame`. 숨길 내용은 명제의 문장에만 씁니다.

### 2.2 엔진 어휘

| 값 종류 | id (한국어) |
|---|---|
| 방식 | `force` 완력, `finesse` 솜씨, `wits` 재치, `charm` 매력 |
| 위험 | `low` 낮음, `normal` 보통 (장애물의 기본 위험) |
| 태도 | `polite` 정중, `friendly` 친근, `plead` 간청, `threaten` 위협, `deceive` 속임 |
| 무리함 | `natural` 자연스러움, `forced` 무리 |
| 축 | `trust` 신뢰, `fear` 두려움 |
| 태그 | `edge` 유리, `snag` 불리 |
| 수명 | `scene` 장면, `chapter` 장 (영구 `scar`는 엔진의 흉터만) |
| 무게 | `light` 가벼움, `heavy` 무거움 |
| 결과 | `success` 성공, `fail` 실패, `none` 굴림 없이 이룸, `blocked` 막힘. `mixed`는 결과가 아님 |

### 2.3 조건

조건은 변수가 없는 문장이고 키 하나짜리 맵으로 씁니다.

| 형태 | 뜻 |
|---|---|
| `{at: [x, y]}` | `at(x, y)` |
| `{link: [p, q]}` | `link(p, q)` |
| `{believes: [g, p]}` | `believes(g, p)`. `p`는 명제 id(2.5) |
| `{fill: [o, 비교, n]}` | `fill(o, m)`이고 `m 비교 n`. `n` 자리에 `full`(칸 수) |
| `{regards: [g, h, 축, 비교, n]}` | `regards(g, h, 축, m)`이고 `m 비교 n` |
| `{mark: [x, 태그]}` | `x`에 그 종류의 `mark`가 있음 |
| `{owes: [g, h, k]}` | `owes(g, h, k)`. `k`는 `promise`(부탁의 약속) 또는 `kindness`(호의) |
| `{flag: [이름, 값]}` | `flag(이름, 값)`. 이름은 `flags`(3.1)에 선언한 것이나 `chapter`(장 번호) |
| `{did: [행동 id 앞부분]}`, `{did: [행동 id 앞부분, 결과]}` | 이력 패턴 |
| `{all: [...]}`, `{any: [...]}`, `{not: c}` | 묶음. `{all: []}`은 참, `{any: []}`는 거짓 |

비교는 `=`, `>=`, `<=`, `>`, `<`입니다. 조건이 놓인 자리가 평가하는 곳을 정합니다(3절 표의 "평가"). **보임**은 `(F, hᵥ)`와 원고 상수, **세계**는 `(S, h)`입니다(ontology.md 3.3).

`did`는 이력 패턴입니다. 사건의 행동 id가 의도 인자를 `:`로 나눈 조각 단위로 그 앞부분으로 시작하고, 앞부분에 적은 판단 인자(`;키=값`)가 모두 같고, 결과를 적었으면 결과가 같으면 맞습니다. 원고의 모든 `did`가 원고의 패턴 집합입니다.

### 2.4 효과

효과는 연산의 열이고 앞 연산이 적용된 상태를 읽으며 차례로 합성합니다(ontology.md 4절). 원고가 쓸 수 있는 연산은 이것뿐입니다.

| 형태 | 연산 | 대상 |
|---|---|---|
| `{move: [x, y]}` | `move(x, y)` | `x`: 물건, 인물, `player`(이때 `y`는 장소) |
| `{set: [fill, o, v]}` | `set_(fill, o, v)` | 장애물, 위협, 갈림 |
| `{set: [regards, g, h, 축, v]}` | `set_(regards, …)` | 인물 |
| `{set: [flag, 이름, v]}` | `set_(flag, …)` | `flags`에 선언한 플래그, 값은 선언한 값 안 |
| `{reveal: [g, p]}` | `reveal(g, p)` | 명제 |
| `{tag: [x, 태그, 수명, 기본 이름]}` | `tag(x, 태그, 수명)` | 수명은 `scene`·`chapter`. 기본 이름은 서술이 이름을 붙이기 전에 씀 |
| `{link: [p, q]}`, `{unlink: [p, q]}` | `link`, `unlink` | 장소 |
| `{retire: o}` | `retire(o)` | 장애물, 위협, 갈림 |

`v`는 값이거나 정수 값에 대한 `"+n"`, `"-n"`입니다. 상대값은 적용하는 순간의 값에 더하고 한도에서 멈춥니다. 위협의 `fill`을 내리는 효과를 지금 값을 모른 채 쓰기 위해서입니다.

이 표에 없는 것이 이 형식의 안전장치입니다. 원고 효과에는 `stat`이 없고(박자, 상처, 방식은 규칙과 복잡화의 `wound`만 바꿈), 위험 시계와 마감은 원고 id가 없어 가리킬 수 없으며, 위협과 갈림은 `move`의 대상이 아니고, 플래그 `chapter`, `ending`과 발동 플래그는 예약되어 `set`할 수 없습니다.

### 2.5 명제

원고에는 명제 절이 따로 없습니다. 명제는 그것이 쓰이는 자리에서 문장 하나로 생기고, 엔진이 `about`, `shows`, `against`, 뜻을 채웁니다(ontology.md 3.1). 원고 명제의 뜻은 모두 서사 상수입니다. 뜻이 세계를 따라 바뀌는 명제는 작가가 예측하기 어렵고 지금의 장치가 쓰지 않습니다.

| 자리 | 명제 id | `about` | `shows` | 뜻 | 누가 믿게 되나 |
|---|---|---|---|---|---|
| 개체의 `hidden` | `x.hidden` | `x` | `x` | 참 | 그것을 `reveals`하는 화제의 공개, 막힘이 드러날 때 |
| 개체의 `clue` | `x.clue` | `x` | - | 참 | `look(x)` |
| 화제의 `text` | 화제 id | - | - | 참 | 그 화제의 공개 |
| 인물의 `beliefs` | 믿음 id | - | - | 참 | 그 인물(시작부터) |
| 주장 | 주장 id | - | - | 거짓, `against`는 주장의 `against` | 아무도 믿지 않음(들통 판정용) |
| 잠재의 `text` | 잠재 id | `brings`의 개체 | 같음 | 참 | 플레이어(선언) |

## 3. 항목

### 3.1 최상위

| 키 | 내용 |
|---|---|
| `id`, `version`, `title`, `premise` | 이야기 id(폴더 이름과 무관, 이야기끼리 다름), 판, 제목, 공개 전제 |
| `beats`, `wound_boxes` | 장면 길이 `B ≥ 2`, 상처 칸 수 `≥ 1` |
| `flags` | 원고 플래그 `{이름: [값, …]}`. 첫 값이 시작 값이고, 값은 정수의 연속 범위이거나 문자열 |
| `style` | 서술 모델에게 그대로 가는 문체(여러 줄) |
| `impossible` | 이 세계에 없는 것을 가리키는 구절(engine.md 3.1) |
| `player` | 3.2 |
| `places`, `characters`, `things`, `obstacles` | 3.3~3.6 |
| `chapters`, `threats`, `forks` | 3.7~3.8 |
| `claims`, `latents`, `triggers`, `endings` | 3.9~3.11 |
| `witnesses` | 5절 |

`S₀`에는 `flag(chapter, 1)`과 선언한 플래그의 시작 값이 있습니다.

없어도 되는 것: 최상위의 `flags`, `impossible`, `threats`, `forks`, `claims`, `latents`, `triggers`(없으면 빈 것); 항목의 `aliases`, `clue`, `hidden`, `complications`; 주인공의 `traits`(없으면 특성 없음); 장소의 `rest`; 인물의 `regards`, `beliefs`, `wants`, `topics`, `favor`, `avoids`; 화제의 `free_when`(없으면 거짓); 장애물의 `risk`(기본 `normal`), `fits`, `clashes`, `blocks`; 해법의 `rely`, `when`; 장의 `goal_effects`; 마감의 `effects`와 `ending`(마지막 장의 `ending`은 필수); 잠재의 `brings`, `effects`; 그리고 `evals.yaml`. 그 밖의 필드는 필수입니다.

### 3.2 주인공

| 필드 | 뜻 |
|---|---|
| `start` | 시작 장소 |
| `approaches` | 네 값, 예 `[2, 1, 1, 0]`. 값은 `0…3`. 플레이어는 그 합을 네 방식에 나눠 주고, 한 방식은 그 가장 큰 값을 넘지 못함 |
| `traits` | `{pick: n ≥ 1, options: {id: {name, text}}}`, 후보는 `pick`보다 많게. 특성은 능력치(방식)와 겹치지 않게 주인공의 내력(직업, 인연, 아는 것)으로 씀 |

시작 소지품은 `things`의 `at: player`입니다. 박자, 상처, 성장은 0에서 시작합니다.

### 3.3 장소

| 필드 | 뜻 |
|---|---|
| `name`, `aliases`, `senses` | 이름, 별칭, 감각 단서 3~5개 |
| `exits` | 갈 수 있는 장소들. `link(이 장소, q)` 하나씩 |
| `rest` | 쉴 곳(`cut:rest`) |
| `clue`, `hidden` | 2.5 |
| `complications` | 3.6 |

### 3.4 인물

| 필드 | 뜻 | 평가 |
|---|---|---|
| `name`, `aliases`, `pronoun`, `desire`, `fear` | 공개 매개변수 | |
| `voice` | 말투 한 줄. 끝에 그 인물다운 대사 한 마디를 `예: "…"`로 붙이면 서술 모델이 말씨를 그 예에 맞춥니다. 예시 대사에는 숨길 사실을 쓰지 않음 | |
| `persona` | 성격 유형. 엔진이 정한 16가지 MBTI 유형(`ISTJ` … `ENTJ`) 중 하나이고, 서술 문맥에 그 유형의 성격 풀이가 함께 나감. 필수 | |
| `at` | 시작 장소. 무대 밖에서 시작하는 인물은 잠재(3.10)가 데려옴 | |
| `avoids` | 함께 다니다가도 들어가지 않는 장소들(rule.md 5.1 동행). 두려움(`fear`)과 맞추면 인물이 살아남. 없으면 어디든 따라감 | |
| `regards` | 플레이어를 보는 시작 값 `{trust, fear}`, `−3…3`. 없으면 0 | |
| `beliefs` | `{id: 문장}`. 시작부터 믿는 명제 | |
| `wants` | 건네받으면 반기는 물건(rule.md 5.1 `give`). 화면과 프롬프트에는 그 물건이 플레이어에게 숨지 않은 동안만 나감 | |
| `topics` | `{id: {title, text 또는 reveals, free_when}}`. `reveals: x`는 `x.hidden`을 공개 | `free_when`: 보임 |
| `favor` | `{label, effects, promise: {name, keep, break}}`. 인물마다 많아야 하나이고, 들어주면 다시 고를 수 없음 | `keep`, `break`: 세계 |
| `clue`, `hidden`, `complications` | 2.5, 3.6 | |

`free_when`은 굴림 여부와 화면이 함께 보임으로 평가합니다(V3가 보임과 세계의 값을 같게 만듦). `break`가 없으면 거짓입니다. 지키지도 어기지도 않은 약속은 생긴 단계 뒤의 첫 장 전환이나 결말에서 `keep`으로 판가름합니다(rule.md 5.2).

### 3.5 물건

`{name, aliases, look, at, clue, hidden}`. `at`은 장소, 인물, `player` 중 하나입니다.

### 3.6 장애물, 해법, 복잡화

| 필드 | 뜻 | 평가 |
|---|---|---|
| `name`, `aliases`, `look`, `at` | 공개 이름, 생김새(글이 적힌 물건은 그 글도), 놓인 장소 | |
| `boxes` | 칸 수 `1…6`. 없으면 1: 한 번 성공하면 넘음 | |
| `risk` | `low` 또는 `normal`. 위험 식의 기본값(rule.md 3.2) | |
| `fits`, `clashes` | 어울리는 방식(`fill` +1 더), 어긋나는 방식(위험 +1) | |
| `blocks` | 막는 장소, 물건, 인물, 장애물 | |
| `solutions` | `{id: {label, approach, rely, when}}`, 둘 이상이고 방식이 서로 다름 | `when`: 보임 |
| `clue`, `hidden`, `complications` | 2.5, 아래 | |

- **해법**은 `try(이 장애물, approach)`에 `label`과 조건 `when`을 붙인 인스턴스입니다. `rely`는 기댄 것(물건 또는 명제 id)을 정하고, 그것을 지니거나 믿는 것이 `when`에 암묵으로 더해집니다. 결과, 위험, 대가는 `try`와 같고, 해법이 아닌 `try(이 장애물, 방식)`도 후보입니다. 해법은 후보를 더하지 않고 이름만 붙입니다.
- 다 찼을 때의 효과는 방아쇠 `{when: {fill: [o, "=", full]}}`로 씁니다.
- **막힘**: `blocks`는 장애물이 놓여 있고 다 차지 않은 동안 막습니다(ontology.md 1.2). 장소면 `go`, 물건이면 `take`, 인물이면 `talk`, 장애물이면 `try`를 막습니다. 보이는 장애물이 막는 행동은 후보가 아닙니다. 숨은 장애물이 막고 있으면 시도할 때 `o.hidden`을 믿게 되어 드러나고, 그 시도는 박자를 올리며 굴림이 없습니다.
- **복잡화** `{id: {name, weight, when, effects, wound}}`는 장소, 인물, 장애물에 붙고, 붙은 곳이 암묵 조건입니다(장소: 거기 있음, 인물: 눈앞에 있음, 장애물: 굴림의 대상). `wound: n`은 상처 +n이고, 상처를 올리는 원고 효과는 이것뿐입니다. `when`은 실패한 굴림에서 세계로 평가합니다(rule.md 3.3).

### 3.7 장

`chapters`는 목록이고 차례가 장 번호입니다(1부터). 장 전환은 늘 다음 장으로 갑니다.

| 필드 | 뜻 | 평가 |
|---|---|---|
| `title` | 공개 제목 | |
| `aim` | 화면에 늘 보이는 목표 한 문장. `goal`을 플레이어 말로 씀 | |
| `goal` | 장 목표. 마지막 장에는 없음 | 세계 |
| `goal_effects` | 목표를 이룰 때 장 전환에 더할 효과 | |
| `clock` | 필수. 위험 시계 `{name, boxes ≥ 3, crisis}`. `crisis`는 시계가 찰 때마다의 효과(하나 이상) | |
| `deadline` | 필수. 마감 `{name, boxes 1…6, effects, ending}`. `ending`은 `collapse`가 아닌 결말 id이고 `when`이 있는 결말이어도 됨 | |

엔진이 만드는 것:
- 장 `k`의 목표 방아쇠 `(flag(chapter, k) ∧ goal, [chapter_to(k+1)] ++ goal_effects)`
- 마감의 도착 효과: `ending: e`가 있으면 `effects ++ [end(e)]`, 없으면 `effects ++ [chapter_to(k+1)]`. 마지막 장의 마감에는 `ending`이 반드시 있음
- 위험 시계와 마감의 엔진 id(`clock.k`, `deadline.k`)와 `S₀` 배치: 첫 장의 것은 `at(·, player)`, 그 밖의 것은 `at` 없음, 모두 `fill` 0

### 3.8 위협과 갈림

| 필드 | 위협 `threats` | 갈림 `forks` | 평가 |
|---|---|---|---|
| `name`, `boxes`(1…6) | 공개 이름, 칸 수 | 같음 | |
| `appears_when` | 등장 조건 | 같음 | 세계 |
| `arrival` | 도착 효과 | - | |
| `choices` | - | `{id: {name, effects}}` 둘 이상 | |
| `default` | - | 버텼을 때의 `{name, effects}`, 고를 수 없음 | |

위협과 갈림은 `S₀`에서 `at`이 없고 `fill` 0입니다. 엔진은 `appears_when`을 한 번만 일어나는 방아쇠 `appear.<id>`(효과 `[move(w, player)]`)로 엮습니다. 위협을 물리는 것은 다른 효과의 `retire`이고, `fill`을 내리는 `set`은 도착을 늦춥니다. `retire`는 등장 방아쇠의 발동 플래그도 놓으므로 등장 전에 물린 위협과 갈림은 등장하지 않습니다.

### 3.9 주장

`claims: {id: {text, against}}`. `text`는 플레이어가 하는 공개 문장, `against`는 들통의 근거가 되는 믿음 id입니다. 듣는 이가 그 믿음을 가지면 들통입니다(rule.md 5.1).

### 3.10 잠재

`latents: {id: {name, when, text, brings, effects}}`.

| 필드 | 뜻 | 평가 |
|---|---|---|
| `name` | "분류: 짧은 말" | |
| `when` | 선언할 수 있는 조건 | 보임 |
| `text` | 선언으로 플레이어가 믿게 되는 명제(2.5) | |
| `brings` | 이 잠재만의 개체. `characters`, `things`처럼 쓰되 `at`이 없음 | |
| `effects` | 선언의 효과. `brings`의 개체를 무대에 올림 | |

**범위 규칙**: 잠재 id와 `brings` 안의 id는 그 잠재 항목 밖에서 쓸 수 없고, 잠재의 `effects`는 `brings`의 개체만 대상으로 합니다(`move`, `tag`, 그 개체의 `regards`). 선언하지 않은 잠재는 세계에 아무 흔적이 없습니다.

### 3.11 방아쇠와 결말

- `triggers: {id: {when, effects, repeat}}`. `when`은 세계로 평가하고, `repeat: true`가 없으면 한 게임에 한 번입니다.
- `endings: {id: {title, when, frame}}`. `collapse`는 반드시 있습니다. `when`이 있으면 엔진이 방아쇠 `end.<id>`(효과 `[end(id)]`)로 엮고, 없으면 어떤 장의 마감이 `ending`으로 가리켜야 합니다. `frame`은 결말 서술에 건네는 공개 문장입니다. 엔진의 결말 `collapse`(쓰러짐, rule.md 6절)는 `when` 없이 `title`과 `frame`만 둡니다.

엔진이 원고 방아쇠를 엮는 차례: 위협·갈림의 등장, `triggers`, 장 목표, `when`이 있는 결말. 같은 종류 안에서는 선언 차례입니다. 그 뒤가 엔진 방아쇠 다섯입니다(rule.md 8절).

### 3.12 행동 id

증인, 영수증, 버튼, 패턴이 쓰는 행동 id는 `스키마:의도 인자들`에 판단 인자를 `;키=값`으로 붙입니다. 적지 않은 판단 인자는 기본값 `ν₀`입니다. `rely`의 값은 가리키는 것의 종류를 붙여 `thing:<id>`, `prop:<id>`, `trait:<id>`, `bond:<id>`, `tag:<개체>:<슬롯>`으로 씁니다(rule.md 2절). 해법의 `rely` 필드는 id만 적고 종류는 원고에서 정합니다.

```
go:village   look:door   take:oil   give:letter:dohae   declare:l_baek   cut:pass   cut:rest
talk:dohae:t_oil;tone=friendly   talk:dohae:favor   talk:dohae:chat;tone=deceive;claim=c_keeper
try:door:finesse;rely=thing:key   try:door:force;strain=forced   choose:g_oil:beacon   grow:finesse
```

## 4. 검증

규칙이 원고에 요구하는 성질과 그것을 지키는 자리입니다.

| 성질 | 구조로 성립하는 것 | 검사로 남는 것 |
|---|---|---|
| 적합한 시작과 효과 | 효과는 2.4의 연산뿐, `move(player, ·)`는 장소로 | V1, V2 |
| 시계와 방아쇠의 문법(rule.md 4.2, 8절) | 시계와 마감은 가리킬 수 없음, 원고 효과에 `stat` 없음, 상처는 `wound`만, 위협 등장은 `appears_when` 한 번, 장 전환과 결말은 엔진이 장과 결말 필드에서 만듦, 장마다 시계와 마감이 있음 | V3: `S₀`에서 참인 방아쇠 조건이 없음 |
| 잠재의 격리 | 잠재의 개체와 명제는 그 항목 안에서 생김 | V1: 범위 규칙(3.10) |
| 유한한 값 | 플래그는 선언한 값만 | V1 |
| 보임 평가 = 세계 평가 | - | V3: 보임으로 평가하는 조건의 원자 |
| 막힘 | 숨은 개체마다 `x.hidden`이 정확히 하나 | V3: 막힘의 배치 |
| 비누설 | 숨길 내용을 쓸 자리(명제 문장)가 공개 글과 나뉨 | V4: 이름 누설만. 뜻의 누설은 작가의 몫 |
| 도달성 | - | V5 |
| 보존과 진행성 | - | V6 |

서버가 시작할 때 모든 이야기에 이 차례로 돌리고, 하나라도 실패하면 서지 않습니다. 오류는 영어로, 항목 id와 필드를 담습니다.

| | 단계 | 확인하는 것 |
|---|---|---|
| V1 | 형식 | 스키마(필드, 값 종류, 값 범위), id의 유일성과 참조, `brings`의 범위, 해법 둘 이상과 방식이 서로 다름, 장마다 `clock`과 `deadline`, 마지막 장은 목표가 없고 마감에 `ending`이 있음, `when` 없는 결말(`collapse` 제외)은 어떤 마감이 가리킴, `collapse` 결말이 있음, 플래그 값이 선언 안, 무게마다 원고 복잡화 58개 이하 |
| V2 | 시작 상태 | `S₀`를 만들어 `S₀ ⊨ C`, `player`가 장소 하나에 있음 |
| V3 | 자리 | `S₀`에서 참인 방아쇠 조건이 없음(엔진 방아쇠 포함). 보임으로 평가하는 조건(해법·잠재의 `when`, 고를 복잡화의 `when`, 화제의 `free_when`)은 평가 시점에 반드시 `F`에 있는 원자만 씀: 플레이어 자신의 원자(`at: [player, 장소]`, `at: [물건, player]`, `believes: [player, p]`, `mark: [player, 태그]`, `player`가 든 `regards`·`owes`), `did`, 그리고 조건이 붙은 개체 자신의 원자(`at: [그 개체, ·]`, `mark: [그 개체, ·]`, `fill: [그 장애물, ·]`). 인물이 지닌 물건의 `at`, 다른 곳의 개체, `flag`는 쓸 수 없음. 막는 장애물은 막는 물건·인물·장애물과 같은 장소에, 막는 장소면 그곳으로 가는 `exits`나 `link` 효과가 있는 모든 장소에 있음 |
| V4 | 이름 | 숨은 개체(`hidden`이 있거나 `brings`에 든 것)의 이름과 별칭이 2.1의 공개 매개변수에 나오지 않음, 별칭이 겹치지 않음, `impossible`의 구절이 이름, 별칭, 해법 `label`의 부분 문자열이 아님(0층의 판정이 부분 문자열이라서, engine.md 3.1) |
| V5 | 증인 | 5절의 재생 |
| V6 | 퍼징 | 무작위 행동열(`K`에서 고르고 주사위는 무작위)을 결말까지, 단계마다 `S ⊨ C`와 `K ≠ ∅`, 굴린 단계마다 미리보기의 위험, 보정 칩 목록, 합이 실행의 값과 같음(rule.md 10절 미리보기 = 실행) |

V1~V4는 원고를 한 번 훑고, V5는 증인 길이만큼 `K`와 `R`을 계산합니다. 마감이 내는 결말과 "막다른 길 없음"은 구조가 보장합니다(rule.md 10절).

## 5. 증인

`witnesses.paths`는 장 목표마다, 그리고 `when`이 있는 결말과 `collapse`마다 하나씩, 시작에서 그것에 닿는 행동과 주사위의 열입니다. 증인은 작성 도구가 찾고 작가는 확인만 합니다. 요구된 것 밖의 길을 더 두어도 되고 모두 재생합니다.

```yaml
witnesses:
  creation: {approaches: {force: 1, finesse: 2, wits: 1, charm: 0}, traits: [sailor, tinker]}
  paths:
    - reach: {goal: 1}
      steps:
        - go:village
        - {do: "try:door:finesse", roll: [6, 6, 0]}   # 굴림이 있는 행동만 [d₁, d₂, u]
    - reach: {ending: two_lights}
      after: 0                                       # 0번 길의 걸음 뒤에서 이어감
      steps: [choose:g_oil:beacon]
```

`creation`은 모든 길이 쓰고, 길이 자기 `creation`을 두면 그것이 앞섭니다. `after: i`는 `i`번 길의 걸음을 앞에 붙입니다.

재생은 `creation`으로 만든 `S₀`에서 걸음마다 `aᵢ ∈ K(Vᵢ)`를 확인하고 주어진 주사위로(굴림이 없으면 주사위 없이) `R`을 적용합니다. 마지막 걸음에서 목표의 방아쇠가 발동하거나 그 결말이 놓여야 합니다. 마감의 도착으로 장이 바뀐 것은 목표에 닿은 것이 아니고, 그 전에 결말이 나면 실패입니다. 카드와 되묻기는 해석의 일이라 재생에 없습니다.

## 6. 해석 평가

`evals.yaml`은 해석 모델의 정확도를 재는 시험 자료이고 시작 시 검증에 들지 않습니다. 상태는 증인의 한 걸음 뒤로 가리키고, 증인 길에 없는 상태는 `then`에 증인 걸음과 같은 꼴로 더 실행할 행동을 적습니다(`then: [{do: "talk:h:come", roll: [6, 6, 0]}]`).

```yaml
- at: {path: 0, step: 2}
  text: 열쇠로 문을 열어 본다
  expect: try:door:finesse;rely=thing:key
```
