# 규칙 구현

[rule.md](../theory/rule.md)의 후보 `K`와 규칙 `R`을 코드로 옮기는 방법을 정합니다. 상태, 연산, 관찰은 [ontology.md](ontology.md)의 것을 쓰고, 원고 매개변수는 [story.md](story.md)의 형식에서 옵니다. 지금의 코드와 무관하게 이론에서 끌어냈고, 이론이 열어 둔 자리를 정한 것은 9절에 모았습니다.

```
server/src/rules/
  acts.py        행동 id: 파싱, 정규형, 스키마 표
  candidates.py  K(O)
  roll.py        H, 위험, 보정, 결과, 미리보기
  costs.py       대가 표, 복잡화 후보와 고르기
  schemas.py     스키마마다의 Δ₀
  triggers.py    방아쇠 훑기, 엔진 방아쇠, 장 전환, 결말
  resolve.py     R = Δ₀ → 방아쇠 → (Δ, mods)
  recommend.py   추천 버튼 β
```

`rules/`는 순수 함수만 둡니다. 시각, 난수, 파일, 모델, 표현층을 읽지 않습니다(온톨로지 P2).

## 1. 행동 id

행동은 story.md 3.12의 id로 오가고, 서버 안에서는 `Action`입니다.

```python
@dataclass(frozen=True)
class Action:
    schema: str                     # go, look, take, give, talk, try, declare, cut, choose, pay, grow
    intent: tuple[str, ...]         # intent arguments in schema order
    judge: tuple[tuple[str, str], ...]  # non-neutral judgment arguments, sorted by key
```

- **정규형**: 판단 인자는 키 차례로 쓰고, 중립값 `ν₀`인 것은 쓰지 않습니다. `parse(format(a)) = a`이고 `format(parse(s))`는 정규형입니다. 영수증, 기록, 패턴, 버튼이 모두 정규형만 씁니다.
- **판단 인자의 키**: `tone`(정중 `polite`가 `ν₀`), `claim`(없음이 `ν₀`), `rely`(없음이 `ν₀`), `strain`(`natural`이 `ν₀`).
- **성장의 항목**: `grow:<방식>`, `grow:trait:<뺄 특성>:<얻을 특성>`, `grow:scar:<슬롯>`.

스키마 표 `SCHEMAS`가 스키마마다 의도 인자의 종류, 판단 인자의 키, 굴림 여부를 정하는 함수, 행동 이름 틀의 키를 둡니다. 행동 이름 `λ`는 이 키로 [engine.md](engine.md)의 틀 표에서 찾습니다.

## 2. 후보 `K`

`candidates(U, O) → list[Action]`은 관찰 `O = (E, F, B, hᵥ)`와 원고 상수만 읽습니다(온톨로지 2.3). 차례는 스키마 표의 차례, 그 안에서 원고의 선언 차례입니다.

**보이는 막힘**: 장애물 `o`가 `E`에 있고, 원고의 `blocks`에 `x`가 있고, `F`에서 `at(o, ·)`가 있고 `fill(o) < 칸 수`면 `x`는 보이게 막혔습니다. 보이게 막힌 `x`를 인자로 하는 `go`, `take`, `talk`, `try`는 후보가 아닙니다(story.md 3.6). 숨은 막힘은 후보를 줄이지 않습니다.

| 스키마 | 후보 |
|---|---|
| `go(q)` | `link(here, q) ∈ F`, `q ∈ E` |
| `look(x)` | `x ∈ E`, `x ≠ player` |
| `take(x)` | `x`가 물건이고 `at(x, here) ∈ F` |
| `give(x, h)` | `at(x, player) ∈ F`, `x`가 물건, `h`가 인물이고 `at(h, here) ∈ F` |
| `talk(h, 화제)` | `at(h, here) ∈ F`인 인물 `h`. 화제는 `h`의 화제들, `favor`(부탁이 있고, 들어준 적이 없고, `owes(player, h, ·)`가 없음), `chat` |
| `try(x, 방식)` | `x = player`(판단 인자는 모두 `ν₀`), 또는 `x ∈ E`인 `plain` 장애물로 `fill < 칸 수`(시계, 마감, 위협, 갈림은 `try`의 대상이 아님), 또는 그 밖의 `x ∈ E`로 빈 태그 슬롯이나 `snag`이 있음 |
| `declare(ℓ)` | `believes(player, ℓ) ∉ F`이고 `ℓ.when`이 보임에서 참 |
| `cut(pass)` | 늘 |
| `cut(rest)` | `here`가 쉴 곳 |
| `choose(g, c)` | `at(g, player) ∈ F`인 갈림 `g`의 선택지 `c` |
| `grow(항목)` | `growth ≥ 1`. 방식은 3 미만, 특성은 지금 가진 것과 원고의 다른 후보, 흉터는 그 슬롯 |

판단 인자는 위 각 행동에 곱해 붙습니다.

| 판단 인자 | 붙는 스키마 | 값 |
|---|---|---|
| `tone` | `talk` | 다섯 태도 |
| `claim` | `talk`, `tone = deceive`일 때만 | 원고의 주장들 |
| `strain` | `try(x ≠ player)` | `natural`, `forced` |
| `rely` | 굴릴 수 있는 `talk`, `try(x ≠ player)` | `F`의 `edge` 태그(대상, 장소, 플레이어의 것, 슬롯으로 가리킴), `spent`가 없는 특성, 지닌 물건, `B`의 명제, 신뢰 3인 인물(유대) |

`rely`의 값은 `tag:<개체>:<슬롯>`, `trait:<id>`, `thing:<id>`, `prop:<id>`, `bond:<id>`로 씁니다.

**`due`가 있으면** 후보는 `pay(c)`(`due(player, c) ∈ F`)와 `try(player, ·)`뿐입니다(rule 3.4). **결말이 놓이면** 후보는 비고 게임이 끝납니다.

`K`의 크기는 판단 인자의 곱 때문에 커질 수 있습니다. 그래서 엔진은 `K`를 통째로 펼쳐 쓰지 않고, 스키마별로 의도 인자만 펼친 목록과 판단 인자마다 허용되는 값을 따로 돌려주는 `space(U, O)`를 씁니다. `a ∈ K(O)`의 판정은 `admits(U, O, a)` 하나로 하고, 두 함수는 같은 조건 함수를 씁니다. 해석의 질문(engine.md 3절)과 굴림 카드(engine.md 4절)가 `space`를 쓰고, 실행 직전의 허용 검사(온톨로지 P5)가 `admits`를 씁니다.

**해법**은 후보를 더하지 않습니다. 해법은 `try(o, approach)`에 `rely`를 채운 행동 id 하나에 `label`과 조건 `when`을 붙인 것이고, `when`(그리고 `rely`가 암묵으로 더하는 조건)이 보임에서 참일 때 그 행동의 이름이 `label`이 됩니다. 해법이 있든 없든 같은 행동 id는 같은 `R`을 거칩니다.

## 3. 판정

### 3.1 주사위 `H`

```python
def roll(seed: int, t: int) -> tuple[int, int, int]:
    b = hashlib.sha256(f"{seed}:{t}".encode()).digest()
    n = lambda i: int.from_bytes(b[i:i + 8], "big")
    return n(0) % 6 + 1, n(8) % 6 + 1, n(16) % 60
```

`seed`는 게임을 만들 때 `secrets.randbits(63)`으로 정합니다. `2⁶⁴`을 6이나 60으로 나눈 나머지의 치우침은 `10⁻¹⁷` 수준이라 무시합니다. `R`은 `r`을 인자로 받으므로 증인과 테스트는 주사위를 직접 줍니다.

### 3.2 위험, 보정, 결과

```python
def risk(U, a) -> Risk                  # rule 3.2; reads only U and a (J3)
def modifiers(U, facts, a) -> Mods      # stat, help, hinder and the atoms behind them
def outcome(r, mods) -> Result          # success >= 10, mixed 7..9, fail <= 6
```

- **위험**: rule 3.2의 식 그대로입니다. `try(player, ·)`는 낮음, `try(o, …)`는 `기본(o) + [방식 ∈ clashes(o)] + [strain = forced]`을 높음에서 멈춤, `talk`는 보통 `+ [tone ∈ {threaten, deceive}]`, `choose`는 높음, 그 밖은 낮음. 원고와 `a`만 읽습니다.
- **보정**: `stat(player, 방식)`(talk는 `charm`)의 원자, `rely`가 있으면 그것을 가리키는 원자 하나(도움 1), 그리고 방해의 원자들. 방해는 대상, `here`, 플레이어에 걸린 `snag` 원자 전부와, `talk`에서 상대가 플레이어를 보는 관련 축(`threaten`이면 `fear`, 아니면 `trust`)이 음수인 `regards` 원자입니다. 방해의 원자가 몇 개든 방해는 1입니다(J2). 원자들이 사건의 `mods`가 되고, 차례는 `stat`, 도움, 방해입니다. 방해의 원자가 여럿이어도 화면에는 방해 하나(값 −1, 이름을 이어 씀)로 보입니다(engine.md 8.3).
- **결과**: `합 = d₁ + d₂ + stat + 도움 − 방해`.

보정은 `facts`에 넘긴 원자만 읽습니다. `R`은 `S`를 넘기고 미리보기(3.4)는 `F`를 넘깁니다. 보정이 읽는 원자는 모두 `E` 안의 개체(대상, `here`, 플레이어, 눈앞의 상대)에 대한 `mark`, `stat`, `regards`이거나 `rely`가 가리키는 `F`와 `B`의 원자라서, 굴리는 행동 `a ∈ K(O)`에 대해 `modifiers(U, S, a) = modifiers(U, F, a)`입니다.

### 3.3 대가와 복잡화

`costs.py`는 rule 3.4의 표를 그대로 둡니다.

| 위험 \ 결과 | `mixed` | `fail` |
|---|---|---|
| `low` | 시계 +1 | 시계 +1, 가벼움 적용 |
| `normal` | 시계 +1, 가벼움 고름 | 시계 +1, 무거움 적용 |
| `high` | 시계 +1, 무거움 고름 | 시계 +2, 무거움 적용 |

**후보 목록** `pool(무게, 대상)`: 엔진의 것 둘(가벼움은 `engine.snag`, `engine.beat`, 무거움은 `engine.wound`, `engine.end`), 그 뒤에 원고의 것을 장소(`here`), 인물(`here`에 있는 인물들, 원고 차례), 장애물(굴림의 대상) 차례로. 원고의 복잡화는 붙은 곳의 암묵 조건과 `when`을 거칩니다(story.md 7절 6).

- **적용**(실패): `when`을 세계 `(S, h)`에서 평가한 목록에서 `u mod 개수`번째의 효과를 `Δ₀`에 넣습니다.
- **고름**(대가 있는 성공): `when`을 단계 시작의 `(F, hᵥ)`에서 평가한 목록에서 `u mod 개수`번째부터 원형으로 셋까지(목록이 짧으면 전부) `assert(due(player, c))`.

엔진의 복잡화는 조건이 없어 목록은 늘 둘 이상입니다. 효과는 `engine.snag`이 플레이어에게 `snag` 장면 태그, `engine.beat`이 `beats +1`, `engine.wound`가 `wounds +1`, `engine.end`가 장면 끝(4.1)이고, 원고 복잡화는 `effects`에 `wound`가 있으면 `wounds +n`을 더한 것입니다.

### 3.4 미리보기

```python
def preview(U, O, a) -> Preview
```

굴림이 있는 행동 `a ∈ K(O)`에 대해, 굴리기 전에 플레이어에게 보일 것을 관찰만으로 계산합니다. 굴림 카드(engine.md 4절)와 화면(ui.md)이 씁니다.

| 필드 | 값 | 근거 |
|---|---|---|
| `risk` | `risk(U, a)` | rule 정리 5 |
| `stat`, `help`, `hinder` | `modifiers(U, O.facts, a)`와 그 원자들 | 3.2 |
| `z` | `stat + help − hinder` | |
| `odds` | `z`에서 2d6로 계산한 `(fail, mixed, success)` | fun.md 4.1 |
| `stakes` | 그 위험의 대가 표 한 줄과, 고름이면 무게 | 3.3 |
| `clock` | 지닌 위험 시계의 이름, 칸 수, `fill` | |
| `gain` | 성공했을 때 대상에 생길 일: 장애물이면 칸 `1 + [어울림]`, 그 밖이면 태그 | rule 3.3 |

**미리보기는 실행과 같습니다.** 위험은 원고와 `a`의 함수이고(J3), 보정은 3.2의 끝에서 보인 대로 `S`와 `F`에서 같습니다. 그래서 굴림이 일어나면 그때의 `z`와 위험은 미리보기의 값과 같습니다. 다른 것은 두 가지뿐입니다. 숨은 막힘이 있으면 굴림이 일어나지 않고(rule 정리 5의 "행동해서 겪음"), 실패의 복잡화는 숨은 것에서도 고를 수 있어 미리보기는 무게만 말합니다.

## 4. 스키마의 결과 `Δ₀`

`schemas.py`는 스키마마다 `Δ₀`를 작업 사본 위의 연산열로 냅니다(ontology.md 3.2). 굴림이 있는 단계는 결과를 정한 뒤 효과를 냅니다.

| 스키마 | `Δ₀` |
|---|---|
| (공통) | `try(player, ·)`, `pay`, `cut`을 뺀 모든 단계가 `beats +1` |
| `go(q)` | 숨은 장애물이 `q`를 막으면 `reveal(player, o.hidden)`. 아니면 `move(player, q)` |
| `look(x)` | `x ∈ about(p)`인 원고 명제 `p`를 원고 차례로 `reveal`(`x.clue` 등) |
| `take(x)` | 숨은 막힘이면 드러냄. 아니면 `move(x, player)` |
| `give(x, h)` | `move(x, h)`. `x ∈ wants(h)`면 `regards(h, player, trust) +1`, `assert(owes(h, player, kindness))` |
| `talk(h, 화제)` | 5.2 |
| `try(player, ·)` | 아무것도 없음. 방아쇠도 훑지 않음(rule 3.3) |
| `try(o, 방식)` | 숨은 막힘이면 드러냄(굴림 없음). 아니면 굴림. 성공·대가 있는 성공이면 장애물은 `fill +(1 + [방식 ∈ fits(o)])`, 그 밖은 가장 낮은 슬롯의 `snag`을 `untag`하고 없으면 `tag(o, edge, scene)`. 대가는 3.3 |
| `declare(ℓ)` | `reveal(player, ℓ)`, `ℓ.effects`, 지닌 시계 `+1` |
| `cut(pass)` | 장면 끝 |
| `cut(rest)` | 장면 끝, `wounds −1`, 활성 위협 `fill +1` |
| `choose(g, c)` | `c.effects`, `retire(g)` |
| `pay(c)` | `c`의 효과, `due(player, ·)`를 모두 `retract` |
| `grow(항목)` | `growth −1`, 그리고 방식 `+1`, 특성 교체(`stat` 원자를 빼고 더함), 또는 그 슬롯의 흉터를 `untag` |

**기대기**: `rely`가 태그면 굴림 뒤에 그 슬롯을 `untag`, 특성이면 `assert(spent(player, 특성))`. 물건, 명제, 유대는 소모하지 않습니다(rule 3.1).

**장면 끝**(`scene_end`): `expire(scene)`, `beats = 0`, 활성 위협(`at(w, player)`인 위협, 갈림, 마감)마다 `fill +1`.

## 5. 대화, 장, 결말

### 5.1 대화

`talk(h, 화제, tone, claim, rely)`의 `Δ₀`는 이 차례로 만듭니다.

1. **숨은 막힘**: `h`가 숨은 장애물에 막혔으면 드러내고 끝냅니다.
2. **굴림 여부**: 화제가 이미 믿는 명제이거나, `free_when`이 세계에서 참이거나, `chat`이거나, `owes(h, player, kindness)`가 있는 부탁이면 굴리지 않습니다. 그 밖의 화제와 부탁은 굴립니다.
3. **결과**: 굴리지 않는 화제는 공개(`reveals: x`면 `x.hidden`, 아니면 화제 id), 호의로 들어주는 부탁은 부탁의 효과와 `retract(owes(h, player, kindness))`. 굴리면 성공·대가 있는 성공에서 공개, 또는 부탁의 효과와 `assert(owes(player, h, 약속 id))`. 대가는 3.3입니다.
4. **태도**: `threaten`은 결과와 무관하게 `regards(h, player, fear) +1`, `trust −1`. `deceive`이고 `claim`의 `against`를 `h`가 믿으면 들통: `trust −2`, 플레이어에게 `snag` 장 태그(기본 이름 "의심").
5. **부탁의 횟수**: 엔진은 인물마다 패턴 `favor:h`(행동 `talk:h:favor`, 결과가 `success`, `mixed`, `none` 중 하나)를 `Pat`에 더합니다. 부탁을 들어준 단계가 이 패턴에 맞고, 후보는 `favor:h ∈ hᵥ`이면 부탁을 내지 않습니다(story.md 7절 7). 후보가 `F`와 `hᵥ`만 읽으므로(온톨로지 2.3) 저장하지 않는 원고 플래그 대신 보이는 이력을 씁니다.

### 5.2 장 전환과 결말

`chapter_to(k)`는 rule 4.5의 차례를 하나의 연산열로 묶은 매크로입니다.

1. `set(flag, chapter, k)`, `expire(chapter)`
2. 단계를 시작할 때 있던 `owes(player, h, 약속)`마다 `keep`이 세계에서 참이면 지킴, 아니면 어김(5.3)
3. `clear_spent(player)`
4. `retire(clock.k−1)`, `retire(deadline.k−1)`, `move(clock.k, player)`, `move(deadline.k, player)`
5. `growth +1`, 그리고 원고의 `goal_effects`(목표로 넘어갈 때)

`end(e)`는 `set(flag, ending, e)` 뒤에 남은 플레이어의 약속을 모두 2.처럼 결말 내고, 그 단계의 방아쇠 훑기를 멈춥니다(story.md 7절 4).

**약속의 결말**: 지킴은 `retract(owes)`, `regards(h, player, trust) +1`. 어김은 `retract(owes)`, `trust −2`, 플레이어에게 `snag` 장 태그(기본 이름 "약속을 어김")입니다. 장 전환 안의 어김 태그는 `expire(chapter)` 뒤에 붙으므로 다음 장으로 넘어갑니다.

## 6. 방아쇠와 `R`

```python
def resolve(U, S, h, a, r) -> Step:
    # Step(delta, mods, rolled, result, risk); never mutates S
```

1. `work = Work(S)`. `start_true[i] = holds(τᵢ.when, S, h)`를 원고 방아쇠마다 계산합니다.
2. 스키마의 `Δ₀`를 `work`에 적용합니다(4절). 굴림의 결과 `result`가 정해집니다.
3. `h* = h ∪ { π | matches(π, a, result) }`. 한 단계 안에서 `a`와 `result`는 바뀌지 않으므로 `h*`는 한 번만 계산합니다.
4. 훑기: 아래 목록을 차례로 보며 처음 발동하는 것 하나의 효과를 `work`에 적용하고 목록의 처음으로 돌아갑니다. 발동할 것이 없으면 멈춥니다. `flag ending`이 놓이면 바로 멈춥니다.
   - 원고 방아쇠 `τᵢ`(ontology.md 4.3의 차례): 이번 단계에 발동하지 않았고, `start_true[i]`가 거짓이고, `holds(τᵢ.when, work, h*)`가 참
   - `τ_위험`: 지닌 시계가 다 참 → 그 장의 `crisis`, 시계 `fill = 0`
   - `τ_쓰러짐`: `wounds = wound_boxes` → `wounds = 0`, `tag(player, snag, scar)`, 장면 끝. 그 뒤 플레이어의 슬롯이 모두 `scar`면 `end(collapse)`
   - `τ_장면`: `beats = B` → 장면 끝
   - `τ_도착`: 다 찬 활성 위협이 있음 → 원고 차례로 그런 것마다 도착 효과(위협은 `arrival`, 갈림은 `default`, 마감은 `chapter_to`나 `end`), `retire`
   - `τ_약속`: `keep`이나 `break`가 참인 `owes(player, ·, 약속)`가 있음 → 5.2의 결말. 둘 다 참이면 지킴
5. `delta = diff(S, work)`. `mods`는 3.2의 원자들입니다.

훑기의 상한은 rule 정리 2의 `m + 3 + w + q`입니다. 코드는 그 값을 넘으면 예외를 냅니다. 이 예외는 정리가 깨졌다는 뜻이므로 시작 시 검증의 퍼징(story.md V6)이 잡아야 할 버그입니다.

`Step.result`는 `success`, `mixed`, `fail`(굴림), `none`(굴림 없이 행동이 이루어짐), `blocked`(숨은 막힘이 드러남) 중 하나이고 사건에 저장합니다(ontology.md 5.1). `risk`는 `a`에서 다시 계산되므로 저장하지 않습니다.

## 7. 추천 버튼 `β`

`recommend(U, O) → list[Action]`, 많아야 셋. engine 2.5를 따릅니다.

1. `due`가 있으면 `pay` 행동들입니다.
2. 아니면 차례로 하나씩 고릅니다.
   - **태그**: 플레이어나 `here`의 `edge` 태그에 기대는 `try`가 있으면 그것. 대상은 활성 장애물 중 원고 차례로 처음 것, 방식은 해법이 있으면 해법의 방식, 없으면 플레이어의 가장 높은 방식
   - **대화**: 눈앞 인물의 아직 믿지 않는 화제 중 원고 차례로 처음 것
   - **나아감**: 활성 갈림이 있으면 그 첫 선택지의 `choose`. 아니면 보임에서 `when`이 참인 해법 중 처음 것, 없으면 장 목표의 조건에 나오는 장소로 가는 `go`

버튼의 판단 인자는 버튼을 정의하는 `rely`(해법의 `rely`, 태그)를 빼고 모두 `ν₀`입니다. 굴림 카드가 기댈 것을 고르게 하므로(engine.md 4절) 버튼과 문장의 차이는 판단 인자가 아니라 방식과 대상, 태도를 자유롭게 고를 수 있는지에 있습니다.

## 8. 의무와 검사

온톨로지 P5, P10, P11과 규칙 J1~J7을 지키는 곳입니다.

| 의무 | 지키는 곳 | 테스트 |
|---|---|---|
| P5 허용 검사 | 서비스가 단계마다 `admits` 뒤에 `resolve`(engine.md 7절) | 후보 밖 id, 낡은 카드의 id |
| P10 진행성 | `try(player, ·)`는 `due`가 있어도 후보 | 모든 퍼징 단계에서 `space`가 비지 않음(결말 전) |
| P11, J7 | story.md V5의 증인 재생 | 뼈대 이야기의 증인 넷 |
| J1 중립값 | 판단 인자를 모두 `ν₀`로 둔 행동에 도움과 위험 증가가 없음, `try(player)`의 `Δ = ∅` | 성질 테스트 |
| J2 이득 한정 | `modifiers`의 도움과 방해가 0 또는 1 | 태그를 여럿 건 대상 |
| J3 위험의 인자 | `risk`의 서명이 `(U, a)` | 숨은 원자만 다른 두 상태 |
| J4 시계와 방아쇠 | story.md의 구조와 V3 | 시작 시 검증 |
| J5 인자의 종류 | `take`, `give`, `rely=thing:`의 인자가 물건 | 시계를 건네거나 기대는 id |
| J6 잠재의 격리 | story.md 3.10의 범위 규칙 | 시작 시 검증 |
| 미리보기 = 실행 | 3.4 | 무작위 행동열에서 굴린 단계마다 미리보기의 `z`, `risk`와 사건의 값이 같음 |

규칙 정리 2의 상한은 6절의 예외로, 정리 6(굴림의 전진)은 퍼징에서 굴린 단계마다 플레이어의 보이는 원자가 바뀌었는지로 확인합니다.

## 9. 여기서 정한 것

| | 자리 | 정한 것 | 이유 |
|---|---|---|---|
| 1 | `H` | SHA-256(`seed:t`)의 세 조각 | 결정적이고, 언어와 플랫폼에 무관함 |
| 2 | 판단 인자의 정규형 | 키 차례, `ν₀`는 생략 | 같은 행동이 같은 id. 영수증과 패턴이 문자열 비교로 끝남 |
| 3 | `claim` | `tone = deceive`일 때만 | 원고의 주장은 거짓 명제(story.md 2.5)라 정직한 태도로 말할 수 없음 |
| 4 | `rely`의 관련성 | 묻지 않음. 허용되는 값이면 어떤 굴림에도 +1 | rule 2절이 관련성을 두지 않음. 태그와 특성은 쓰면 사라져 공짜가 아님 |
| 5 | 후보의 표현 | `space`와 `admits`로 나눔 | 판단 인자의 곱을 펼치지 않음 |
| 6 | 부탁의 횟수 | 엔진 패턴 `favor:h`로 판정 | 후보는 `F`와 `hᵥ`만 읽어야 함(온톨로지 2.3) |
| 7 | 버튼과 문장의 차이 | 기댈 것은 굴림 카드에서 누구나 고름 | engine.md 4절. engine 2.5의 "문장이 조금 유리함"은 방식, 대상, 태도로 남음 |
