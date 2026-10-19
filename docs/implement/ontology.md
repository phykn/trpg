# 온톨로지 구현

[ontology.md](../theory/ontology.md)의 상태 `S`, 변경 `Δ`, 기록 `L`, 이력 요약 `h`, 관찰 `V`를 코드로 옮기는 방법을 정합니다. 원고를 읽는 형식은 [story.md](story.md)가 정하고, 이 문서는 읽은 원고를 **우주** `U`와 시작 상태 `S₀`로 엮는 데서 시작합니다. 규칙(`R`, `K`)은 [rule.md](rule.md), 모델과 프로토콜은 [engine.md](engine.md)입니다. 지금의 코드와 무관하게 이론에서 끌어냈고, 이론이 열어 둔 자리를 정한 것은 8절에 모았습니다.

```
server/src/onto/
  atoms.py    원자, 상태 S, 적합성 검사 C
  change.py   변경 Δ, 효과 연산, 합성
  universe.py 원고 → 우주(U, 명제, 매개변수, 패턴) → S₀
  cond.py     조건의 평가 (S, h)와 (F, hᵥ) 공통
  view.py     관찰 V: E, F, B, M, hᵥ
  log.py      사건, 기록, 이력 요약 h
  save.py     스냅숏, 기록에서 다시 만들기
```

이 패키지는 모델도 규칙도 모릅니다. 규칙의 술어(`owes`, `due`, `spent`)와 연산(`assert`, `expire` 등)은 [rule.md](../theory/rule.md) 7절이 모형에 더한 것이라 여기서 함께 표현합니다.

## 1. 원칙

| 원칙 | 근거 |
|---|---|
| 상태는 원자의 집합과 **같은 뜻**인 색인으로 저장하고, 적합성 `C`의 대부분을 자료 구조가 지킨다 | 온톨로지 2.1, 6.3 |
| 세계를 바꾸는 코드는 `change.py`의 연산뿐이다 | 공리 2, P1, P8 |
| 저장의 근원은 기록이다. 상태와 기억은 기록에서 다시 만드는 캐시다 | 공리 3, 정리 1 |
| 조건은 하나의 평가기로, 세계와 관찰 위에서 같은 방식으로 평가한다 | 온톨로지 2.3, 7.4 |
| 출력에 영향을 주는 모든 순회는 선언 차례나 정렬된 차례를 따른다 | P2 |

마지막 원칙은 파이썬 `set`의 순회 차례가 실행마다 달라질 수 있기 때문입니다. 차례가 결과를 바꾸는 곳(복잡화 후보, 위협의 도착, 방아쇠)은 늘 원고의 선언 차례를 쓰고, 그 밖의 집합은 정렬해서 내보냅니다.

## 2. 원자와 상태

### 2.1 원자

원자는 술어 이름을 첫 칸에 둔 튜플입니다. JSON으로는 배열이 됩니다.

```python
Atom = tuple[str, ...]          # ("at", "key", "dohae"), ("fill", "door", 2)
```

| 술어 | 원자 | 출처 |
|---|---|---|
| `at` | `("at", x, y)` | 온톨로지 6.2 |
| `link` | `("link", p, q)` | |
| `mark` | `("mark", x, kind, life, slot)` | kind `edge`·`snag`, life `scene`·`chapter`·`scar` |
| `believes` | `("believes", g, p)` | |
| `regards` | `("regards", g, h, axis, n)` | rule 7절의 축 |
| `fill` | `("fill", o, n)` | |
| `stat` | `("stat", g, s, n)` | 방식 넷, `beats`, `wounds`, `growth`, 특성 id(값 1) |
| `flag` | `("flag", f, v)` | `chapter`, `ending`, 원고 플래그, 발동 플래그 |
| `owes` | `("owes", g, h, k)` | rule 7절. `k`는 약속 id 또는 `kindness` |
| `due` | `("due", g, c)` | rule 7절 |
| `spent` | `("spent", g, s)` | rule 7절 |

`blocks`는 저장하지 않는 유도 원자입니다(story.md 7절 1). 조건 평가와 `V`가 `at`, `fill`과 원고의 `blocks`에서 계산합니다. 영구 태그의 수명 이름은 `scar`입니다(rule 6.2의 `영구`).

### 2.2 상태

`State`는 술어마다 색인 하나를 두고, `atoms()`가 원자의 집합을 돌려줍니다. 두 표현은 일대일입니다.

| 술어 | 색인 | 자료 구조가 지키는 것 |
|---|---|---|
| `at` | `dict[x, y]` | C1 한 곳 |
| `link`, `believes`, `owes`, `due`, `spent` | `set[tuple]` | - |
| `mark` | `dict[(x, slot), (kind, life)]` | C2 슬롯마다 하나 |
| `regards` | `dict[(g, h, axis), n]` | C2 |
| `fill` | `dict[o, n]` | C2 |
| `stat` | `dict[(g, s), n]` | C2 |
| `flag` | `dict[f, v]` | C2 |

C3(칸 상한)와 rule 7절의 한도는 `set` 연산이 값을 한도에서 멈추게 해서 지킵니다(3.2). C4(무리)는 이 형식에 무리가 없어 비어 있습니다(story.md 7절 13). 그래도 `conforms(S)`는 C1~C4와 한도를 원자 집합 위에서 다시 검사합니다. 자료 구조가 지키는 것을 다시 재는 이 검사는 퍼징(story.md V6)과 다시 만들기(6.3)에서만 씁니다.

**기본값을 원자로 둡니다.** `fill`, 플레이어의 `stat`(방식 넷, `beats`, `wounds`, `growth`), 인물마다 플레이어를 보는 `regards`(두 축)는 `S₀`에 값 0인 원자로도 들어갑니다. 원자가 없는 것과 0인 것을 구별하지 않으면 조건 `{fill: [o, "=", 0]}`이 원자의 유무에 따라 달라지기 때문입니다. 플레이어가 인물을 보는 `regards`는 쓰는 장치가 없어 두지 않습니다.

`State`는 바꾸지 않는 값으로 다룹니다. `apply(S, Δ)`는 새 상태를 돌려주고, 규칙은 한 단계를 작업 사본에서 계산합니다(P3, 3.3).

## 3. 변경과 연산

### 3.1 변경

```python
@dataclass(frozen=True)
class Delta:
    add: frozenset[Atom]
    remove: frozenset[Atom]      # add ∩ remove = ∅
```

`apply(S, Δ) = (S ∖ remove) ∪ add`(온톨로지 2.1의 `⊕`)입니다. 한 단계의 `Δ`는 효과 연산을 차례로 합성한 결과이고, 저장할 때는 **차이**로 줄입니다: `add = S* ∖ S`, `remove = S ∖ S*`. `S ⊕ Δ_합성 = S ⊕ Δ_차이`이므로 다시 만들기(정리 1)가 같고, 같은 단계에서 빠졌다 다시 들어온 원자처럼 결과에 없는 변화가 기록과 서술에 남지 않습니다.

### 3.2 연산

연산은 `op(work, …)` 꼴의 함수이고, 작업 상태 `work`를 읽고 고칩니다. 앞 연산이 고친 상태를 다음 연산이 읽으므로 온톨로지 7.4의 차례 합성과 같습니다.

| 연산 | 하는 일 | 지키는 것 |
|---|---|---|
| `move(x, y)` | `at[x] = y`. `x = player`면 `y`는 장소, 아니면 거부 | C1, 플레이어의 위치 |
| `set_(pred, key, v)` | 값 또는 `"+n"`·`"-n"`. 상대값은 지금 값에 더하고, 결과를 한도에서 멈춤 | C2, C3, rule 7절 한도 |
| `reveal(g, p)` | `believes`에 더함 | - |
| `tag(x, kind, life)` | 빈 슬롯 중 가장 낮은 번호에(story.md 7절 14). 다 찼으면 `scar`를 건너뛰고 가장 낮은 번호를 비우고 그 자리에. `scar`밖에 없으면 하지 않음 | C2, rule 6.2 |
| `untag(x, slot)` | 그 슬롯을 비움 | - |
| `link(p, q)`, `unlink(p, q)` | | - |
| `retire(o)` | `at[o]`를 뺌. 위협과 갈림이면 그 등장 방아쇠의 발동 플래그도 놓음(story.md 7절 11) | C1 |
| `expire(life)` | 그 수명의 `mark`를 모두 뺌 | - |
| `assert_(atom)`, `retract(atom)` | `owes`, `due`, `spent` 원자 | `C` 밖의 술어 |
| `clear_spent(g)` | `g`의 `spent`를 모두 뺌 | - |

한도는 이렇습니다. `fill`은 `0…boxes`, `regards`는 `−3…3`, 방식은 `0…3`, `beats`는 `0…B`, `wounds`는 `0…wound_boxes`, `growth`는 `0…`. 슬롯 수는 `1…3`입니다(온톨로지 6.1). 모든 연산이 `C`를 보존하므로 차례 합성도 보존합니다(P1의 원고 효과 부분).

원고의 효과(story.md 2.4)는 이 연산으로 그대로 번역됩니다. `{set: [regards, g, h, axis, v]}`는 `set_("regards", (g, h, axis), v)`, `{tag: [x, kind, life, name]}`은 `tag(x, kind, life)`와 함께 기본 이름을 표현층에 둡니다(engine.md 6절).

### 3.3 원자성

규칙은 `Work(S)`라는 쓰기 시 복사 사본에서 단계를 계산하고 `Delta`를 돌려줍니다. 서비스는 그 단계의 사건을 만든 뒤 상태, 기록, 표현층을 한 번에 바꿉니다(engine.md 7절). 계산 도중 예외가 나면 사본만 버려지고 `S`와 `L`은 그대로입니다(P3).

## 4. 우주

`universe.py`는 원고(story.md의 형식)를 읽어 한 번 만들고 플레이 내내 바꾸지 않는 `Universe`를 만듭니다. 온톨로지의 "원고 상수"가 모두 여기 있습니다.

| 필드 | 내용 |
|---|---|
| `kind` | `id → 종류`(`agent`, `place`, `thing`, `obstacle`, `prop`)와 장애물의 하위 표시(`plain`, `clock`, `deadline`, `threat`, `fork`) |
| `name`, `aliases` | 틀 표 `𝔗`가 쓰는 이름. 엔진 개체의 이름은 원고의 `clock.name`, `deadline.name` |
| `props` | 명제 id → `text`, `about`, `shows`, `against`, 출처(story.md 2.5) |
| `params` | 개체별 원고 매개변수: 칸 수, 기본 위험, 어울림·어긋남, `blocks`, 해법, 복잡화, 화제, 부탁, `wants`, 감각 단서 등 |
| `chapters` | 장마다 목표 조건, 시계 id, 마감 id, 위기 효과, 목표 효과 |
| `triggers` | 엮은 원고 방아쇠의 목록(4.3) |
| `patterns` | 원고의 모든 `did`를 모은 `Pat`(5.2) |
| `flags` | 플래그 이름 → 값의 유한 집합 |
| `limits` | `B`, `wound_boxes`, 슬롯 수 |

### 4.1 엔진 id

엔진이 만드는 개체와 명제는 `.`이 든 id를 씁니다. 원고 id는 소문자, 숫자, `_`뿐이라 겹치지 않습니다.

| 것 | id |
|---|---|
| 장 `k`의 위험 시계, 마감 | `clock.k`, `deadline.k` |
| 숨음, 단서 명제 | `x.hidden`, `x.clue` |
| 엔진의 복잡화 | `engine.snag`, `engine.beat`, `engine.wound`, `engine.end` |
| 엔진이 엮는 방아쇠 | 위협·갈림의 등장 `appear.<id>`, 장 목표 `goal.<k>`, 결말 `end.<id>` |
| 방아쇠의 발동 플래그 | `fired_<방아쇠 id>`(원고 방아쇠와 위의 엮은 방아쇠 모두). 플래그 이름이라 개체 id와 따로이고, story.md가 `fired_`를 예약해 원고 플래그와 겹치지 않음 |

### 4.2 시작 상태

`initial(universe, creation) → State`. `creation`은 플레이어가 고른 방식 배분과 특성입니다(story.md 3.2).

1. 원고의 `at`, `exits`(→ `link`), 인물의 `beliefs`(→ `believes`), `regards`를 원자로 옮깁니다.
2. 모든 장애물(시계, 마감, 위협, 갈림 포함)에 `fill 0`. 첫 장의 시계와 마감에 `at(·, player)`.
3. 플레이어의 `stat`: 방식 넷은 `creation`의 배분, 특성마다 1, `beats`·`wounds`·`growth`는 0.
4. 인물마다 플레이어를 보는 `regards` 두 축(없으면 0). 잠재가 데려오는 인물도 넣습니다. `at`이 없고 숨어 있어 보이지 않습니다.
5. `flag(chapter, 1)`과 선언한 원고 플래그의 시작 값.

`creation`이 원고의 `approaches` 값들의 배치이고 특성이 `pick`개인지는 여기서 검사합니다. 같은 원고와 `creation`은 같은 `S₀`를 냅니다.

### 4.3 방아쇠 엮기

원고 방아쇠는 `Trigger(id, when, effects, repeat, kind)`로 엮고, story.md 3.11의 차례(등장, `triggers`, 장 목표, 결말)를 지킵니다. `repeat`가 아니면 `when`에 `not flag(fired_id, 1)`, 효과 끝에 `set(flag, fired_id, 1)`을 더합니다. 장 목표와 결말의 효과는 엔진의 매크로 연산(`chapter_to(k+1)`, `end(e)`)이고, 그 내용은 [rule.md](rule.md) 5절이 정합니다.

## 5. 기록과 이력

### 5.1 사건

```python
@dataclass(frozen=True)
class Event:
    t: int
    action: str                  # canonical action id (story.md 3.12)
    roll: tuple[int, int, int] | None   # (d1, d2, u) only when the step rolled
    result: str                  # success, mixed, fail, none, blocked (rule.md 6)
    delta: Delta                 # minimal difference (3.1)
    witnesses: tuple[str, ...]   # sorted
    mods: tuple[Atom, ...]       # atoms that adjusted the roll, in rule order
```

온톨로지 2.2의 `e = (t, a, r, Δ, W, mods)`에 `R`이 정한 결과 `result`를 더한 것입니다. 굴림이 없는 단계는 `r`을 쓰지 않으므로 `roll`을 비웁니다. 굴린 결과는 `roll`과 `mods`에서 계산되지만, 굴림 없이 이루어진 것(`none`)과 숨은 막힘이 드러난 것(`blocked`)은 `Δ`를 해석해야 구별되므로 결과를 함께 저장하고 패턴이 그것을 읽습니다. **목격자**는 행동 직전과 직후에 플레이어가 있던 장소의 agent들입니다(온톨로지 7.3).

기록 `L`은 사건의 목록이고 덧붙기만 합니다. 사건을 고치거나 지우는 함수를 두지 않습니다(P4).

### 5.2 패턴과 이력 요약

`Pat`은 원고의 `did`들과 엔진의 패턴(부탁의 횟수, [rule.md](rule.md) 5.1)입니다. 패턴은 `(앞부분 조각들, 판단 인자들, 결과의 집합)`으로 컴파일하고(결과를 적지 않으면 모든 결과), `matches(pattern, action, outcome)`가 사건 하나에 대해 판정합니다. `h(L)`은 맞은 패턴 번호의 집합이고, 사건을 덧붙일 때마다 그 사건이 맞는 패턴을 더합니다.

**보이는 이력은 `h`와 같습니다.** 패턴은 행동 id와 결과만 보고(story.md 7절 12), 모든 사건의 행위자가 플레이어라 `p★ ∈ W`이며, 플레이어의 기억 투영은 행동과 결과를 그대로 남깁니다(6.3). 그래서 사건의 투영이 맞는 패턴은 사건이 맞는 패턴과 같고 `hᵥ = h`입니다. 패턴이 `Δ`나 목격자를 읽게 되면 이 등식이 깨지므로 두 집합을 나눠야 합니다.

## 6. 조건과 관찰

### 6.1 조건 평가

`cond.py`는 story.md 2.3의 조건을 AST로 컴파일하고 `holds(c, facts, hist)`로 평가합니다. `facts`는 `State`이거나 관찰의 `F`(같은 `State` 형식, 6.2)이고 `hist`는 패턴 번호의 집합입니다. 세계 평가는 `holds(c, S, h)`, 보임 평가는 `holds(c, F, hᵥ)`입니다. 평가기가 하나라서 두 평가가 다른 것은 오직 받는 원자 집합의 차이입니다. 유도 원자 `blocks`와 숨음은 받은 원자 집합 위에서 계산합니다.

### 6.2 관찰 `V`

`observe(U, S, L, o) → Obs`는 온톨로지 7.2를 그대로 옮깁니다.

```python
@dataclass(frozen=True)
class Obs:
    observer: str
    seen: frozenset[str]          # E
    facts: State                  # F, a sub-state of S
    beliefs: tuple[str, ...]      # B, in reveal order
    memory: tuple[Seen, ...]      # M
    hist: frozenset[int]          # hᵥ
```

1. **숨음**: `hidden(x)`는 `x`를 `shows`하는 명제가 있고 그중 어느 것도 `o`가 믿지 않는 것입니다.
2. **`E`**: `o`, `o`가 지닌 것(`at(x, o)`, 지닌 시계와 위협 포함), `here(o)`, `here`에 있는 숨지 않은 개체, `link(here, q)`인 숨지 않은 장소 `q`.
3. **`F`**: `S`의 원자 중 술어별 규칙(온톨로지 7.2 표와 rule 7절의 `owes`, `due`, `spent`)을 통과한 것. 이 규칙을 `fact_rule(o, S, atom)`으로 두고, `F`와 기억 투영이 같은 함수를 씁니다.
4. **`B`**: `believes(o, p)`의 `p`들. 믿게 된 차례(기록에서 처음 더해진 사건)로 줄 세웁니다. 시작부터 믿는 것은 원고 차례입니다.
5. **`M`**, **`hᵥ`**: 6.3.

`F ⊆ S`는 구성으로 성립합니다(P9의 앞 절반). 관찰은 `S`, `L`, `U`만 읽고 표현층을 읽지 않습니다.

### 6.3 기억

기억 `M(o)`의 원소는 사건 하나의 투영입니다.

```python
@dataclass(frozen=True)
class Seen:
    t: int
    action: str
    roll: tuple[int, int, int] | None
    result: str
    witnesses: tuple[str, ...]    # W ∩ E_e
    delta: Delta                  # Δ ∩ F-rule_e
    mods: tuple[Atom, ...]        # mods ∩ F-rule_e
```

`E_e`와 `F-rule_e`는 사건 직전과 직후 상태에서 계산한 것의 합입니다. 투영은 사건을 덧붙일 때 직전과 직후 상태가 손에 있으므로 그때 계산해 캐시에 둡니다.

| 캐시 | 내용 | 쓰는 곳 |
|---|---|---|
| `seen[player]` | 플레이어가 목격한 사건의 투영 | `δ`(engine.md 5절), 단계 기록, 되돌아보기 |
| `seen[g]` | 인물 `g`가 목격한 사건을 `g`의 규칙으로 투영하고 다시 플레이어의 규칙으로 거른 것 | 인물 기억(온톨로지 7.5) |

모든 사건의 행위자가 플레이어이므로 `seen[g]`의 사건은 모두 플레이어도 목격한 것입니다. 그래서 "플레이어가 함께 보지 않은 사건"(온톨로지 7.2)은 이 모형에서 생기지 않습니다. 캐시는 저장하지 않고, 불러올 때 기록을 다시 따라가며 같은 함수로 다시 만듭니다(7.3). 그래서 기억은 기록의 함수라는 온톨로지 7.2의 조건이 코드에서도 성립합니다.

## 7. 저장

### 7.1 스냅숏

게임 하나는 `saves/engine/g_<id>.json` 하나입니다.

```json
{
  "schema_version": 2,
  "story": {"id": "lighthouse", "version": 1, "digest": "sha256:…"},
  "seed": 4821930017,
  "creation": {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]},
  "log": [{"t": 0, "action": "go:village", "roll": null, "result": "none", "delta": {"add": [["at", "player", "village"], ["stat", "player", "beats", 1]], "remove": [["at", "player", "dock"], ["stat", "player", "beats", 0]]}, "witnesses": ["dohae", "player", "yunseul"], "mods": []}],
  "presentation": {}
}
```

상태 `S`는 저장하지 않습니다. `presentation`은 표현층 `P`이고 그 내용은 engine.md 6절입니다. `digest`는 원고 파일의 바이트 해시입니다.

### 7.2 쓰기

임시 파일에 쓰고 `fsync` 후 `rename`으로 바꿉니다. 한 요청의 상태, 기록, 표현층은 이 한 번의 쓰기로 함께 바뀝니다(P3, P4). 서버는 프로세스 하나이고 게임마다 잠금 하나를 둡니다(engine.md 7절).

### 7.3 다시 만들기

`load(path) → Game`:

1. `schema_version`이 다르거나 원고의 `digest`가 다르면 거부합니다. 원고가 바뀌면 `U`와 `S₀`가 달라질 수 있기 때문입니다. 엔진 코드가 바뀐 것은 거부하지 않습니다. 다시 만들기가 `R`을 다시 돌리지 않기 때문입니다(정리 1의 따름).
2. `S₀ = initial(U, creation)`에서 사건마다 `S ← apply(S, e.delta)`. 단계마다 `conforms(S)`를 확인하고, 어긋나면 거부합니다(망가진 파일).
3. 같은 순회에서 `h`, 기억 캐시, 믿게 된 차례를 다시 만듭니다.

다시 만들기의 비용은 사건 수에 비례합니다. 한 게임은 수백 사건이라 불러올 때마다 다시 만듭니다.

## 8. 의무와 검사

| 의무 | 지키는 곳 | 테스트 |
|---|---|---|
| P1 보존 | 3.2의 연산만 상태를 바꿈, `State`가 C1·C2를 구조로 지킴 | 연산마다 성질 테스트, 무작위 행동열 퍼징에서 단계마다 `conforms` |
| P2 결정성 | `R`과 연산이 시각, 난수, 표현층을 읽지 않음, 순회 차례(1절) | 같은 입력 두 번, `PYTHONHASHSEED`를 바꿔 같은 결과 |
| P3 원자성 | `Work` 사본, 한 번의 저장(3.3, 7.2) | 연산 중간에 예외를 넣어 상태와 파일이 그대로인지 |
| P4 기록 | 덧붙임만 있는 `log`, 영수증(engine.md 7절) | 저장 후 다시 만든 상태가 메모리 상태와 같음 |
| P6 관찰 순수성 | `observe`가 `S`, `L`, `U`만 읽음. 화면과 프롬프트는 `Obs`만 받음 | 숨은 원자만 다른 두 상태 → 같은 `Obs`, 같은 화면, 같은 프롬프트 |
| P7 일반성 | `onto/`에 이야기 id, 이름, 문장이 없음 | 경계 테스트(뼈대 이야기의 id와 이름을 `src/`에서 찾음) |
| P8 원고 적합 | `universe.py`, `initial`, story.md V1~V2 | 시작 시 검증 |
| P9 표현의 건전성 | `F ⊆ S`(6.2), 믿음은 따로 | 렌더러가 `F`와 `B` 밖의 원자를 쓰지 않음 |

P5, P10, P11은 규칙의 일입니다([rule.md](rule.md) 8절).

## 9. 여기서 정한 것

| | 자리 | 정한 것 | 이유 |
|---|---|---|---|
| 1 | 상태의 표현 | 술어별 색인. 원자 집합과 일대일 | C1, C2가 구조로 성립하고 조회가 빠름 |
| 2 | 기본값 | `fill`, 플레이어의 `stat`, 인물이 플레이어를 보는 `regards`는 0도 원자로 둠 | 조건이 원자의 유무와 값 0을 구별하지 않게 함 |
| 3 | 저장하는 `Δ` | 합성의 결과를 차이로 줄인 것 | `⊕`의 결과가 같고, 서술과 기억에 남는 변화가 실제 변화와 같음 |
| 4 | `hᵥ` | `h`와 같게 둠 | 패턴과 사건의 모양에서 증명됨(5.2) |
| 5 | 저장의 근원 | 기록만 저장하고 상태와 기억은 다시 만듦 | 정리 1. 저장된 상태와 기록이 어긋날 길이 없음 |
| 6 | 원고가 바뀐 저장 | 거부 | `U`와 `S₀`가 달라지면 기록의 원자가 뜻을 잃음 |
| 7 | 엔진 id | `.`이 든 id | 원고 id와 겹치지 않음을 문법으로 보장 |
| 8 | 사건의 결과 | `result`를 사건에 저장 | 굴림 없는 이룸과 막힘을 패턴이 `Δ`를 해석하지 않고 가름 |
