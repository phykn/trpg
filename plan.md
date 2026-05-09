# Plan — verb-first north star

이 문서는 앞으로 기능을 어디부터 어디까지 밀지 정하는 북극성이다. 핵심은 **verb를 먼저 고정하고**, 그 verb가 요구하는 슬롯과 엔진 책임을 뒤따라 붙이는 것이다. LLM은 플레이어 문장을 게임 의도로 해석하고 난이도를 판단하지만, 상태 변경·규칙·시간·저장은 엔진이 단일한 방식으로 처리한다.

## 원칙

- **verb가 먼저다.** 플레이어 입력은 먼저 `move` / `transfer` / `attack` 같은 게임 행위로 분류한다. `what` / `from` / `to` / `with` / `how`는 verb를 보조하는 슬롯이다.
- **한 verb는 한 종류의 상태 변화를 대표한다.** 장비 장착, 구매, 선물, 절도는 모두 소유권 이동이므로 `transfer`에 모으고 `how`로 갈라진다.
- **LLM은 의미를 만들고, 엔진은 결과를 확정한다.** classify/narrate는 의도와 묘사를 만들 수 있지만 HP, 인벤토리, 퀘스트, 시간은 engine `apply`가 바꾼다.
- **슬롯이 맞지 않으면 거부한다.** 잘못 채워진 Action은 후처리로 교정 가능한 것만 고치고, 나머지는 reject한다.
- **사용자에게 보이는 문장은 한국어 존댓말이다.** 내부 구조 이름과 테스트 코드는 영어를 유지하되, 게임 prose와 act line은 한국어로 나간다.

## 진행 순서

1. **Verb taxonomy를 잠근다.** player verb와 narrate verb를 분리하고, 각 verb가 어떤 게임 사건을 뜻하는지 한 줄로 정의한다.
2. **Verb별 슬롯 계약을 잠근다.** 각 verb가 요구하는 `what` / `from` / `to` / `with` / `how`와 roll 여부를 표로 고정한다.
3. **Classify를 verb-first로 맞춘다.** prompt, schema, 후처리가 모두 같은 verb 계약을 보게 한다.
4. **Dispatch를 verb별로 단순화한다.** 각 verb는 narrate-only, one-step engine, roll, combat, rest 중 하나의 흐름으로 떨어진다.
5. **Engine `apply`를 단일 출처로 만든다.** Player Action과 Narrate Action을 같은 Result/Effect 표면으로 처리한다.
6. **Tests는 verb 계약을 보호한다.** classify 후처리, dispatch 흐름, engine permission, save round-trip을 verb별로 작게 고정한다.

## 1단계: verb taxonomy

### Player Action

| verb | what | from | to | with | how | roll |
|---|---|---|---|---|---|---|
| `move` | X | X | O | X | X | X |
| `transfer` | O | O | O | X | `gift` / `buy` / `sell` / `steal` | `steal` |
| `use` | O | X | X | O | X | X |
| `attack` | O | X | X | O | `surprise` | `attack` |
| `cast` | O | X | X | O | X | X |
| `speak` | X | X | O | X | `friendly` / `hostile` / `deceptive` / `recruit` / `part` / `accept` / `abandon` | `recruit` / `deceptive` |
| `perceive` | O | X | X | X | X | `perceive` |
| `rest` | X | X | X | O | X | X |
| `pass` | X | X | X | X | `refuse` | X |

### verb / 슬롯 의미

| verb | how | what | from | to | with | 의미 |
|---|---|---|---|---|---|---|
| `move` | — | — | — | 목적지 id | — | 위치 이동 |
| `transfer` | `gift` | 아이템 id | 출발 인벤·슬롯 | 도착 인벤·슬롯 | — | 무상 증여 |
| `transfer` | `buy` | 아이템 id | 출발 인벤·슬롯 | 도착 인벤·슬롯 | — | 구매 (금화 지불) |
| `transfer` | `sell` | 아이템 id | 출발 인벤·슬롯 | 도착 인벤·슬롯 | — | 판매 (금화 수령) |
| `transfer` | `steal` | 아이템 id | 출발 인벤·슬롯 | 도착 인벤·슬롯 | — | 절도 (DEX 판정) |
| `use` | — | 아이템 id | — | — | 대상 id | 아이템 사용 |
| `attack` | — | 적 id 목록 | — | — | 기술 id | 전투 진입 |
| `attack` | `surprise` | 적 id 목록 | — | — | 기술 id | 기습 공격 |
| `cast` | — | 기술 id | — | — | 대상 id | 기술 시전 (heal / buff) |
| `speak` | `friendly` | — | — | NPC id | — | 일반 대화·협상·정보 요청 |
| `speak` | `hostile` | — | — | NPC id | — | 위협·욕설 |
| `speak` | `deceptive` | — | — | NPC id | — | 거짓말·기만 |
| `speak` | `recruit` | — | — | NPC id | — | 동료 영입 (CHA 판정) |
| `speak` | `part` | — | — | companion id | — | 동료 해산 |
| `speak` | `accept` | — | — | NPC id | — | 퀘스트 수락 |
| `speak` | `abandon` | — | — | NPC id | — | 퀘스트 포기 |
| `perceive` | — | 관찰 대상 id | — | — | — | 주변 관찰·탐지 |
| `rest` | — | — | — | — | gold (지불 금액) | 휴식 (HP/MP 회복, 시간 경과) |
| `pass` | — | — | — | — | — | 턴 넘기기 |
| `pass` | `refuse` | — | — | — | — | 게임 외부 입력 거부 |

### Narrate Action

narrate는 prose를 streaming하면서 부수로 4종 Action만 emit한다.

| verb | 6필드 매핑 | 의미 |
|---|---|---|
| `set` | `what="<entity>:<id>"`, `how="<field>"`, `note=value` | 엔티티 필드 직접 수정 |
| `move` | `what=target`, `to=destination` | 캐릭터 위치 이동 |
| `move_item` | `what=item`, `from`, `to` | 아이템 인벤토리 간 이동 |
| `affinity` | `what=target`, `from=actor`, `how=intent`, `note=grade` | NPC가 actor를 보는 호감도 |

## 2단계: classify — 문장을 Action으로

### Input

```python
HowValue = Literal[
    "gift", "buy", "sell", "steal",                                              # transfer
    "surprise",                                                                  # attack
    "friendly", "hostile", "deceptive", "recruit", "part", "accept", "abandon",  # speak
    "refuse",                                                                    # pass
]

class Action(BaseModel):
    verb:  VerbName
    what:  Ref | None = None                                    # 무엇/누구를
    from_: Ref | None = Field(default=None, alias="from")       # 어디서
    to:    Ref | None = None                                    # 어디로
    with_: Ref | None = Field(default=None, alias="with")       # 무엇으로
    how:   HowValue | None = None                               # 어떻게
    note:  str | None = None                                    # 부언

    model_config = ConfigDict(populate_by_name=True)
```

### Output

```json
{"verb": "transfer", "what": "item_sword",
 "from": "self.inv", "to": "self.eq.weapon",
 "with": null, "how": "gift", "note": null}
```

### 후처리

classify 후처리에서 verb 교정:

- `attack` + what 없음·protected → `pass`
- `attack` + what이 사물 → `perceive`
- `attack` + with가 heal/buff → `cast`
- `cast` + with가 damage/debuff → `attack`
- `use` + with가 무기/방어구 → `transfer(gift)` (장비 장착)
- `rest` + 전투 중 → `pass`

슬롯이 맞지 않는 Action은 reject.

## 3단계: dispatch — Action을 엔진/narrate/roll로

핸들러는 셋 중 하나로 떨어진다:

- **`narrate_absorb_and_finalize`** — 엔진 emit 없음. `Action`만 narrate에 넘기고, narrate가 묘사 + (필요 시) Narrate Action(`set`/`affinity`/...)을 부수로 emit.
- **`_run_one_step_action(emit_factory)`** — `turn_count++` → 엔진 호출 → 결과에 따라 narrate가 붙거나 act 카드만 surface.
  - **receipt action**(장비 장착, 두 번째 방문 이동 등 짧은 확인성 행위): act 카드만 띄우고 narrate skip
  - **first-visit move / 극적 실패**: act는 묻고 narrate가 흡수
- **전용 핸들러**: `run_rest` / `run_recruit_verb` / `run_dismiss_verb` / `run_steal` / `_enter_combat_and_finalize` — 패턴이 안 맞아서 별도.

### Player verb별 흐름

| verb | engine emit | narrate body | combat_narrate | roll(`pending_check`) | 별도 LLM |
|---|---|---|---|---|---|
| `move` | 위치 / `visited_location_ids` | 첫 방문만 | — | — | — |
| `transfer(gift\|buy\|sell)` | 인벤·장비·매매 | receipt면 skip | — | — | — |
| `transfer(steal)` | (성공 시) 인벤 | (성공 시) | — | **있음** (DEX) | — |
| `use` | 소비·효과 | 효과 의미 있을 때 | — | — | — |
| `attack` | 전투 진입 | — | **있음** (5~10문장 시네마틱) | — | combat_narrate |
| `cast` | MP·효과 | 의미 있을 때 | — | — | — |
| `speak(friendly\|hostile\|deceptive)` | (narrate가 affinity Action) | 항상 | — | — | — |
| `speak(recruit)` | (성공 시) 동료 추가 | 항상 | — | **있음** (CHA) | — |
| `speak(part)` | 동료 해산 | 짧게 | — | — | — |
| `speak(accept\|abandon)` | quest 상태 flip | 묘사 | — | — | — |
| `perceive` | — | 항상 | — | — | — |
| `rest` | `turn_count` 점프, HP/MP/소생 회복 | 인카운터 없을 때 | 인카운터 시 | — | summon (인카운터 시) |
| `pass` | — | 항상 (how=`refuse`면 게임 외부 입력 거부, 없으면 in-world 흡수) | — | — | — |

### 추가 동작 메모

- **move** — 새 위치 이름이 alive NPC면 그 NPC를 target panel에 핀.
- **attack** — 시드 외 id면 `NO_COMBAT_TARGETS_TEXT`로 fail line + 종료. 자동 전투 sim(`combat_auto.py`)이 라운드 trace 누적 후 `combat_narrate` LLM이 시네마틱 streaming.
- **cast** — `skill.target == "self"` → `[player_id]`, `single` → `target_ids[:1]` 또는 self, 그 외 → `[]`.
- **rest** — 시드 인카운터 풀이 비면 `summon` LLM이 즉석 적 합성 → 전투 페이즈로 진입.
- **speak.affinity** — friendly/hostile/deceptive에서 narrate가 `affinity` Narrate Action을 emit → engine이 `target.relations[actor]`에 grade-mapped 델타 적용.

### 멀티 verb chain (최대 4개)

`actions.length >= 2`면 `_run_verb_chain`이 순차 emit. **마지막 verb에서만 narrate**가 본문을 streaming. 중간 verb의 act 라인은 `act_log_lines`로 narrate에 합류해 prose가 모순되지 않게 만든다. 도중에 attack이 끼면 거기서 chain 끊고 전투 페이즈로 넘어감.

## 4단계: engine — Action을 state 변경 + Result로

순수 게임 로직만. LLM 호출도, I/O도 없음.

### 단일 진입점

```python
def apply(state: State, action: Action, dirty: Dirty) -> Result:
    ok, reason = validate_engine(action, ctx_of(state))
    if not ok:
        return Result(applied=0, rejected=[(action, reason)], effects=[])

    snap = snapshot(state, action)        # quest status, affinity 사전값

    match action.verb:
        case "set":          _apply_set(state, action, dirty)
        case "move":         _apply_move(state, action, dirty)
        case "move_item":    _apply_move_item(state, action, dirty)
        case "affinity":     _apply_affinity(state, action, dirty)
        case "transfer":     _apply_transfer(state, action, dirty)
        case "use":          _apply_use(state, action, dirty)
        case "attack":       _enter_combat(state, action, dirty)
        case "cast":         _apply_cast(state, action, dirty)
        case "rest":         _apply_rest(state, action, dirty)
        case "accept" | "abandon": _apply_quest(state, action, dirty)

    if touched_relations(action):
        state.invalidate_graph()

    return Result(applied=1, rejected=[], effects=collect_effects(state, snap, dirty))
```

batch 처리는 단순 fold:

```python
def apply_changes(state, actions, dirty) -> Result:
    return reduce(merge, (apply(state, a, dirty) for a in actions), Result.empty())
```

### Result — 출력 한 모양

```python
@dataclass
class Result:
    applied:  int
    rejected: list[tuple[Action, str]]    # (action, 거부 사유)
    effects:  list[Effect]                 # 후속 사건 (Action에서 자동 도출)
```

`dirty: Dirty`는 인자로 받아 in-place mutate(out-param). `Dirty`는 변경된 entity 튜플 set + `deferred_act_cards` 큐(사용자에게 보일 후속 메시지)를 들고 다닌다.

`Effect`는 verb 적용 후 자동으로 발생한 사건들의 통합 표면 — `started_quest` / `completed_quest` / `failed_quest` / `level_up` / `kill` / `turn_jump` / `combat_start` / `affinity_delta` 등.

### verb별 적용 — Player + Narrate 통합

| verb | 호출자 | 적용 단계 | 후속 effects |
|---|---|---|---|
| `set` | narrate | permission matrix check + entity field 수정 | quest active flip 시 `_refresh_active_quest_id` |
| `move` | narrate / flow | (player만) 인접 검증 + 위치 이동 + companion 동행 + `check_quests("location_enter")` | `started_quest`, `completed_quest` |
| `move_item` | narrate | inventory 이동 + 장비 슬롯 자동 해제 (`unequip_by_item`) | — |
| `affinity` | narrate | `_affinity_delta(grade, intent)` → `target.relations[actor]` (단방향, -100..+100 클램프) | — |
| `transfer` | flow | `check_can_carry` + (gift\|trade\|steal) 분기 | gold change, equip auto |
| `use` | flow | consumable 소모 / trigger 발동 + 효과 분기 (`heal`/`damage`/`mp`/`buff`) | hp/mp delta |
| `attack` | flow | `start_combat` → 자동 sim → kill XP → loot transfer → `cascade_giver_death` | `kill`, `level_up`, `failed_quest` |
| `cast` | flow | `_validate_gate`(MP, 레벨) + `compute_cast_grade` + 효과 분기 (`attack`/`heal`/`buff`) | hp/mp delta, buff applied |
| `accept` / `abandon` | flow | quest status flip + chapter 진행 (`_maybe_unlock_dependents`, `_maybe_advance_chapters`) | `started_quest` / `failed_quest` |
| `rest` | flow | gold cost 차감 + `sleep_risk` 굴림 + (인카운터 or full_recovery) | `turn_jump`, optionally `combat_start` |

verb별 내부 모듈: `combat.py` (전투 수학·initiative·HP·kill XP), `inventory/` (carry / equipment / trade / use), `skill.py` (gate·grade·effect 분기), `growth.py` (XP·level_up), `quest.py` (상태머신·trigger 매칭·`fail wins`), `recovery.py` (휴식 절차).

### validate_engine — verb별 permission

```python
def validate_engine(a: Action, ctx: Context) -> tuple[bool, str]:
    match a.verb:
        case "set":
            if a.how in FORBIDDEN_BY_ENTITY[entity_kind(a.what)]:
                return False, "engine-owned field"
            if entity_kind(a.what) in {"chapter", "quest"} and a.how not in CHAPTER_QUEST_ALLOWED:
                return False, "chapter/quest set restricted"
        case "move" if is_player(a.what):
            if a.to not in connections_of(ctx.graph, current_loc(a.what)):
                return False, "destination not adjacent"
        case "transfer":
            if not check_can_carry(ctx, a.to, a.what):
                return False, "carry capacity"
            if a.how in {"buy", "sell"} and not _check_trade_allowed(ctx, a.from_, a.to):
                return False, "hostile merchant"
        case "cast":
            if not _validate_gate(ctx, a.what, a.with_):
                return False, "MP/level gate"
    return True, ""
```

거부된 Action은 `Result.rejected`에 누적. batch의 나머지는 계속 처리.

**permission은 단일 출처**: `game/rules/permissions.py`. narrate 프롬프트와 엔진이 같은 frozenset을 본다 — 프롬프트가 "set 못 하는 필드"를 LLM에 알려주고, 엔진이 같은 룰로 검증한다.

## Effect — Action에서 자동 도출

`apply` 안의 `collect_effects(state, snap, dirty)`가 snapshot(사전 상태)과 dirty(변경된 entity)를 비교해 후속 사건을 누적한다. 호감도 변화·turn 점프·취침 조우 LLM 호출 등은 `Action`이 정해지면 자동:

```python
def collect_effects(state, snap, dirty) -> list[Effect]:
    effects = []
    # Narrate Action: speak 의도 → affinity 가공 (engine 측에서 사전 처리)
    # Player Action: verb별 후속
    if rest_applied:                            effects.append(TimeJump.next_dawn())
    if rest_seed_pool_empty:                    effects.append(MaybeLLM.sleep_encounter())
    if attack_applied or offensive_cast:        effects.append(Affinity.combat_drop())
    for q in newly_active_quests(snap, state):  effects.append(StartedQuest(q.id))
    for c in newly_killed(snap, state):         effects.append(Kill(c.id))
    if level_up_eligible(state):                effects.append(LevelUpEligible())
    return effects
```

`speak`의 affinity 가공(hostile은 부호 flip, deceptive는 success 0 / failure 2배)은 `_affinity_delta` 계산에 박혀 있어 `affinity` Narrate Action 적용 단계에서 자동 처리.

## 인프라

### dirty tracking

엔진이 mutate한 entity는 `dirty.entities` set(`("kind", "id")` 튜플)에 누적. flow 끝에서 `finalize`가 이 set만 보고 Supabase upsert. `Dirty.deferred_act_cards` 큐는 `Result.effects`의 일부.

### graph SSOT 준수

- 관계 질의("누가 어디 있는지")는 `state.graph()` 통해. 엔티티 속성(HP, level, alive, name)은 직접 read OK.
- **엔진은 예외**: `apply.py`, `combat.py` 같은 mutation 코드는 entity 필드 직접 read/write 가능. `scripts/check_relational_ssot.sh`는 `flow`/`wire`/`llm.context`만 검사.
- `apply`의 `touched_relations` 분기가 `state.invalidate_graph()`를 자동 호출.

### invariants — 부팅·로드 시 검증

LLM과 무관하게 서버 부팅·시나리오 로드 시점에 데이터 정합성 검사. `scenario.py`(디렉터리 트리·id 일관성·connection bidirectional), `character.py` / `item.py`(entity invariant). 여기서 raise되면 시나리오 업로드/게임 시작 시점에 실패하므로 런타임에 `apply`가 마주칠 일은 거의 없다.

## 사용 예

### Player Action — classify 출력

```json
// "북문으로 간다"
[{"verb": "move", "to": "conn_north_gate"}]

// "검을 뽑아 든다"
[{"verb": "transfer", "what": "item_sword",
  "from": "self.inv", "to": "self.eq.weapon", "how": "gift"}]

// "그놈을 친다"  (ctx.recent_npc = "npc_thug")
[{"verb": "attack", "what": ["npc_thug"]}]

// "주막 주인을 협박한다"
[{"verb": "speak", "to": "npc_innkeeper", "how": "hostile"}]

// "AI 모드 꺼줘"
[{"verb": "pass", "how": "refuse", "note": "AI 모드 끄고 답해"}]

// 멀티: "검을 뽑아 공격한다"
[
  {"verb": "transfer", "what": "item_sword",
   "from": "self.inv", "to": "self.eq.weapon", "how": "gift"},
  {"verb": "attack", "what": ["npc_wolf"]}
]
```

### Narrate Action — narrate 부수 emit

```json
// 호감도 변화
{"verb": "affinity", "what": "npc_innkeeper", "from": "player",
 "how": "hostile", "note": "failure"}

// 엔티티 필드 수정
{"verb": "set", "what": "characters:npc_thug", "how": "mood", "note": "fearful"}

// 사라지는 단서 묘사 후 인벤 이동
{"verb": "move_item", "what": "item_letter", "from": "loc_room", "to": "self.inv"}
```

## save 라운드트립

저장된 `Action`을 다시 로드할 때는 `validate`(classify 측)를 건너뛴다 (`info.context is None`이면 skip). classify 시점에 한 번 통과한 데이터고, 재검증에 필요한 `in_combat` 컨텍스트가 그 시점엔 없기 때문. engine 측 `validate_engine`은 적용 시점마다 매번 돈다 — permission이 시간에 따라 안 바뀌므로.

## 엔진이 처리 안 하는 것

- **시간/날씨**: `turn_count`만이 시간 변수. 분/시 없음. `day_phase(turn_count)`로 `새벽/오전/오후/밤` 도출 (`game/domain/clock.py` — 엔진 아님).
- **스토리/묘사**: 전부 narrate(LLM) 책임. 엔진은 한국어 prose 안 만든다. 엔진 결과를 한국어 한 줄로 요약하는 act 카드는 `flow/format.py` (엔진 아니라 flow).
- **묘사 정합성**: narrate가 만든 묘사가 Narrate Action과 모순돼도 엔진은 모름. `apply`가 reject한 Action은 `Result.rejected`에 회수되지만 본문 prose는 이미 streaming 됐을 수 있다.
