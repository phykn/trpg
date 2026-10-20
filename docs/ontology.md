# 온톨로지

세계는 원자의 유한 집합이고, 그것을 바꾸는 것은 규칙 `R`뿐이며, 플레이어와 모델은 관찰 `V`만 받습니다. 이 문서는 세계의 정의와 불변식, 어휘, 관찰, 변경 연산, 그리고 그것을 옮긴 `server/src/onto/`와 저장 형식을 정합니다. 행동과 판정은 [rule.md](rule.md), 원고 형식은 [story.md](story.md), 모델과 프로토콜은 [engine.md](engine.md)입니다.

```
server/src/onto/
  atoms.py    원자, 상태 State
  change.py   변경 Delta, 효과 연산, 작업 사본 Work
  universe.py 우주 Universe, 시작 상태 S₀, 적합성 검사 conforms
  cond.py     조건 평가 holds — 세계 (S, h)와 관찰 (F, hᵥ) 공통
  view.py     관찰 observe: E, F, B, M, hᵥ
  log.py      사건 Event, 기록 L, 패턴, 이력 요약 h
  save.py     스냅숏 쓰기, 기록에서 다시 만들기
```

이 패키지는 모델도 규칙도 모릅니다. 규칙이 더한 술어(`owes`, `spent`)와 연산(`assert_`, `expire` 등)도 여기 둡니다.

## 1. 세계

### 1.1 원자와 상태

- 개체 종류 `𝒯 = {agent, place, thing, obstacle, prop}`. 개체의 유한 집합 `U`는 원고가 정하고 플레이 중 바뀌지 않습니다.
- 값 종류 `𝒱`는 모두 유한합니다(1.3). 수의 범위는 값 종류가 정합니다.
- 술어 `Σ`(1.2)마다 자리의 종류가 정해지고, 자리마다 종류가 맞는 바닥 원자 전체가 `Atom`입니다. 유한합니다.
- **상태** `S ⊆ Atom`. 원자가 `S`에 있으면 참, 없으면 거짓입니다(닫힌 세계).
- **변경** `Δ = (Δ⁺, Δ⁻)`, `Δ⁺ ∩ Δ⁻ = ∅`. `S ⊕ Δ = (S ∖ Δ⁻) ∪ Δ⁺`.

코드에서 원자는 술어 이름을 첫 칸에 둔 튜플이고 JSON으로는 배열입니다.

```python
Atom = tuple[str, ...]          # ("at", "key", "dohae"), ("fill", "door", 2)
```

`State`는 술어마다 색인 하나를 두고 `atoms()`가 원자 집합을 돌려줍니다. 두 표현은 일대일이고, 색인이 적합성(1.4)의 대부분을 구조로 지킵니다.

| 술어 | 색인 | 구조가 지키는 것 |
|---|---|---|
| `at` | `dict[x, y]` | C1 |
| `link`, `believes`, `owes`, `follows`, `due`, `spent` | `set[tuple]` | |
| `mark` | `dict[(x, slot), (kind, life)]` | C2 |
| `regards` | `dict[(g, h, axis), n]` | C2 |
| `fill` | `dict[o, n]` | C2 |
| `stat` | `dict[(g, s), n]` | C2 |
| `flag` | `dict[f, v]` | C2 |

`State`는 바꾸지 않는 값입니다. `apply(S, Δ) = (S ∖ Δ⁻) ∪ Δ⁺`는 새 상태를 돌려주고, 한 단계의 계산은 쓰기 시 복사 사본 `Work(S)` 위에서 합니다(4절).

**기본값도 원자로 둡니다.** `fill`, 플레이어의 `stat`(방식 넷, `beats`, `wounds`, `growth`), 인물마다 플레이어를 보는 `regards` 두 축은 `S₀`에 값 0인 원자로 들어갑니다. 조건 `{fill: [o, "=", 0]}`이 원자의 유무에 따라 달라지지 않게 하기 위해서입니다. 플레이어가 인물을 보는 `regards`는 쓰는 장치가 없어 두지 않습니다.

### 1.2 술어

| 술어 | 원자 | 뜻 |
|---|---|---|
| `at(x, y)` | `("at", x, y)` | agent·thing·obstacle `x`가 place `y`에 있다. `y`가 agent면 지닌다 |
| `link(p, q)` | `("link", p, q)` | 장소 `p`에서 `q`로 갈 수 있다 |
| `mark(x, k, l, i)` | `("mark", x, kind, life, slot)` | `x`에 걸린 태그 하나. kind `edge`(유리)·`snag`(불리), life `scene`·`chapter`·`scar`(영구), slot `1…3` |
| `believes(g, p)` | `("believes", g, p)` | agent `g`가 명제 `p`를 믿는다 |
| `regards(g, h, 축, n)` | `("regards", g, h, axis, n)` | `g`가 `h`를 보는 눈. 축 `trust`·`fear`, `n ∈ −3…3` |
| `fill(o, n)` | `("fill", o, n)` | 장애물 `o`의 찬 칸 |
| `stat(g, s, n)` | `("stat", g, s, n)` | 시트 항목. `s`는 방식 넷(`force`, `finesse`, `wits`, `charm`), `beats`, `wounds`, `growth`, 특성 id(값 1) |
| `flag(f, v)` | `("flag", f, v)` | `chapter`, `ending`, 원고 플래그, 발동 플래그 `fired_*` |
| `owes(g, h, k)` | `("owes", g, h, k)` | `g`가 `h`에게 진 것. `k`는 `promise`(`h`의 부탁에 걸린 약속) 또는 `kindness`(호의) |
| `follows(h, g)` | `("follows", h, g)` | agent `h`가 `g`(플레이어)와 함께 다닌다. `g`가 옮기면 따라 옮긴다 |
| `due(g, c)` | `("due", g, c)` | 옛 규칙의 고를 대가. 이 규칙 전의 저장을 읽도록 색인에만 남았고 아무것도 만들지 않음 |
| `spent(g, s)` | `("spent", g, s)` | 이 장에서 이미 기댄 특성 `s` |

`blocks(o, x)`("o가 x를 막는다")는 저장하지 않는 유도 원자입니다. 원고의 `blocks` 목록에서 `at(o, ·)`이 있고 `fill(o) < 칸 수`인 동안 참이며, 조건 평가와 관찰이 받은 원자 집합 위에서 계산합니다.

### 1.3 값과 한도

| 값 종류 | 범위 |
|---|---|
| 호감 `regards` | `−3…3` |
| 칸 `fill` | `0…칸 수`(장애물마다 `1…6`) |
| 방식 값 | `0…3` |
| `beats` | `0…B`(원고의 장면 길이) |
| `wounds` | `0…wound_boxes` |
| `growth` | `0…` |
| 슬롯 | `1…3` |
| 방식 | `{force, finesse, wits, charm}` |
| 태그 | kind `{edge, snag}`, life `{scene, chapter, scar}` |
| 플래그 값 | 원고가 선언한 유한 집합 |

`set_` 연산은 결과를 범위의 양 끝에서 멈춥니다(4절).

### 1.4 적합성 `C`

- **C1 한 곳**: agent·thing·obstacle마다 `at(x, ·)`는 많아야 하나.
- **C2 함수성**: `regards(g, h, 축, ·)`, `fill(o, ·)`, `stat(g, s, ·)`, `flag(f, ·)`, `mark(x, ·, ·, i)`는 각각 많아야 하나.
- **C3 한도**: 모든 값이 1.3의 범위 안.
- **C4 동행**: `follows(h, g)`가 있으면 `at(h, ·)`와 `at(g, ·)`의 장소가 같다.

모두 "이런 원자 조합은 없다"는 문장이라 부분집합(`F`)에서도 성립합니다. "플레이어는 늘 장소 하나에 있다"는 존재 조건이라 `C`가 아니라 시작 상태(5.2)와 `move` 연산이 지킵니다. 무리(장소 없는 agent)는 두지 않습니다. `conforms(S)`는 C1~C4를 원자 집합 위에서 다시 검사하며, 퍼징(story.md V6)과 다시 만들기(6절)에서만 씁니다.

## 2. 전이와 기록

- **행동** `a`: 스키마에 인자를 채운 것으로, 정규형 행동 id(story.md 3.12)와 일대일입니다. 모든 행동의 집합 `Act`는 유한합니다.
- **주사위** `rₜ = H(seed, t)`. `H`는 고정 함수(rule.md 3.1), `seed`는 게임마다 하나.
- **규칙** `R(S, h, a, r) = (Δ, mods)`. `mods ⊆ Atom`은 판정을 보정한 원자들.
- **사건** `e = (t, a, r, Δ, W, mods, result)`. 목격자 `W`는 행동 직전과 직후에 플레이어가 있던 장소의 agent들.
- **기록** `L`: 사건의 열. `L₀ = ε`.
- **이력 요약** `h(L) ⊆ Pat`: 원고의 `did` 패턴과 엔진 패턴(rule.md 5.1) 중 `L`의 어떤 사건이 맞는 것. 패턴은 사건의 행동 id와 결과만 읽고 `t`는 보지 않으며, 한 번 들어간 패턴은 빠지지 않습니다.

세계는 다음 다섯 불변식으로만 움직입니다.

| 불변식 | 내용 |
|---|---|
| 전이 | `(Δₜ, modsₜ) = R(Sₜ, h(Lₜ), aₜ, rₜ)`, `Sₜ₊₁ = Sₜ ⊕ Δₜ`. 서술, 모델의 답, 화면은 `R`의 인자가 아니므로 세계를 바꾸지 못한다 |
| 기록 | `Lₜ₊₁ = Lₜ · eₜ`. 덧붙기만 한다 |
| 허용 | 실행되는 행동은 그때의 후보다: `aₜ ∈ K(Vₜ)`. 되묻기, 거절, 카드는 행동이 아니며 `t`를 늘리지 않고 사건을 만들지 않는다 |
| 비간섭 | 턴 `t`에 플레이어와 모델이 받는 모든 것은 `(Vₜ, 외생 입력)`의 함수다(서술은 `Vₜ₊₁`). 외생 입력은 플레이어의 문장, 이전 모델 출력, 모델의 난수 |
| 일반성 | `R`, `V`, `K`, `W`, `h`, `C`는 개체를 이름으로 알지 못한다. 종류를 보존하는 이름 바꾸기에 결과가 그대로 따라간다 |

코드의 변경과 사건:

```python
@dataclass(frozen=True)
class Delta:
    add: frozenset[Atom]
    remove: frozenset[Atom]      # add ∩ remove = ∅

@dataclass(frozen=True)
class Event:
    t: int
    action: str                  # canonical action id (story.md 3.12)
    roll: tuple[int, int, int] | None   # (d1, d2, u) only when the step rolled
    result: str                  # success, fail, none, blocked
    delta: Delta                 # minimal difference
    witnesses: tuple[str, ...]   # sorted
    mods: tuple[Atom, ...]       # atoms that adjusted the roll, in rule order
```

한 단계의 `Δ`는 효과 연산을 차례로 합성한 것이지만 저장할 때는 **차이**로 줄입니다: `add = S* ∖ S`, `remove = S ∖ S*`. 결과 상태가 같고, 같은 단계에서 빠졌다 다시 들어온 원자가 기록과 서술에 남지 않습니다. `result`는 굴림 없이 이룬 `none`과 숨은 막힘이 드러난 `blocked`를 `Δ`를 해석하지 않고 가르기 위해 저장합니다.

패턴은 `(앞부분 조각들, 판단 인자들, 결과의 집합)`으로 컴파일하고(결과를 적지 않으면 모든 결과) `matches(pattern, action, result)`로 사건 하나를 판정합니다. `h(L)`은 맞은 패턴 번호의 집합이며 사건을 덧붙일 때 갱신합니다. 사건을 고치거나 지우는 함수는 없습니다.

## 3. 명제와 관찰

### 3.1 명제

명제 `p`마다 원고가 `text(p)`(모델에게 건네는 문장), `about(p)`·`shows(p) ⊆ U`(무엇에 대한 말인가, 믿으면 무엇이 보이는가), `against(p)`(함께 믿을 수 없는 명제들), 그리고 선택으로 뜻 `⟦p⟧`(`Σ` 위의 문장)를 줍니다. 뜻이 없는 명제는 원고가 정한 참·거짓 상수입니다(story.md 2.5).

- **참** `true(p, S) ⟺ S ⊨ ⟦p⟧`. 세계가 바뀌면 명제의 참거짓도 바뀝니다.
- **앎** `knows(g, p, S) ⟺ believes(g, p) ∈ S ∧ true(p, S)`. 저장하지 않습니다. 거짓 믿음은 허용되며 판정은 `S`로 합니다.
- **숨음** `hidden(x, o, S)`: `x`를 `shows`하는 명제가 있고 그중 어느 것도 `o`가 믿지 않음.
- **들통**: 플레이어가 대화에서 원고 명제 `p`를 주장했고 듣는 이가 `against(p)`의 명제를 믿으면 들통입니다. 원고 명제에 맞지 않는 주장은 사건에 문장으로만 남고 들통의 근거가 되지 않습니다.

### 3.2 관찰 `V`

`observe(U, S, L, o) → Obs`. `here(o)`는 `at(o, q) ∈ S`인 장소 `q`입니다.

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

1. **`E`** 보는 개체: `o` 자신, `o`가 지닌 것(물건, 시계, 위협), `here(o)`, 거기 있는 숨지 않은 개체, `link(here, q)`인 숨지 않은 장소 `q`. 믿는 명제로만 아는 먼 개체는 `E`에 넣지 않습니다. 그 개체는 명제의 문장 속 이름으로만 전해지고, 지금 장소나 이어진 곳에 오면 그때 들어옵니다.
2. **`F`** 보이는 사실: `S`의 원자 중 아래 규칙에 맞는 것. `F ⊆ S`는 구성으로 성립합니다. 규칙은 `fact_rule(o, S, atom)` 하나이고 기억 투영도 같은 함수를 씁니다.

| 술어 | 보이는 조건 |
|---|---|
| `at`, `link`, `mark`, `fill` | 개체 자리가 모두 `E` 안 |
| `stat(g, ·)`, `believes(g, ·)`, `due(g, ·)`, `spent(g, ·)` | `g = o` |
| `regards(g, h, ·)`, `owes(g, h, ·)`, `follows(g, h)` | `g = o` 또는 `h = o` |
| `flag` | 보이지 않음 |

3. **`B`** 믿음: `believes(o, p)`의 `p`들을 믿게 된 차례(기록에서 처음 더해진 사건, 시작부터면 원고 차례)로. 각 `text(p)`를 건네되 `⟦p⟧`를 `F`에 섞지 않습니다.
4. **`M`** 기억: `o ∈ W`인 사건마다 그때 보인 부분만 남긴 투영. `Eₑ`, `F규칙ₑ`는 사건 직전과 직후 상태에서 계산한 것의 합입니다.
5. **`hᵥ`**: `M`의 사건이 맞는 패턴들. 패턴은 행동 id와 결과만 읽고 모든 사건의 행위자가 플레이어라 투영이 그 둘을 그대로 남기므로 `hᵥ = h`입니다. 패턴이 `Δ`나 목격자를 읽게 되면 둘을 나눠야 합니다.

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

투영은 사건을 덧붙일 때 계산해 캐시에 둡니다. 플레이어의 투영 `seen[player]`만 만들며, 서술 입력 `δ`, 단계 기록, 되돌아보기와 문맥의 기억 줄에 씁니다. 인물에게는 자기 프롬프트가 없으므로 인물별 투영은 두지 않습니다. 기억은 프롬프트에만 쓰고 `R`과 조건은 `h(L)`만 읽습니다. 캐시는 저장하지 않고 불러올 때 다시 만듭니다.

관찰은 `S`, `L`, `U`만 읽고 표현층(engine.md 6절)을 읽지 않습니다.

### 3.3 조건과 후보

조건(story.md 2.3)은 `cond.py`가 AST로 컴파일하고 `holds(c, facts, hist)`로 평가합니다. 세계 평가는 `holds(c, S, h)`, 보임 평가는 `holds(c, F, hᵥ)`이며 평가기가 하나라 둘의 차이는 받는 원자 집합뿐입니다. 유도 원자 `blocks`와 숨음은 받은 집합 위에서 계산합니다.

후보 `K(O)`는 `(E, F, B, hᵥ)`와 원고 상수만 읽습니다(rule.md 2절). 개체 인자는 `E` 안, 명제 인자는 `B` 안, 조건은 `(F, hᵥ)` 위에서 평가하며, 보이는 막힘이 없으면 막힘이 없다고 보는 일부러 낙관적인 평가입니다. 그래서 `R`은 보이는 조건은 참이지만 실제 조건은 거짓인 경우(숨은 막힘)에도 정의되어야 하고, 숨은 것을 아는 길은 행동해서 겪는 것뿐입니다. 화면이나 프롬프트에 나가는 조건(화제의 공짜 조건, 해법 이름)도 같은 보임 평가입니다.

## 4. 효과와 연산

세계를 바꾸는 코드는 `change.py`의 연산뿐입니다. 연산은 `op(work, …)` 꼴로 작업 사본 `Work(S)`를 읽고 고치며, 앞 연산이 고친 상태를 다음 연산이 읽습니다. 모든 연산이 `C`를 보존하므로 차례 합성도 보존합니다.

| 연산 | 하는 일 |
|---|---|
| `move(x, y)` | `at[x] = y`. `x = player`면 `y`는 장소여야 하며 아니면 거부하고, `follows(h, player)`인 `h`도 모두 `y`로 옮김. `x`가 누군가를 따라다니던 인물이면 그 `follows`를 뺌. 둘 다 C4를 지키기 위해서임 |
| `set_(pred, key, v)` | `regards`·`fill`·`stat`·`flag`의 값. `v`가 `"+n"`·`"-n"`이면 지금 값에 더하고, 결과를 1.3의 범위에서 멈춤. 값이 같으면 아무것도 하지 않음 |
| `reveal(g, p)` | `believes(g, p)`를 더함 |
| `tag(x, kind, life)` | 빈 슬롯 중 가장 낮은 번호에. 다 찼으면 `scar`를 건너뛰고 가장 낮은 번호를 비우고 그 자리에. `scar`밖에 없으면 하지 않음 |
| `untag(x, slot)` | 그 슬롯을 비움 |
| `link(p, q)`, `unlink(p, q)` | `link`를 더하거나 뺌 |
| `retire(o)` | `at[o]`를 뺌. 위협·갈림이면 등장 방아쇠의 발동 플래그도 놓음 |
| `expire(life)` | 그 수명의 `mark`를 모두 뺌 |
| `assert_(atom)`, `retract(atom)` | `owes`, `spent`, `follows` 원자 |
| `clear_spent(g)` | `g`의 `spent`를 모두 뺌 |

원고의 효과(story.md 2.4)는 이 연산으로 그대로 번역됩니다. `{set: [regards, g, h, axis, v]}`는 `set_("regards", (g, h, axis), v)`, `{tag: [x, kind, life, 이름]}`은 `tag(x, kind, life)`와 함께 기본 이름을 표현층에 둡니다.

**원자성**: 규칙은 `Work(S)` 위에서 한 단계를 계산해 `Delta`(차이)를 돌려주고, 서비스는 사건을 만든 뒤 상태, 기록, 표현층을 한 번의 저장으로 바꿉니다(engine.md 7절). 도중에 예외가 나면 사본만 버려집니다.

**순회 차례**: 출력에 영향을 주는 모든 순회(복잡화 후보, 위협의 도착, 방아쇠)는 원고의 선언 차례를 따르고 그 밖의 집합은 정렬해서 내보냅니다. 파이썬 `set`의 차례가 실행마다 다를 수 있기 때문입니다.

## 5. 우주와 시작 상태

`story/compile.py`가 원고를 읽어 플레이 내내 바꾸지 않는 `Universe`(`onto/universe.py`)를 만들고 방아쇠를 엮습니다.

| 필드 | 내용 |
|---|---|
| `kind` | `id → 종류`와 장애물의 하위 종류(`plain`, `clock`, `deadline`, `threat`, `fork`) |
| `name`, `aliases` | 이름 표. 엔진 개체의 이름은 원고의 `clock.name`, `deadline.name` |
| `props` | 명제 id → `text`, `about`, `shows`, `against`, 출처(story.md 2.5) |
| `params` | 개체별 원고 매개변수: 칸 수, 기본 위험, `fits`·`clashes`, `blocks`, 해법, 복잡화, 화제, 부탁, `wants`, 감각 단서 |
| `chapters` | 장마다 목표 조건, 시계 id, 마감 id, 위기 효과, 목표 효과 |
| `triggers` | 엮은 방아쇠 목록(5.3) |
| `patterns` | 원고의 모든 `did`와 엔진 패턴을 모은 `Pat` |
| `flags` | 플래그 이름 → 값의 유한 집합 |
| `limits` | `B`, `wound_boxes`, 슬롯 수 |

### 5.1 엔진 id

엔진이 만드는 개체·명제·방아쇠는 `.`이 든 id를 씁니다. 원고 id는 `[a-z0-9_]`뿐이라 겹치지 않습니다.

| 것 | id |
|---|---|
| 장 `k`의 위험 시계, 마감 | `clock.k`, `deadline.k` |
| 숨음, 단서 명제 | `x.hidden`, `x.clue` |
| 엔진의 복잡화 | `engine.snag`, `engine.beat`, `engine.wound`, `engine.end` |
| 엮은 방아쇠 | 위협·갈림의 등장 `appear.<id>`, 장 목표 `goal.<k>`, 결말 `end.<id>` |
| 방아쇠의 발동 플래그 | `fired_<방아쇠 id>`(원고 방아쇠와 엮은 방아쇠 모두) |

### 5.2 시작 상태

`initial(universe, creation) → State`. `creation`은 플레이어가 고른 방식 배분과 특성, 그리고 이름입니다(story.md 3.2). 이름은 화면에만 쓰고 `S₀`에 들어가지 않습니다. 같은 원고와 `creation`은 같은 `S₀`를 냅니다.

1. 원고의 `at`, `exits`(→ `link`), 인물의 `beliefs`, `regards`를 원자로.
2. 모든 장애물(시계, 마감, 위협, 갈림 포함)에 `fill 0`. 첫 장의 시계와 마감에 `at(·, player)`.
3. 플레이어의 `stat`: 방식 넷은 `creation`의 배분, 특성마다 1, `beats`·`wounds`·`growth`는 0.
4. 인물마다 플레이어를 보는 `regards` 두 축(없으면 0). 잠재가 데려오는 인물도 넣되 `at`이 없고 숨어 있습니다.
5. `flag(chapter, 1)`과 원고 플래그의 시작 값.

`creation`의 방식 값이 원고 `approaches`의 합을 다 쓰고 저마다 그 가장 큰 값 이하인지, 특성이 `pick`개인지는 여기서 검사합니다.

### 5.3 방아쇠 엮기

원고 방아쇠는 `Trigger(id, when, effects, repeat, kind)`로 엮고 story.md 3.11의 차례(등장, `triggers`, 장 목표, 결말)를 지킵니다. `repeat`가 아니면 `when`에 `not flag(fired_<id>, 1)`, 효과 끝에 `set(flag, fired_<id>, 1)`을 더합니다. 장 목표와 결말의 효과는 엔진의 매크로 `chapter_to(k+1)`, `end(e)`이며 내용은 rule.md 4.3입니다.

## 6. 저장

게임 하나는 `saves/engine/g_<id>.json` 하나이고, 저장의 근원은 기록입니다. 상태와 기억은 기록에서 다시 만드는 캐시라 저장하지 않습니다.

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

`presentation`은 표현층 `P`(engine.md 6절), `digest`는 원고 파일의 바이트 해시입니다.

- **쓰기**: 임시 파일에 쓰고 `fsync` 후 `rename`. 한 요청의 상태, 기록, 표현층이 이 한 번의 쓰기로 함께 바뀝니다. 서버는 프로세스 하나이고 게임마다 잠금 하나를 둡니다.
- **다시 만들기** `load(path) → Game`: `schema_version`이나 원고 `digest`가 다르면 거부합니다(`U`와 `S₀`가 달라지면 기록의 원자가 뜻을 잃음). 엔진 코드가 바뀐 것은 거부하지 않습니다. `R`을 다시 돌리지 않기 때문입니다. `S₀ = initial(U, creation)`에서 사건마다 `S ← apply(S, e.delta)`, 단계마다 `conforms(S)`를 확인하고 어긋나면 거부하며, 같은 순회에서 `h`, 기억 캐시, 믿게 된 차례를 다시 만듭니다. 비용은 사건 수에 비례하고 한 게임은 수백 사건입니다.

## 7. 성질과 검사

| 성질 | 내용과 이유 | 지키는 곳 | 검사 |
|---|---|---|---|
| 재현 | `Sₜ = S₀ ⊕ Δ₀ ⊕ … ⊕ Δₜ₋₁`. 원고와 기록만으로 상태를 다시 만들며 `R`, `seed`, 모델이 필요 없다(전이·기록 불변식의 귀납). `(이야기, seed, 행동열)`이 같으면 상태와 기록이 같다 | `save.py` | 저장 후 다시 만든 상태 = 메모리 상태; 같은 입력 두 번 → 같은 결과(`PYTHONHASHSEED`를 바꿔도) |
| 적합성 | 모든 `Sₜ ⊨ C`. `S₀ ⊨ C`이고 모든 연산이 `C`를 보존하므로. 모델이 어떤 답을 내도 같다 | `change.py`, `State` 구조 | 연산마다 성질 테스트; 무작위 행동열 퍼징에서 단계마다 `conforms` |
| 원자성 | 한 단계의 `Δ`는 전부 적용되거나 전혀 적용되지 않는다 | `Work`, 한 번의 저장 | 연산 중간에 예외 → 상태와 파일 그대로 |
| 비창조 | `U`, `Σ`가 상수이므로 모델은 개체도 술어도 만들지 못한다 | `universe.py`, `story/compile.py` | 사건의 원자가 모두 `Atom` 안 |
| 모델 영향의 한계 | 모델 출력이 세계에 닿는 길은 다음 행동 `aₜ ∈ K(Vₜ)`뿐이다(전이식의 인자 중 모델이 닿는 것이 그것뿐). 해석이 틀리면 원하지 않은 후보가 실행될 뿐 후보 밖의 일은 없다 | 허용 검사(rule.md 10절) | 후보 밖 id → 거절 |
| 비누설 | 관찰과 외생 입력이 같으면 플레이어와 모델이 받는 것이 같다. 숨은 사실이 닿는 길은 이후 관찰이 달라지는 것뿐 | `observe`가 `S`, `L`, `U`만 읽음; 화면·프롬프트·다시 쓰기 피드백은 `Obs`만 받음 | 숨은 원자만 다른 두 상태 → 같은 `Obs`, 같은 화면, 같은 프롬프트 |
| 한 근원 | 한 시점의 화면, 후보, 사실 목록, 프롬프트가 사실로 주장하는 것은 모두 `F ⊆ S`에 있어 함께 참이고 `C`를 어기지 않는다. 믿음은 믿음으로 표시한다 | 렌더러, `context` | 렌더러가 `F`와 `B` 밖의 원자를 쓰지 않음 |
| 이야기 독립 | 엔진 코드에 이야기의 id, 이름, 문장이 없다(일반성의 문법적 대리). 성질은 검증을 통과한 모든 이야기에 대해 성립해야 하므로 이야기마다 퍼징한다 | `server/src/` 전체 | 뼈대 이야기의 id와 이름을 `src/`에서 찾는 경계 테스트 |
| 원고 적합 | `S₀ ⊨ C`, 플레이어는 장소 하나에, 매개변수가 `Σ`·`U` 위에 정의되고 효과는 4절의 연산뿐 | `initial`, story.md V1~V2 | 시작 시 검증 |
| 도달성 | 구성 `(S, h)`가 유한하고 다음 구성이 `(S, h, a, r)`로 정해지므로 "목표에 닿을 수 있는가"는 유한 그래프의 도달성이다. 주사위는 세 결과를 모두 펼친다 | story.md V5~V6 | 시작 시 검증 |

## 8. 정한 것

| 질문 | 결정 | 이유 |
|---|---|---|
| 명제의 뜻 | 문장은 필수, `⟦p⟧`는 선택 | 뜻 없는 명제는 원고 상수로 충분 |
| 사실에 시간 구간, 조건에 변수 | 두지 않음 | 이력 요약과 유한한 `U`로 충분하고 원고가 단순함 |
| NPC의 자율 행동 | 반응과 원고 효과만 | 목표 추구 NPC는 계획기가 필요함 |
| 무리, 장소보다 작은 단위 | 두지 않음 | `here`가 장소 하나여야 `V`가 단순함 |
| 원고 플래그 | 최소한만 | 이력 요약과 `fill`이 대부분을 대신함 |
