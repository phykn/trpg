# TRPG v1 Runtime Plan

이 문서는 v1 구현 계약이다. LLM은 게임 결과를 정하지 않는다. server가 graph와 engine으로 결과를 확정하고, LLM은 확정 결과를 플레이어가 읽을 narration으로 바꾼다.

외부 API와 client 응답 shape는 되도록 유지한다. 단, 레거시는 내부에 남기지 않는다. legacy intent는 입력 해석 경계에서만 alias로 받고, canonical action으로 변환한 뒤에는 legacy action, legacy dispatch, legacy seed, 과도기 호환 branch를 남기지 않는다.

## 1. 원칙

- server flow는 `classify -> normalize -> resolve -> pending/execute -> narrate`다.
- LLM 호출은 늘리지 않는다. `classify` 한 번에서 intent, target, `goal`, `manner`, `check_required`, `check_reason`을 받는다.
- LLM은 graph, stat, DC, 성공/실패, 보상, 피해량을 정하지 않는다.
- `graph`는 게임 사실의 원천이고, `state`는 pending, combat, locale 같은 진행 상태다.
- roll 실패 시 저장된 action은 실행하지 않는다.
- query, 장비 착용/해제, 단순 재방문 이동은 LLM narration 없이 server message로 끝낸다.
- 시간 시스템은 쓰지 않는다. 규칙과 narration 모두 낮/밤, 몇 시간 뒤, 오래 걸림 같은 시간 경과 표현을 만들지 않는다.
- v1 runtime은 새 장소, NPC, 몬스터, 아이템, 목표 계약을 자동 생성하지 않는다. seed나 이미 graph에 있는 대상만 공개한다.

성공 기준은 action과 roll 정책 분리, affinity 기반 DC 변화, roll 후 LLM narration, 최근 원본 대화 기반 NPC/전투 narration, streaming 문장과 저장 로그 일치다.

## 2. 입력 파이프라인

한 턴은 아래 순서로 처리한다.

```text
state/graph 읽기 -> pending block -> 후보 목록 -> classify
  -> normalize/builder -> resolver -> confirmation 또는 roll 저장
  -> execute -> result 저장/event -> narrate -> final 저장/event
```

pending이 있으면 새 자연어 입력을 해석하지 않는다. 먼저 현재 pending을 확인, 취소, roll 제출 중 하나로 해결한다.

classify 입력은 현재 상황, 플레이어 발화, graph에서 만든 후보 목록, `recent_anchors`뿐이다. 최근 원본 대화 5턴, 관련 요약 15턴, 최근 narration 원문은 `graph_narrate`와 `combat_narrate` 입력이다.

후보 목록은 현재 장소, 보이는 NPC/적/아이템, 공개 `connects_to`, 인벤토리, 기술, 직전 대상/대화상대/언급 대상인 `recent_anchors`다. LLM이 후보를 만들거나 없는 id를 지어내도 server는 믿지 않는다.

classify 출력은 `intent`, 후보 id들, `manner`, `goal`, `with`, `check_required`, `check_reason`이다. `how`는 classify 출력이 아니다. builder가 intent, manner, 대상, graph 상태를 보고 internal `how`를 만든다.

canonical action은 8개다.

| action | 뜻 |
|---|---|
| `move` | 장소 이동 |
| `transfer` | 아이템, 장비, 돈, 목표 계약 상태 이전 |
| `use` | 아이템, 장치, 비공격 기술 사용 |
| `attack` | 공격 또는 전투 시작 |
| `speak` | NPC와 말하기 |
| `perceive` | 보기, 찾기, 기억하기, 추적하기 |
| `rest` | 쉬기 |
| `query` | 현재 공개 정보 질문 |

`pass`는 gameplay action이 아니다. 분류 실패, 무행동, 게임 밖 요청 거절을 안전하게 끝내는 no-op으로만 쓴다.

alias normalize:

| legacy/public intent | canonical |
|---|---|
| `talk` | `speak` |
| `inspect` | `perceive` |
| `buy`, `sell`, `pickup`, `give`, `steal`, `loot`, `equip`, `unequip`, `accept_quest`, `abandon_quest` | `transfer` + internal `how` |
| 공격형 `cast` | `attack` + `with` |
| 비공격형 `cast` | `use` + `with` |

internal `how`는 `free`, `trade`, `steal`, `equip`, `unequip`, `accept`, `abandon`만 쓴다. `buy`, `sell`, `pickup`, `give`, `loot`은 public intent나 UI label이다.

roll 정책은 action 안에 넣지 않는다. 내부 wrapper는 `ActionEnvelope { action, check.required, check.reason }`이고, pending payload에는 실행할 canonical action만 저장한다.

resolver 순서는 `pending block -> query -> confirmation -> check roll -> execute/server message/narrate`다. 확인과 roll이 모두 필요하면 confirmation을 먼저 띄우고, confirm 후 저장된 canonical action을 다시 resolver에 넣는다.

## 3. Roll, DC, roll narration

check 가능 action과 stat은 `move/agility`, `steal/agility`, 사회적 `transfer/presence`, `use/mind`, `speak/presence`, `perceive/mind`다. `attack`, `rest`, `query`, `pass`는 check 대상이 아니다. 전투는 combat exchange roll을 쓴다.

LLM은 roll 필요성과 이유만 제안한다. server는 아래 규칙으로 보정한다.

- roll 금지: `query`, `attack`, `rest`, `pass`, player `equip/unequip`, 공개 아이템 줍기, 공개 정보 확인.
- roll 필수: `steal`, 잠긴/위험/은신/추격 이동, 위험 장치/아이템 사용, 동료 합류 요청, 숨겨진 대상 공개 시도.
- 그 외: LLM의 `check_required`를 따른다.

graph check DC는 server가 tier를 고르고 범위 안에서 랜덤으로 뽑는다. `easy=2-7`, `normal=8-13`, `hard=14-19`이며 기본값은 `normal`이다. classify는 숫자 DC나 tier를 만들지 않는다.

NPC check는 affinity로 보정한다.

```text
affinity = relation:{npc}:{player}.affinity 또는 0
affinity_band = trunc_toward_zero(affinity / 10)
effective_dc = random_base_dc_from_tier - affinity_band
```

base DC 13, affinity 20이면 DC 11이다. affinity -10이면 DC 14다.

roll 결과:

- 실패하면 저장된 action을 실행하지 않는다.
- NPC 관련 실패는 affinity를 `RULES.social.affinity_failure`만큼 낮춘다.
- critical failure는 `RULES.social.affinity_critical`을 쓴다.
- 우호, 협조, 합류 요청 성공만 affinity를 올린다.
- `hostile`, `deceptive`, `steal` 성공은 affinity를 올리지 않는다.
- v1 실패 비용은 목표 실패와 관계 하락이다. 전투 시작, HP 손실, 아이템 손상 같은 큰 실패 효과는 넣지 않는다.

roll stream:

- client의 `rollGraphPending`은 `/session/{id}/graph/roll/stream`을 기본으로 쓴다.
- `/session/{id}/graph/roll`은 기존 client 호환용 final 응답으로 남기고 narration delta는 보내지 않는다.
- event 순서는 `result -> narration_delta* -> final`이다.
- `result`는 roll 결과 저장, pending 해제, 성공 action 또는 실패 effect 적용 뒤 보낸다.
- `final`은 narration 저장까지 끝난 뒤 보낸다.

roll 성공 후 `move`, `transfer`, `use`는 저장된 action을 실행하고 실행 결과를 narration payload에 넣는다. `speak`, `perceive`는 성공 outcome과 대상 context를 넣고, server가 미리 아는 reveal/access effect만 graph에 적용한다.

허용 reveal/access effect는 seed나 기존 graph에 있는 대상만 공개한다: 숨겨진 아이템/NPC의 `hidden_at` 공개, 숨겨진 `connects_to` 해제, NPC 설득으로 기존 통로/목표 계약 제안/정보 flag 공개. 새 content는 만들지 않는다.

roll 실패 후에는 action 미실행, affinity/XP 같은 server effect, 실패 outcome, `check_reason`, 최근 히스토리를 narration payload에 넣는다. LLM narration은 실패를 성공처럼 바꿀 수 없다.

## 4. Graph와 world model

node type은 `character`, `item`, `location`, `quest`, `skill`, `race`, `chapter`다. `quest`는 내부 graph type이고 플레이어에게는 목표 계약으로 보인다.

edge type은 `located_at`, `hidden_at`, `connects_to`, `carries`, `equips`, `reward_of`, `has_companion`, `knows_skill`, `belongs_to_race`, `grants_skill`, `gives_quest`, `target_of`, `required_by`, `part_of_chapter`, `relation`이다. 위치, 소유, 장착, 종족, 기술, 동료, 목표 계약 목표와 보상은 property가 아니라 edge가 원본이다.

GraphChange는 `add_node`, `set_node_property`, `add_edge`, `set_edge_property`, `remove_edge`만 허용한다. LLM은 GraphChange를 직접 만들지 않는다.

검사 규칙:

- edge 양끝 node가 존재해야 한다.
- 아이템은 위치, 소유, 장착, 보상 edge 중 하나만 가진다.
- `equips`는 player에게만 허용한다. NPC, 몬스터, 동료 후보는 `carries`만 쓴다.
- 캐릭터는 동시에 하나의 현재 위치만 가진다.
- `connects_to`가 없으면 이동할 수 없다.
- 목표 계약은 제공자, 목표, 보상, 완료 조건을 graph에서 찾을 수 있어야 한다.
- 플레이어 확인 없이 목표 계약이 `active`가 되면 안 된다.
- LLM draft는 검사 통과 전까지 graph가 아니다.
- node는 기본적으로 삭제하지 않는다. 사라진 대상은 status를 바꾸거나 보이는 edge를 제거한다.

LLM과 client에는 전체 graph를 주지 않는다. server가 `surroundings`, `target_view`, `story_graph`만 만든다. 숨겨진 아이템/통로, 미공개 목표 계약 정보, 내부 관계 수치, 보상 예산은 공개 view에 넣지 않는다.

아이템:

- 아이템은 node이고, 위치/소유/장착/보상 예약은 edge다.
- player는 장비 3개와 소지품을 가진다.
- 기타 character는 소지품만 가진다.
- 장비 슬롯은 `weapon`, `armor`, `accessory`다.
- 장착 중인 player 아이템을 팔거나 넘기려면 먼저 `unequip`해야 한다.
- 아이템 사용은 `transfer`가 아니라 `use`다.
- 가격, 슬롯, 피해량, 회복량, 규칙 효과는 engine이 정한다.

transfer:

| public intent | internal `how` | roll |
|---|---|---|
| `pickup`, `loot`, `give` | `free` | 없음 |
| `buy`, `sell` | `trade` | 없음 |
| `steal` | `steal` | confirmation 후 check |
| `equip`, `unequip` | `equip`, `unequip` | 없음 |

루팅은 쓰러진 대상이나 시체의 `carries`에서만 가능하다. 살아 있는 NPC에게서 몰래 가져오면 `steal`이다. 장비 착용/해제는 roll, confirmation, LLM narration 없이 graph를 바꾸고 짧은 server message만 만든다. 대상 아이템이 모호하면 임의로 고르지 않는다.

장소:

- 이동은 `connects_to`로만 가능하다.
- 첫 방문이나 의미 있는 상태 변화가 붙은 이동만 `graph_narrate`로 보낸다.
- 이미 방문한 장소로 돌아가는 단순 이동은 server message로 끝낸다.

seed:

- 기존 seed는 마이그레이션하지 않는다. 새 graph 계약에 맞게 삭제 후 다시 만든다.
- 시작 전 id 중복, 깨진 참조, 시작 위치, 아이템 단일 위치/소유, player 외 `equips`, 목표 계약 목표/보상/trigger를 검사한다.
- 목표 계약 보상과 XP는 seed가 정한다. runtime은 LLM에게 보상 수치를 만들게 하지 않는다.
- 보상 한도는 seed validation 설정으로 검사한다.
- ContentDraft는 v1에서 사용하지 않는다.

## 5. Gameplay

stat은 `body`, `agility`, `mind`, `presence`다. `body`는 힘/버티기/근접, `agility`는 피하기/숨기/빠른 움직임, `mind`는 살피기/지식/집중/마법 제어, `presence`는 설득/위협/의지/분위기 장악이다. HP와 MP는 stat이 아니라 자원이며, LLM에는 보통 숫자보다 `healthy`, `hurt`, `critical`, `ready`, `strained`, `drained` 같은 상태 말을 준다. 별도 `downed` 상태는 두지 않는다.

전투:

- 시작 시 플레이어 하트 3, 적 하트 3을 둔다.
- 플레이어 입력 하나가 한 번의 교환이다.
- 플레이어만 d20을 굴린다.
- 적 하트가 0이면 승리한다.
- 플레이어 하트가 0이면 패배하고 남은 적 하트만큼 실제 HP를 잃는다.
- NPC와 몬스터는 장기 HP/MP를 갖지 않고, 전투 안의 하트와 defeat status로만 처리한다.
- LLM은 피해량, 사망, 승패를 정하지 않는다.

전투 밖 `attack`은 confirmation 뒤 `CombatState`를 만들고 전투 대기 상태로 들어간다. 전투 대기 상태에서는 추천 chip 또는 자유 자연어 입력을 받는다. 추천 chip은 기본 3개이며, 자연어 한국어 문장과 내부 `CombatIntent` metadata를 함께 가진다. 자유 입력도 LLM이 같은 `CombatIntent`로 분류한다.

`CombatIntent`는 `raw_text`, `target_id`, `tactic`, optional `support_id`를 가진다. 한 교환은 `CombatIntent 정규화 -> 대상/보조 검사 -> DC와 효과 계산 -> d20 -> 하트/상태 적용 -> 승패/도주 확인 -> result -> combat_narrate -> chip 갱신 -> final`이다.

적의 강함은 level 하나로만 표현한다.

```text
combat_dc = dc_by_enemy_level + tactic_modifier - support_bonus
level 1..6+ base DC = 10, 11, 12, 13, 14, 15
```

| tactic | DC | 성공 | 실패 |
|---|---:|---|---|
| `precise` | 0 | 적 하트 -1 | 플레이어 하트 -1 |
| `guarded` | -2 | 적 하트 -1 | 하트 손실 없음 |
| `reckless` | +2 | 적 하트 -2 | 플레이어 하트 -1 |
| `create_distance` | 0 | `escape_ready=true` 또는 escape 성공 | 플레이어 하트 -1 |
| `talk` | 0 | `enemy_pressure += 1` 또는 중단 조건 진전 | 플레이어 하트 -1 |

v1 `CombatState`는 `escape_ready: bool`과 `enemy_pressure: int`를 둔다. `escape_ready=true`에서 도망/빠져나가기/거리 벌리기 입력이 성공하면 `escaped`로 끝낸다. `talk` 성공으로 `enemy_pressure >= 2`가 되거나 적 하트가 1 이하일 때 다시 `talk`가 성공하면 server가 seed/상황에 맞게 `surrendered`, `escaped`, `combat_stopped` 중 하나로 끝낼 수 있다. LLM은 없던 항복이나 도주를 만들지 않는다.

전투 기술과 아이템은 한 교환에 하나만 붙는 보조다. `character_defeat`는 `dead`, `unconscious`, `surrendered`, `escaped`, `combat_stopped`를 구분한다.

성장:

- XP는 `xp_pool`에 쌓이고, 레벨업은 현재 level만큼 XP를 소비해 level을 1 올린다.
- 최대 level은 10이고, stat 성장에는 별도 최대치가 없다.
- 의미 있는 roll 성공 +1, critical success +2, 실패 0, 전투 승리 XP는 적 level 기준, 목표 계약과 milestone은 seed/engine 보상이다.
- 의미 있는 roll은 graph나 state에 진행이 남는 성공이다. 공개 정보 확인, 상태 질문, 같은 목적 반복 roll은 XP를 주지 않는다.

`xp_award_key`는 public state에 노출하지 않는다. key 형식은 `roll:{action}:{target_id}:{goal_key}`, `combat:victory:{combat_id}`, `quest:complete:{quest_id}`, `milestone:{milestone_id}`다.

레벨업 선택지는 stat +1, 최대 HP +1, 최대 MP +1, 새 기술 습득, 기존 기술 tier 3까지 강화다. 기술은 별도 `cast` action이 아니며 `attack/use/perceive/speak`에 `with`로 붙는다. LLM은 기술 후보의 이름과 설명만 만들 수 있고, 수치와 비용은 engine template이 정한다.

휴식은 회복, 비용, 장소 위험도, 조우만 처리한다. 위험하면 confirmation을 띄우고, 전투 중에는 휴식할 수 없다. 휴식 결과를 시간 경과로 설명하지 않는다.

목표 계약:

- 내부 graph type은 `quest`, UI/narration 용어는 목표 계약이다.
- 발견했다고 바로 시작하지 않는다.
- 상태는 `locked -> pending -> active -> completed/failed/abandoned`다.
- 수락과 포기는 confirmation을 거친다.
- v1에서는 동시에 active 목표 계약을 하나만 둔다.
- 완료 조건은 `location_enter`, `character_defeat`, `item_obtained`, `item_use`, `social_check`처럼 engine이 확인할 수 있는 trigger여야 한다.
- v1 목표 계약은 seed나 이미 graph에 있는 NPC/장소 offer에서만 나온다.

## 6. LLM, 히스토리, API

LLM 호출은 `classify`, `graph_intro`, `graph_narrate`, `combat_narrate`, `summon`, `recommend`다. 모두 graph를 바꾸지 않는다. route env는 `LLM_ROUTE_CLASSIFY`, `LLM_ROUTE_GRAPH_INTRO`, `LLM_ROUTE_GRAPH_NARRATE`, `LLM_ROUTE_COMBAT_NARRATE`, `LLM_ROUTE_SUMMON`, `LLM_ROUTE_RECOMMEND`이며 없으면 `LLM_ROUTE_DEFAULT`를 쓴다.

JSON 출력 호출은 schema 검사 실패 시 repair/retry를 먼저 한다. 플레이 중 `/graph/input`, `/graph/turn`, `/graph/roll/stream`은 retry를 모두 실패해도 HTTP 에러가 아니라 인게임 fallback 응답으로 끝낸다. 자유문 narration 실패도 server fallback 문장을 쓴다.

`graph_narrate`는 확정 action/outcome, 관련 graph 조각, roll 결과와 `check_reason`, affinity 변화, 최근 원본 대화, 관련 요약 히스토리, 최근 narration 원문을 받는다. `combat_narrate`는 확정 전투 결과, `CombatIntent.raw_text`, tactic, 보조 기술/아이템, 공개 하트 상태, HP/MP 상태 말, 최근 원본 대화, 관련 요약, 최근 전투 narration, 공개 초점을 받는다.

LLM narration은 JSON을 붙이거나, graph를 바꾸거나, engine이 처리하지 않은 이동/획득/전투 결과를 말하거나, 성공/실패를 다시 정하면 안 된다.

히스토리 기본량은 최근 원본 대화 5턴, 관련 요약 히스토리 15턴이다. `dialogue_entries.target_id`는 v1부터 optional로 저장한다. 대상이 분명한 대화, NPC 관련 roll narration, 전투 직전/전투 중 발화는 가능한 한 채운다. 대상이 없거나 애매하면 `null`이다. narration context는 같은 `target_id`의 최근 원본 대화를 먼저 넣고, 부족하면 전체 최근 원본 대화로 보충한다.

client는 graph를 직접 해석하지 않는다. `PublicState`는 `hero`, `quest`, `questOffers`, `place`, `combat`, `log`, `pendingConfirmation`, `pendingRoll`을 가진다. 숨겨진 아이템/통로, 미공개 목표 계약, 내부 관계 수치, 보상 예산, raw action, pending action 원본, 저장용 변경 목록은 client로 보내지 않는다.

pending payload는 `id`, `kind`, `title`, `body`, `target_label`을 가진다. roll payload에는 `stat`, `stat_label`, `required_roll`을 추가한다.

stream event는 `result`, `narration_delta`, `final`이다. `result`까지 도달하면 게임 사실은 확정이다. 이후 narration 생성이나 저장이 실패해도 graph, pending, combat, affinity, XP, item 이동은 되돌리지 않는다. narration 실패 시 server는 짧은 fallback message로 `final`을 보낸다.

HTTP endpoint는 도메인별로 늘리지 않는다. 유지할 그룹은 `init/state`, `intro(/stream)`, `input(/stream)`, `turn(/stream)`, `combat(/stream)`, `roll(/stream)`, `confirm(/stream)`, `level_up/options`, `level_up`이다.

저장 table은 `game_progress`, `graph_nodes`, `graph_edges`, `log_entries`, `history_entries`, `dialogue_entries`다. 게임 사실 transaction은 `GraphChange`, pending 해제, combat 상태, affinity, XP, item 이동을 함께 적용한다. `result`와 일반 HTTP final 응답은 이 transaction commit 뒤에만 보낸다. narration 생성과 기록 저장은 그 뒤에 처리한다. 이미 소비된 pending id가 다시 들어와도 저장된 action을 재실행하지 않는다.

에러:

| 상황 | 처리 |
|---|---|
| 요청 모양 오류 | HTTP 422 |
| 게임 id 없음 | HTTP 404 |
| pending 불일치 | HTTP 409 또는 422 |
| 인증/권한 실패 | HTTP 401 또는 403 |
| 저장 실패, server 내부 예외 | HTTP 500 계열 |
| 대상 모호, 없는 대상/아이템/장소, engine 거부 | HTTP 200, graph 변경 없음, pending 없음, 인게임 server narration |
| 플레이 중 LLM JSON retry 실패 | HTTP 200, graph 변경 없음, pending 없음, 인게임 fallback narration |
| 자유문 narration 실패 | HTTP 200, 확정 결과 유지, server fallback narration |

인게임 server narration은 상태창에 가까운 짧은 문장으로, 다음 입력을 고칠 수 있게 말한다. 예: `당신은 주변을 살피지만, 그 이름에 맞는 대상을 찾지 못합니다.`, `당신이 향하려는 길은 지금 이어져 있지 않습니다.`, `무엇을 집으려는지 조금 더 분명히 말해야 합니다.`

## 7. 코드 책임과 테스트

책임 경계는 `domain/rules`, `engine`, `llm agents`, `context`, `action builder`, `resolver`, `graph`, `flow`, `persistence`, `wire/mapping`, `api`, `client`로 나눈다. engine은 LLM, HTTP, client, storage를 몰라야 한다.

테스트는 LLM 문장 품질보다 계약 파손을 막는다.

| 영역 | 확인 |
|---|---|
| classify / builder | 8개 canonical action, alias normalize, `check_required`, `check_reason`, DC/tier 미생성, `cast` compatibility |
| resolver | check 대상/비대상, confirmation 후 roll, pending block, direct action compatibility |
| DC / 관계 | tier별 base DC 랜덤, affinity 보정, 실패 후 다음 DC 상승 |
| 성공/실패 / XP | 우호 성공만 affinity 상승, 실패 하락, XP와 `xp_award_key` 중복 방지 |
| 장비/이동/transfer | 장비 server message, 단순 재방문 server message, steal만 confirmation + roll |
| roll narration | `/graph/roll/stream` 순서, `/graph/roll` 호환, 상태 변경 뒤 narration, 실패 시 action 미실행 |
| 히스토리 | `dialogue_entries.target_id` optional 저장, 대상별 최근 원본 대화 우선, 전체 fallback |
| graph / seed | 불가능한 `GraphChange`, 숨겨진 정보 노출, player 외 `equips`, 보상 한도, v1 자동 생성 차단 |
| combat | 하트 감소, 방어, 도주, talk pressure, 패배 시 실제 HP 손실, 반복 narration 방지 |
| API / 저장 | raw action 미노출, 에러 경계, reload 복원, result 뒤 narration 실패가 rollback/중복 실행을 만들지 않음 |

live LLM 테스트는 실제 호출이 되는지 확인하는 짧은 smoke test로만 둔다. 기준은 schema, resolver, engine, persistence 테스트다.
