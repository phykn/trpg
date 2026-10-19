# 규칙

규칙은 후보 `K`와 전이 `R`의 내용입니다. 여섯 면 주사위 둘, 위험, 고르는 대가, 복잡화로 판정하고(3절), 박자와 장면과 위협으로 시간을 움직이며(4절), 대화가 관계와 약속을 남기고(5절), 주인공에게 선언·흉터·성장이 있습니다(6절). 상태와 연산은 [ontology.md](ontology.md), 원고 매개변수는 [story.md](story.md)의 것입니다.

```
server/src/rules/
  acts.py        행동 id: parse, format, SCHEMAS
  candidates.py  K: candidates, space, admits
  roll.py        roll(H), risk, modifiers, outcome, odds, preview
  costs.py       대가 표, pool, settle
  schemas.py     스키마마다의 Δ₀, scene_end
  triggers.py    scan, 엔진 방아쇠, chapter_to, end
  resolve.py     R = Δ₀ → 방아쇠 → Step
  recommend.py   추천 버튼
```

`rules/`는 순수 함수만 둡니다. 시각, 난수, 파일, 모델, 표현층을 읽지 않습니다.

## 1. 행동

행동은 story.md 3.12의 id로 오가고 서버 안에서는 `Action`입니다.

```python
@dataclass(frozen=True)
class Action:
    schema: str                     # go, look, take, give, talk, try, declare, cut, choose, pay, grow
    intent: tuple[str, ...]         # intent arguments in schema order
    judge: tuple[tuple[str, str], ...]  # non-neutral judgment arguments, sorted by key
```

**정규형**: 판단 인자는 키 차례로 쓰고 기본값 `ν₀`인 것은 쓰지 않습니다. `parse(format(a)) = a`이고 `format(parse(s))`는 정규형입니다. 영수증, 기록, 패턴, 버튼이 모두 정규형만 씁니다.

| 스키마 | 하는 일 | 의도 인자 | 판단 인자 (`ν₀`) |
|---|---|---|---|
| `go` | 이어진 장소로 감 | 갈 곳 | - |
| `look` | 살펴서 명제를 앎 | 대상 | - |
| `take` | 장소의 물건을 집음 | 물건 | - |
| `give` | 지닌 물건을 건넴 | 물건, 받는 이 | - |
| `talk` | 대화(5절) | 상대, 화제 | `tone`(`polite`), `claim`(없음), `rely`(없음) |
| `try` | 즉흥 시도(3절) | 대상, 방식 | `strain`(`natural`), `rely`(없음). `try(player, ·)`는 `ν₀`만 |
| `declare` | 잠재를 선언(6절) | 잠재 | - |
| `cut` | 장면을 넘김(4절) | `pass` 또는 `rest` | - |
| `choose` | 갈림에서 하나를 고름(4절) | 갈림, 선택지 | - |
| `pay` | 고를 대가 하나를 치름(3.3) | 대가 | - |
| `grow` | 성장(6절) | `grow:<방식>`, `grow:trait:<뺄>:<얻을>`, `grow:scar:<슬롯>` | - |

**의도 인자**는 무엇을 하려는지, **판단 인자**는 행동하는 모양입니다. `ν₀`는 도움도 위험 증가도 `spent`도 만들지 않습니다. 인자가 모두 유한한 종류 위를 돌므로 행동의 집합은 유한합니다. 스키마 표 `SCHEMAS`가 스키마마다 의도 인자의 종류, 판단 인자의 키, 굴림 여부를 정하는 함수, 행동 이름 틀의 키를 둡니다.

## 2. 후보 `K`

`candidates(U, O) → list[Action]`은 관찰 `O = (E, F, B, hᵥ)`와 원고 상수만 읽습니다. 차례는 스키마 표의 차례, 그 안에서 원고의 선언 차례입니다.

**보이는 막힘**: 장애물 `o ∈ E`가 원고의 `blocks`에 `x`를 두고 `F`에서 `at(o, ·)`가 있고 `fill(o) < 칸 수`면 `x`는 보이게 막혔습니다. 보이게 막힌 `x`를 인자로 하는 `go`, `take`, `talk`, `try`는 후보가 아닙니다. 숨은 막힘은 후보를 줄이지 않습니다.

| 스키마 | 후보 |
|---|---|
| `go(q)` | `link(here, q) ∈ F`, `q ∈ E` |
| `look(x)` | `x ∈ E`, `x ≠ player` |
| `take(x)` | `x`가 물건이고 `at(x, here) ∈ F` |
| `give(x, h)` | `at(x, player) ∈ F`인 물건 `x`, `at(h, here) ∈ F`인 인물 `h` |
| `talk(h, 화제)` | `at(h, here) ∈ F`인 인물 `h`. 화제는 `h`의 화제들, `favor`(부탁이 있고, `favor:h ∉ hᵥ`이고, `owes(player, h, ·)`가 없음), `chat` |
| `try(x, 방식)` | `x = player`(판단 인자 모두 `ν₀`), 또는 `x ∈ E`인 `plain` 장애물로 `fill < 칸 수`(시계, 마감, 위협, 갈림은 대상이 아님), 또는 그 밖의 `x ∈ E`로 빈 태그 슬롯이나 `snag`이 있음 |
| `declare(ℓ)` | `believes(player, ℓ) ∉ F`이고 `ℓ.when`이 보임에서 참 |
| `cut(pass)` | 늘 |
| `cut(rest)` | `here`가 쉴 곳 |
| `choose(g, c)` | `at(g, player) ∈ F`인 갈림 `g`의 선택지 `c` |
| `grow(항목)` | `growth ≥ 1`. 방식은 3 미만인 것, 특성은 지금 가진 것 하나와 원고의 다른 후보 하나, 흉터는 그 슬롯 |

판단 인자는 위 행동에 곱해 붙습니다.

| 판단 인자 | 붙는 스키마 | 값 |
|---|---|---|
| `tone` | `talk` | `polite`, `friendly`, `plead`, `threaten`, `deceive` |
| `claim` | `talk`, `tone = deceive`일 때만 | 원고의 주장들. 주장은 거짓 명제라 정직한 태도로 말할 수 없음 |
| `strain` | `try(x ≠ player)` | `natural`, `forced` |
| `rely` | 굴리는 `talk`, `try(x ≠ player)` | 아래 표. 관련성은 묻지 않으며 허용되는 값이면 어떤 굴림에도 도움 1 |

| `rely` 값 | 조건 | 도움의 원자 | 소모 |
|---|---|---|---|
| `tag:<x>:<슬롯>` | `x`는 대상, `here`, 플레이어 중 하나이고 `mark(x, edge, ·, 슬롯) ∈ F` | 그 `mark` | 굴림 뒤 `untag` |
| `trait:<id>` | 플레이어가 가진 특성이고 `spent(player, id) ∉ F` | `stat(player, id, 1)` | 굴림 뒤 `assert(spent(player, id))`. 결과와 무관 |
| `thing:<id>` | `at(id, player) ∈ F` | 그 `at` | 없음 |
| `prop:<id>` | `id ∈ B` | `believes(player, id)` | 없음 |
| `bond:<h>` | `regards(h, player, trust, 3) ∈ F`(유대) | 그 `regards` | 없음 |

**`due`가 있으면** 후보는 `pay(c)`(`due(player, c) ∈ F`)와 `try(player, ·)`뿐입니다. **결말이 놓이면** 후보는 비고 게임이 끝납니다. `try(player, ·)`는 늘 후보이므로 결말 전에는 `K ≠ ∅`입니다(진행성).

`K`의 크기는 판단 인자의 곱 때문에 커지므로 엔진은 `K`를 통째로 펼치지 않습니다. `space(U, O)`는 스키마별로 의도 인자만 펼친 목록과 판단 인자마다 허용되는 값을 돌려주고, `admits(U, O, a)`가 `a ∈ K(O)`를 판정하며, 둘은 같은 조건 함수를 씁니다. 해석의 질문과 굴림 카드(engine.md 3~4절)가 `space`를, 실행 직전의 허용 검사가 `admits`를 씁니다.

**해법**은 후보를 더하지 않습니다. 해법은 `try(o, approach)`에 `rely`를 채운 행동 id 하나에 `label`과 조건 `when`을 붙인 것이고, `when`(과 `rely`가 암묵으로 더하는 조건)이 보임에서 참일 때 그 행동의 이름이 `label`이 됩니다. 해법이 있든 없든 같은 행동 id는 같은 `R`을 거칩니다.

## 3. 판정

### 3.1 주사위

```python
def roll(seed: int, t: int) -> tuple[int, int, int]:
    b = hashlib.sha256(f"{seed}:{t}".encode()).digest()
    n = lambda i: int.from_bytes(b[i:i + 8], "big")
    return n(0) % 6 + 1, n(8) % 6 + 1, n(16) % 60
```

`r = (d₁, d₂, u)`. `seed`는 게임을 만들 때 `secrets.randbits(63)`으로 정합니다. 나머지의 치우침은 `10⁻¹⁷` 수준이라 무시합니다. `R`은 `r`을 인자로 받으므로 증인과 테스트는 주사위를 직접 줍니다.

```
합 = d₁ + d₂ + stat(player, 방식) + 도움 − 방해        talk의 방식은 charm
결과 = success (합 ≥ 10) | mixed (7~9) | fail (≤ 6)
```

### 3.2 위험, 보정, 결과

```python
BANDS = (7, 10)                          # mixed from 7, success from 10
def risk(U, a) -> Risk                   # reads only U and a
def modifiers(U, facts, a) -> Mods       # stat, help, hinder and the atoms behind them
def outcome(r, mods) -> Result           # by BANDS
def odds(z) -> tuple[float, float, float]  # (fail, mixed, success) of 2d6 + z by BANDS
```

**위험**은 원고 매개변수와 `a`의 인자만 읽습니다. 그래서 숨은 원자만 다른 두 상태에서 같고, `rely` 선택지마다 같으며, 숨은 경비 같은 `S`의 숨은 부분은 위험에 들지 않고 행동해서 겪습니다. 판단 인자는 위험을 올릴 수만 있습니다.

```
risk(try(player, ·))            = low
risk(try(o, 방식, strain))       = min(high, 기본(o) + [방식 ∈ clashes(o)] + [strain = forced])
risk(talk(h, ·, tone))           = min(high, normal + [tone ∈ {threaten, deceive}])
risk(choose(·))                  = high          (되돌릴 수 없음)
risk(그 밖)                      = low
```

`기본(o)`는 장애물의 `risk`(`low`·`normal`), 장애물이 아닌 대상이면 `normal`입니다.

**보정**의 원자는 이 차례로 사건의 `mods`가 됩니다.

| 보정 | 값 | 원자 |
|---|---|---|
| `stat` | `stat(player, 방식)`의 값 | 그 `stat` 원자 |
| 도움 | `rely`가 있으면 1, 아니면 0 | 2절 표의 원자 하나 |
| 방해 | 아래 원자가 하나라도 있으면 1, 아니면 0 | 대상, `here`, 플레이어에 걸린 `snag` `mark` 전부. `talk`에서 상대가 플레이어를 보는 관련 축(`threaten`이면 `fear`, 아니면 `trust`)이 음수인 `regards` |

도움과 방해는 원자 수와 무관하게 각각 0 또는 1이므로 한 굴림의 `도움 − 방해`는 −1, 0, +1입니다(이득 한정). 방해의 원자가 여럿이어도 화면에는 방해 하나(값 −1, 이름을 이어 씀)로 보입니다(api.md 3절).

`modifiers`는 `facts`에 넘긴 원자만 읽습니다. `R`은 `S`를, 미리보기는 `F`를 넘깁니다. 보정이 읽는 원자는 모두 `E` 안의 개체(대상, `here`, 플레이어, 눈앞의 상대)에 대한 `mark`, `stat`, `regards`이거나 `rely`가 가리키는 `F`와 `B`의 원자라서, 굴리는 행동 `a ∈ K(O)`에 대해 `modifiers(U, S, a) = modifiers(U, F, a)`입니다.

`outcome`, `odds`, api.md의 `view.bands`는 모두 `BANDS` 하나에서 나옵니다.

### 3.3 대가와 복잡화

**복잡화**는 `(조건, 효과, 무게)`입니다. 원고가 장소, 인물, 장애물에 붙여 선언하고(story.md 3.6), 엔진은 조건이 없는 것을 무게마다 둘씩 둡니다.

| 무게 | 엔진의 복잡화 | 이름(`locale/ko.py`) | 효과 |
|---|---|---|---|
| `light` | `engine.snag` | 꼬임 | 플레이어에게 `snag` 장면 태그 |
| | `engine.beat` | 지체 | `beats +1` |
| `heavy` | `engine.wound` | 다침 | `wounds +1` |
| | `engine.end` | 끊긴 장면 | 장면 끝(4.1) |

원고 복잡화의 효과는 `effects`에 `wound: n`이 있으면 `wounds +n`을 더한 것입니다. 대가는 굴림 결과와 위험으로 정합니다.

| 위험 \ 결과 | `mixed` | `fail` |
|---|---|---|
| `low` | 시계 +1 | 시계 +1, 가벼움 적용 |
| `normal` | 시계 +1, 가벼움 **고름** | 시계 +1, 무거움 적용 |
| `high` | 시계 +1, 무거움 **고름** | 시계 +2, 무거움 적용 |

**후보 목록** `pool(무게, 대상)`: 엔진의 것 둘(위 표의 차례), 그 뒤에 원고의 것을 장소(`here`), 인물(`here`에 있는 인물들, 원고 차례), 장애물(굴림의 대상) 차례로. 원고 복잡화는 붙은 곳의 암묵 조건과 `when`을 거칩니다. 엔진의 것이 조건이 없어 목록은 늘 둘 이상입니다.

- **적용**(`fail`): `when`을 세계 `(S, h)`에서 평가한 목록에서 `u mod 개수`번째의 효과를 `Δ₀`에 넣습니다. 겪어서 드러나는 것이므로 숨은 것을 써도 되고, 그래서 미리보기는 무게만 말합니다.
- **고름**(`mixed`): `when`을 단계 시작의 `(F, hᵥ)`에서 평가한 목록에서 `u mod 개수`번째부터 원형으로 셋까지(목록이 짧으면 전부) `assert(due(player, c))`. 그 차례가 `view.due`의 차례입니다. `due`가 있는 동안 후보는 `pay(c)`와 `try(player, ·)`뿐이고, `pay(c)`는 `c`의 효과를 적용하고 `due`를 모두 지웁니다.

`settle(U, O, work, a, result, risk, u)`가 대가 표의 한 칸(시계, 적용 또는 고름)을 `Δ₀`에 넣습니다.

### 3.4 미리보기

```python
def preview(U, O, a) -> Preview
```

굴림이 있는 행동 `a ∈ K(O)`에 대해, 굴리기 전에 플레이어에게 보일 것을 관찰만으로 계산합니다. 굴림 카드(engine.md 4.2)가 씁니다.

| 필드 | 값 |
|---|---|
| `risk` | `risk(U, a)` |
| `mods` | `modifiers(U, O.facts, a)`를 api.md 3절의 칩 목록(`kind`, `label`, `value`)으로. 단계 기록의 `mods`와 같은 모양, 같은 차례 |
| `z` | `stat + 도움 − 방해` |
| `odds` | `odds(z)` |
| `stakes` | 그 위험의 대가 표 한 줄과, 고름이면 무게 |
| `clock` | 지닌 위험 시계의 이름, 칸 수, `fill`, 그리고 `mixed`·`fail`일 때의 증가(`min(n, 남은 칸)`) |
| `gain` | 성공했을 때 대상에 생길 일: 장애물이면 칸 `min(1 + [방식 ∈ fits], 남은 칸)`, 그 밖의 `try`면 가장 낮은 슬롯의 `snag`을 뗌(그 이름) 또는 `edge` 장면 태그, `talk`면 화제의 공개 또는 부탁의 효과(이름들) |

**미리보기는 실행과 같습니다.** 위험은 원고와 `a`의 함수이고 보정은 3.2의 끝에서 `S`와 `F`에서 같으므로, 굴림이 일어나면 그때의 `z`, `mods`, 위험은 미리보기의 값과 같습니다. 다른 것은 두 가지뿐입니다. 숨은 막힘이 있으면 굴림이 일어나지 않고(`blocked`, 기댄 것도 소모하지 않음), 실패의 복잡화는 숨은 것에서도 고를 수 있어 미리보기는 무게만 말합니다.

## 4. 시간

### 4.1 박자와 장면

**박자** `stat(player, beats, n)`, `0 ≤ n ≤ B`. `try(player, ·)`, `pay`, `cut`을 뺀 모든 단계가 `Δ₀`에서 `beats +1`합니다.

**장면 끝** `scene_end`: `expire(scene)`, `beats = 0`, 활성 위협(`at(w, player)`인 위협, 갈림, 마감)마다 `fill +1`. 위험 시계는 들지 않습니다. `go`는 장면 태그를 만료하지 않습니다.

`cut(pass)`는 장면 끝을 바로 일으킵니다("밤이 될 때까지 기다린다"). `cut(rest)`는 `here`가 쉴 곳일 때만 후보이고, 장면 끝에 더해 `wounds −1`, 활성 위협 `fill +1`을 한 번 더 합니다.

### 4.2 위험 시계와 위협

장마다 위험 시계 `clock.k` 하나를 플레이어가 지닙니다. 시계의 `fill`을 올리는 것은 굴림의 대가와 선언뿐, 내리는 것은 `τ_위험`뿐, 옮기는 것은 장 전환뿐입니다.

**위협**은 도착 효과를 가진 장애물입니다. 플레이어가 지니면(`at(w, player)`) **활성**이라 보이고 장면이 끝날 때마다 다가옵니다. 등장 방아쇠의 `move(w, player)`가 등장시키고, 원고 효과가 `fill`을 내리거나 `retire`로 물릴 수 있습니다. **갈림**은 선택지와 기본 선택지를 가진 위협입니다. `choose(g, c)`는 `c`의 효과를 내고 `g`를 물리며, 고르지 않고 버티면 도착해 기본 선택지가 일어납니다. 결말의 조건은 이력 패턴으로 어떤 선택이 있었는지 읽습니다.

**마감** `deadline.k`는 장마다 하나인 위협이고, 도착 효과가 조건 없이 장 전환이나 결말을 냅니다. 첫 장의 것은 시작부터, 그 뒤의 것은 장 전환으로 활성이 됩니다.

### 4.3 장 전환과 결말

`chapter_to(k)`는 하나의 연산열입니다.

1. `set(flag, chapter, k)`, `expire(chapter)`
2. 단계를 시작할 때 있던 `owes(player, h, 약속)`마다 `keep`이 세계에서 참이면 지킴, 아니면 어김(5.2). 그 단계에 생긴 약속은 다음 장으로 넘어감
3. `clear_spent(player)`
4. `retire(clock.k−1)`, `retire(deadline.k−1)`, `move(clock.k, player)`, `move(deadline.k, player)`
5. `growth +1`, 그리고 목표로 넘어갈 때는 원고의 `goal_effects`

`end(e)`는 `set(flag, ending, e)` 뒤에 남은 플레이어의 약속을 모두 2.처럼 결말 내고, 그 단계의 방아쇠 훑기를 멈춥니다. 장 목표가 `Δ₀`에서 참이 되면 원고 방아쇠가 엔진 방아쇠보다 먼저 훑이므로, 같은 단계에 지난 시계가 찼어도 그 시계는 `τ_위험` 없이 물러납니다.

## 5. 사람

### 5.1 대화와 건넴

`regards(g, h, 축, n)`의 축은 `trust`·`fear`입니다. 대화 굴림의 **관계**는 상대가 플레이어에게 가진 값으로 `threaten`이면 `fear`, 그 밖이면 `trust`이며, 음수일 때만 방해로 들어가고 양수는 유대(`trust` 3)로 기댑니다.

`talk(h, 화제, tone, claim, rely)`의 `Δ₀`는 이 차례로 만듭니다.

1. **숨은 막힘**: `h`가 숨은 장애물에 막혔으면 드러내고 끝냅니다.
2. **굴림 여부**(보임으로 판정하며, `R` 안에서는 `fact_rule`로 `S`에서 `F`를 만들어 같은 판정을 함): 화제가 이미 믿는 명제이거나, `free_when`이 참이거나, `chat`이거나, `owes(h, player, kindness)`가 있는 부탁이면 굴리지 않습니다. 그 밖의 화제와 부탁은 굴립니다.
3. **결과**: 굴리지 않는 화제는 공개(`reveals: x`면 `x.hidden`, 아니면 화제 id), 호의로 들어주는 부탁은 부탁의 효과와 `retract(owes(h, player, kindness))`. 굴리면 `success`·`mixed`에서 공개, 또는 부탁의 효과와 `assert(owes(player, h, promise))`. 대가는 3.3입니다.
4. **태도**: `threaten`은 결과와 무관하게 `regards(h, player, fear) +1`, `trust −1`. `deceive`이고 `claim`의 `against`를 `h`가 믿으면 들통: `trust −2`, 플레이어에게 `snag` 장 태그(기본 이름 "의심"). 원고 명제에 맞지 않는 주장은 문장으로만 남습니다.
5. **부탁의 횟수**: 엔진은 인물마다 패턴 `favor:h`(행동 `talk:h:favor`, 결과 `success`·`mixed`·`none`)를 `Pat`에 더합니다. 들어준 단계가 이 패턴에 맞고, 후보는 `favor:h ∈ hᵥ`이면 부탁을 내지 않습니다. 후보는 `F`와 `hᵥ`만 읽으므로 원고 플래그 대신 보이는 이력을 씁니다.

`give(x, h)`는 `move(x, h)`이고, `x ∈ wants(h)`면 `regards(h, player, trust) +1`, `assert(owes(h, player, kindness))`.

### 5.2 약속

`owes(g, h, k)`: `g`가 `h`에게 `k`를 빚졌습니다. `k`는 `promise`(`h`의 부탁에 걸린 약속으로, `keep`·`break` 조건은 `h`의 `favor.promise`에서 읽음) 또는 `kindness`(호의)입니다. 인물마다 부탁이 하나라 `owes(player, h, promise)`로 약속이 정해집니다. 플레이어의 약속은 부탁으로만 생깁니다.

- **지킴**: `retract(owes)`, `regards(h, player, trust) +1`.
- **어김**: `retract(owes)`, `trust −2`, 플레이어에게 `snag` 장 태그(기본 이름 "약속을 어김"). 장 전환 안의 어김 태그는 `expire(chapter)` 뒤에 붙으므로 다음 장으로 넘어갑니다.

`τ_약속`(6절)이 조건이 참해진 약속을 결말 내고, 남은 것은 생긴 단계 뒤의 첫 장 전환이나 결말이 결말 냅니다. 그래서 약속은 늦어도 다음 장 전환에서 결말이 납니다.

## 6. 주인공

- **선언** `declare(ℓ)`: `reveal(player, ℓ)`, `ℓ.effects`, 지닌 시계 `+1`. 플레이어가 "옛 친구가 이 마을에 산다"고 말하면 세계에 사실이 더해지는 것처럼 보이지만, 원고가 처음부터 둔 잠재가 드러날 뿐입니다(story.md 3.10의 범위 규칙).
- **흉터** `τ_쓰러짐`: `wounds = 0`, `tag(player, snag, scar)`, 장면 끝. `tag`는 비울 슬롯에서 `scar`를 건너뛰고 그런 슬롯밖에 없으면 붙이지 않습니다. 같은 방아쇠의 효과 끝에서 플레이어의 슬롯이 모두 `scar`면 `end(collapse)`. `collapse`의 이름과 서술 틀은 원고가 둡니다.
- **성장** `grow(항목)`: `growth ≥ 1`일 때만 후보이고 `growth −1`. 항목은 방식 하나 `+1`, 특성 교체(`stat` 원자를 빼고 더함), 흉터 하나 `untag` 중 하나입니다. 성장은 장 전환이 엽니다.

## 7. 스키마의 결과 `Δ₀`

`schemas.py`는 스키마마다 `Δ₀`를 작업 사본 위의 연산열로 냅니다. 굴림이 있는 단계는 결과를 정한 뒤 효과를 냅니다.

| 스키마 | `Δ₀` |
|---|---|
| (공통) | `try(player, ·)`, `pay`, `cut`을 뺀 모든 단계가 `beats +1` |
| `go(q)` | 숨은 장애물이 `q`를 막으면 `reveal(player, o.hidden)`(`blocked`). 아니면 `move(player, q)` |
| `look(x)` | `x ∈ about(p)`인 원고 명제 `p`를 원고 차례로 `reveal` |
| `take(x)` | 숨은 막힘이면 드러냄. 아니면 `move(x, player)` |
| `give(x, h)` | 5.1 |
| `talk(h, 화제)` | 5.1 |
| `try(player, ·)` | 아무것도 없음. 방아쇠도 훑지 않음 |
| `try(o, 방식)` | 숨은 막힘이면 드러냄(굴림 없음). 아니면 굴림. `success`·`mixed`면 장애물은 `fill +(1 + [방식 ∈ fits(o)])`, 그 밖은 가장 낮은 슬롯의 `snag`을 `untag`하고 없으면 `tag(o, edge, scene)`. 대가는 3.3 |
| `declare(ℓ)` | 6절 |
| `cut(pass)` | 장면 끝 |
| `cut(rest)` | 장면 끝, `wounds −1`, 활성 위협 `fill +1` |
| `choose(g, c)` | `c.effects`, `retire(g)` |
| `pay(c)` | `c`의 효과, `due(player, ·)`를 모두 `retract` |
| `grow(항목)` | 6절 |

굴린 뒤의 **기대기 소모**는 2절 표대로입니다. 굴림이 있는 단계는 늘 `beats`를 올리고 `mixed`·`fail`은 시계를 바꾸므로, "아무 일도 없었습니다"로 끝나는 굴림은 없습니다.

## 8. 방아쇠와 `R`

방아쇠는 차례가 있는 `(조건, 효과)`입니다. 원고 방아쇠(ontology.md 5.3의 차례)는 **가장자리 발동**이고 한 단계에 많아야 한 번 발동하며, `repeat`가 아니면 발동 플래그로 한 게임에 한 번입니다. 그 뒤에 엔진 방아쇠 다섯이 이 차례로 오며 **수준 발동**입니다.

| 방아쇠 | 조건 | 효과 |
|---|---|---|
| `τ_위험` | 지닌 시계가 다 참 | 그 장의 `crisis`, 시계 `fill = 0` |
| `τ_쓰러짐` | `wounds = wound_boxes` | 흉터(6절) |
| `τ_장면` | `beats = B` | 장면 끝 |
| `τ_도착` | 다 찬 활성 위협이 있음 | 원고 차례로 그런 것마다 도착 효과(위협은 `arrival`, 갈림은 `default`, 마감은 `chapter_to`나 `end`), `retire` |
| `τ_약속` | `keep`이나 `break`가 참인 `owes(player, ·, 약속)`가 있음 | 5.2의 결말. 둘 다 참이면 지킴 |

```python
def resolve(U, S, h, a, r) -> Step:
    # Step(delta, mods, rolled, result, risk); never mutates S
```

1. `work = Work(S)`. 원고 방아쇠마다 `start_true[i] = holds(τᵢ.when, S, h)`.
2. 스키마의 `Δ₀`를 `work`에 적용합니다(7절). 굴림의 결과 `result`가 정해집니다.
3. `h* = h ∪ { π | matches(π, a, result) }`. 한 단계 안에서 `a`와 `result`는 바뀌지 않으므로 한 번만 계산합니다.
4. **훑기** `scan`: 목록을 차례로 보며 처음 발동하는 것 하나의 효과를 `work`에 적용하고 목록의 처음으로 돌아갑니다. 발동할 것이 없으면 멈추고, `flag ending`이 놓이면 바로 멈춥니다. 원고 방아쇠 `τᵢ`는 이번 단계에 발동하지 않았고 `start_true[i]`가 거짓이고 `holds(τᵢ.when, work, h*)`가 참일 때, 엔진 방아쇠는 조건이 `work`에서 참일 때 발동합니다.
5. `delta = diff(S, work)`. `mods`는 3.2의 원자들입니다.

훑기는 많아야 `m + 3 + w + q`번(원고 방아쇠 수, 엔진 셋, 위협·갈림·마감 수, 부탁 수) 뒤에 끝나고 결정적입니다. `Δ₀` 뒤의 효과는 시계·박자·상처를 올리지 않고, 도착은 위협을 물리고, 약속 결말은 `owes`를 지우기 때문입니다. 코드는 그 값을 넘으면 예외를 내며, 이는 퍼징(story.md V6)이 잡아야 할 버그입니다. 끝에서 엔진 방아쇠의 조건은 모두 거짓이므로 모든 단계는 시계가 다 차지 않은 채 시작합니다.

`Step.result`는 `success`, `mixed`, `fail`(굴림), `none`(굴림 없이 이룸), `blocked`(숨은 막힘이 드러남) 중 하나이고 사건에 저장합니다. `risk`는 `a`에서 다시 계산되므로 저장하지 않습니다.

## 9. 추천 버튼

`recommend(U, O) → list[Action]`, 많아야 셋.

1. `due`가 있으면 `pay` 행동들(`view.due`의 차례).
2. 아니면 차례로 하나씩 고릅니다.
   - **태그**: 플레이어나 `here`의 `edge` 태그에 기대는 `try`가 있으면 그것. 대상은 활성 장애물 중 원고 차례로 처음 것, 방식은 해법이 있으면 해법의 방식, 없으면 플레이어의 가장 높은 방식
   - **대화**: 눈앞 인물의 아직 믿지 않는 화제 중 원고 차례로 처음 것
   - **나아감**: 활성 갈림이 있으면 그 첫 선택지의 `choose`. 아니면 보임에서 `when`이 참인 해법 중 처음 것, 없으면 장 목표의 조건에 나오는 장소로 가는 `go`

버튼의 판단 인자는 버튼을 정의하는 `rely`(해법의 `rely`, 태그)를 빼고 모두 `ν₀`입니다. 기댈 것은 굴림 카드에서 누구나 고르므로(engine.md 4.2) 버튼과 문장의 차이는 방식, 대상, 태도를 자유롭게 고를 수 있는지에 있습니다.

## 10. 성질과 검사

| 성질 | 내용과 이유 | 지키는 곳 | 검사 |
|---|---|---|---|
| 허용 검사 | 상태에 적용하기 전에 `a ∈ K(Vₜ)`. 버튼, 카드, API 포함 | 서비스가 단계마다 `admits` 뒤에 `resolve`(engine.md 7절) | 후보 밖 id, 낡은 카드의 id → 거절 |
| 진행성 | `try(player, ·)`는 `due`가 있어도 후보 | `candidates` | 퍼징의 모든 단계(결말 전)에서 `space`가 비지 않음 |
| 중립값 | `ν₀`는 도움, 위험 증가, `spent`를 만들지 않고 `try(player)`의 `Δ = ∅` | 1절, 7절 | 판단 인자를 모두 `ν₀`로 둔 행동의 결과 |
| 이득 한정 | 도움·방해는 `F`나 `B`의 원자에 기대고 각각 0 또는 1. `try`의 성공이 바꾸는 것은 `fill`과 `mark`뿐이고 물건·명제·길은 원고 효과와 `take`·`give`·`look`·`talk`로만 움직임 | `modifiers`, 7절 | 태그를 여럿 건 대상 → 방해 1 |
| 위험의 독립 | `risk`는 `(U, a)`만 읽음 | `risk`의 서명 | 숨은 원자만 다른 두 상태 → 같은 위험 |
| 미리보기 = 실행 | 3.4 | `preview`, `modifiers` | 퍼징에서 굴린 단계마다 `preview`의 `z`, `mods`, `risk` = `Step`의 값, `result = outcome(total)`; `odds(z)`가 `BANDS`로 센 2d6 분포와 같음(경계 6·7·9·10 단위 테스트) |
| 인자의 종류 | `take`, `give`, `rely=thing:`의 인자는 물건. 시계는 인자가 아님 | `candidates` | 시계를 건네거나 기대는 id → 거절 |
| 방아쇠의 끝 | 8절의 상한 | `scan` | 퍼징에서 예외 없음 |
| 굴림의 전진 | 굴린 단계는 보이는 것을 바꾸고 `mixed`·`fail`은 시계를 바꿈(7절) | `schemas.py` | 퍼징에서 굴린 단계마다 플레이어의 보이는 원자가 바뀜 |
| 시간의 전진 | `try(player)`·`pay`를 뺀 단계 `B`번 안에 장면이 끝나고, 칸 수 `n`인 활성 위협은 `fill`을 내리는 효과가 없는 한 그런 단계 `n·B`번 안에 도착하거나 물러남 | 4절 | 퍼징 |
| 결말의 보장 | 어느 구성에서든 `pay`와 `cut(pass)`만으로 많아야 `1 + Σₖ nₖ`(남은 장들의 마감 칸 수) 단계 안에 결말에 닿음. 주사위를 쓰지 않음 | story.md의 구조(장마다 마감, 마지막 장은 결말) | 시작 시 검증은 구조만 봄 |
| 원고 성질 | 시계와 방아쇠의 문법, 잠재의 격리, 증인 | story.md 4절 | 시작 시 검증 |
