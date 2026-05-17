# Release Test Checklist

릴리스 전까지 멈추지 않고 확인할 항목입니다. 체크는 실제 명령, API 응답, 브라우저 조작, transcript 확인 중 하나가 끝난 뒤에만 합니다. 새 문제가 나오면 이 문서에 항목을 추가하고, 수정 후 관련 항목을 다시 검증합니다.

## Recheck Execution Order - 2026-05-17

다시 빠지는 항목이 없도록 아래 소스를 먼저 대조하고, 그 다음 이 문서의 기능 묶음과 세부 체크박스를 기준으로 진행합니다.

- [x] `docs/plan.md` v1 runtime 계약 재확인
- [x] `docs/plan_client.md` server/client 통합 작업 범위 재확인
- [x] `server/src/api/base_routes.py`, `server/src/api/session_graph_routes.py` 실제 endpoint 목록 재확인
- [x] `server/src/api/schema.py` public request/response schema, combat command, think/client option 경계 재확인
- [x] `server/src/game/**`, `server/src/wire/**`, `server/src/db/**` graph/engine/wire/persistence 책임 경계 재확인
- [x] `client/services/**`, `client/logic/**`, `client/components/**`, `client/screens/**` 실제 client 기능 표면 재확인
- [x] `scenarios/dev_test/README.md` 수동 QA 흐름 재확인
- [x] `agency/AGENTS.md` QA runner와 transcript 검토 기준 재확인
- [x] `client/package.json` release export/deploy script 경계 재확인
- [x] 자동 테스트로 덮는 항목과 live browser/QA로만 덮는 항목을 최신 결과로 다시 체크
- [x] QA transcript를 turn number 기준으로 읽고 문제 있으면 이 문서에 새 항목 추가
- [x] 수정이 생기면 server/client/seed/story/export/diff gate를 다시 실행

## No-Omission Source Matrix - 2026-05-17

아래 항목은 이번 재점검에서 다시 빠뜨리지 않기 위한 소스 기준 목록입니다. 실제 테스트는 이 문서의 세부 항목에 체크하고, 여기에는 "어느 소스를 보고 어떤 기능군을 반드시 덮는지"를 고정합니다.

- [x] FastAPI endpoint 전체: `/health`, `/version`, `/profiles`, graph `init/state/intro/input/turn/combat/confirm/roll/level_up` plain + stream
- [x] Public schema 전체: profile/init/action/combat command/support/confirm/roll/level-up request, public state, pending, combat, suggestion payload
- [x] Canonical runtime 전체: `move`, `transfer`, `use`, `attack`, `speak`, `perceive`, `rest`, `query`, no-op/refuse `pass`
- [x] Transfer 기본기능 전체: pickup, give, loot, buy, sell, steal, equip, unequip, equipped-item guard, merchant/player gold delta
- [x] Party 기본기능 전체: starting companion, companion movement, party display, join/social roll, companion equipment guard
- [x] Combat 전체: start confirm/cancel, direct tactic buttons, support skill, free text in combat, hearts, roll result, victory/defeat/escape/surrender/stop
- [x] Skill/growth 전체: known skills, MP cost, support exposure, stat/HP/MP growth, learn, upgrade, max choices 3, no player-facing `스킬`
- [x] Quest 전체: offer, accept, abandon, active cap, triggers, completion/failure/abandon payload, seed rewards
- [x] Item/rest/resource 전체: HP/MP/buff/trigger item, target item use, full-resource guards, safe/risky rest, combat rest block
- [x] Movement/perception 전체: connected/disconnected move, revisit message, roll policy, hidden item/NPC/exit reveal, no generated world facts
- [x] Social/history 전체: visible dialogue, affinity/DC, target_id dialogue history, no repeated silence fallback
- [x] Persistence 전체: LocalFs/Supabase graph rows, progress rows, pending/combat/quest reload, `next_log_id`, client game/story storage
- [x] Client API 전체: stream-first/plain fallback, result-before-final, abort/stale guard, no client `think`, no legacy `cast`/combat commands
- [x] Client UI 전체: new game, shell states, composer, confirm, roll, level-up, combat, map, sheet, nearby, BGM, responsive/no-overlap checks
- [x] Scenario/manual QA 전체: `scenarios/dev_test/README.md`의 대화/파티/퀘스트/전투/판정/이동/휴식/거래/아이템/장비/레벨업 플로우
- [x] Agency QA 전체: all 9 personas, pending confirmation, pending roll, transcript formatting, first-error stop behavior
- [x] Release 전체: server tests, ruff, seed check, story sweep, client lint/type/test, web export, diff whitespace

## Must-Cover Feature Map

서버 코드, `docs/plan.md`, `scenarios/dev_test/README.md`, client 화면/서비스 파일을 다시 대조한 기능 묶음입니다. 아래 묶음 중 하나라도 새 결함이 나오면 세부 항목을 추가하고, 수정 후 API 또는 브라우저로 재검증합니다.

- [x] Base/API: health, version, auth, profile list, graph init/state, 404/422/409 error mapping
- [x] Stream/API: intro/input/turn/combat/confirm/roll stream order, error event, plain fallback shape
- [x] Canonical action pipeline: classify, normalize, resolve, pending/execute, narrate, legacy route/action 제거
- [x] Graph contract: node/edge invariants, hidden content filtering, internal fields not exposed, db graph/scenario folder split
- [x] Movement/perception: connected move, disconnected rejection, revisit message, risky roll, hidden item/exit reveal
- [x] Inventory/transfer/equipment: pickup, give, loot, equip, unequip, slot replacement, impossible transfer guards
- [x] Trade: buy, sell, merchant gold, player gold, insufficient gold, low affinity, equipped item rejection
- [x] Party/companion: companion display, follows movement, cannot equip, join request/social roll, party wording
- [x] Skills/support: known skills, MP cost, combat support metadata, support validation, level-up learn/upgrade, player-facing `기술`
- [x] Item/rest/resource: heal, MP restore, buff, trigger item, full-resource guards, target item use, safe/risky rest
- [x] Speak/social/history: visible NPC dialogue, social DC/affinity, history target id, repeated fallback prevention
- [x] Pending/roll/DC/XP: confirmations, roll policy, stale pending id, success/failure execution, XP once keys
- [x] Combat: start/cancel/confirm, direct commands, free text in combat, supports, hearts, victory/defeat/escape/surrender/stop
- [x] Quest/growth: accept/abandon/complete/fail, triggers, seed rewards, level-up choices max 3, skill learn/upgrade
- [x] LLM/prompt/fallback: classify/recommend/narration schemas, fallback messages, no JSON/fact invention, GM tone
- [x] Persistence/reload: LocalFs/Supabase row codecs, pending/combat/quest reload, client current game pointer
- [x] Client API runner: stream-first requests, plain fallback, abort/stale request handling, suggestion preservation
- [x] Client UI: new game, shell states, hero, composer, confirm, roll, level-up, combat, map, sheet, nearby, BGM, responsive layout
- [x] Live browser: new game through dev_test flows, long list scrolling with hidden scrollbar, responsive overlap checks
- [x] QA/transcript: socialite/all agent runs, awkward Korean/key mismatch/repeated silence review
- [x] Release gate: full server/client/seed/story/export/diff verification and checklist review

## Latest Fresh Evidence

- [x] 8004 FastAPI restarted with `RELOAD=1`; reload includes now cover `*.py`, `*.toml`, `*.md`
- [x] API smoke passed: base/public/stream
- [x] API smoke passed: movement/roll/party/query
- [x] API smoke passed: pickup/trade/equipment
- [x] API smoke passed: items/rest/quest/growth
- [x] API smoke passed: combat cancel/direct/support/missing/free-input
- [x] Browser smoke passed: new game -> intro
- [x] Browser smoke passed: nearby long list scrolls and uses hidden scrollbar
- [x] Browser smoke passed: level-up choices stay at 3 and applied log says `당신의 레벨이 올랐습니다`
- [x] Browser smoke passed: attack input creates confirmation modal
- [x] Browser smoke passed: combat starts, heart strip/buttons render, skill spends MP, d20 result renders
- [x] Browser smoke passed: combat free input via text field returns combat result and re-enables controls
- [x] Found and fixed: level-up card used character name/`주인공` instead of `당신`
- [x] Found and fixed: locale catalog TOML changes were cached during live server runs
- [x] Found and fixed: QA runner did not auto-resolve public `pendingRoll`, causing 409 after roll prompts
- [x] Found and fixed: classify `refuse` responses surfaced as HTTP 422 instead of in-game rejected responses
- [x] Found and fixed: intent builder `ValueError` such as missing `destination_id` bypassed classify retry/fallback and crashed QA
- [x] Fresh server gate after fixes: `.\.venv\Scripts\python.exe -m pytest -q` -> 546 passed
- [x] Fresh lint/seed/story gates after fixes: ruff passed, `check_seed scenarios\dev_test` OK, story sweep OK
- [x] Fresh client gate after fixes: `npm run lint`, `npx tsc --noEmit`, `npm test -- --runInBand` all passed
- [x] Fresh QA after fixes: `agency\run_qa.py --agent all --turns 25` -> all 9 agents, 25 turns each, errors=0
- [x] Fresh transcript scan after fixes: no error markers, no `undefined/null/NaN`, no code fence/JSON leakage, no player-facing `스킬`/`주인공`
- [x] Fresh release export after fixes: `npx expo export -p web --clear`, entry bundle generated and release API URL value verified
- [x] Fresh browser check after fixes: current in-app tab `http://localhost:8085/` shows local app text and no runtime/env error text

## 0. Source Coverage Audit

- [x] `docs/plan.md`의 v1 runtime 계약을 다시 대조
- [x] `docs/plan_client.md`의 통합 범위와 completion criteria 다시 대조
- [x] `server/src/api/base_routes.py`와 `server/src/api/session_graph_routes.py`의 실제 라우트 목록 확인
- [x] `server/src/api/schema.py`의 request/response shape와 combat command literal 확인
- [x] `scenarios/dev_test/README.md`의 수동 QA 흐름 전체 확인
- [x] `client/services/api.ts`의 client 호출 endpoint와 stream fallback 확인
- [x] `client/package.json`의 lint/test/deploy script 확인
- [x] client 주요 화면/컴포넌트 목록 확인
- [x] 서버 테스트 파일별 커버리지와 checklist 항목 매핑
- [x] client 테스트 파일별 커버리지와 checklist 항목 매핑
- [x] 자동 테스트로 못 잡는 항목을 live browser/API/QA로 분류

## 1. Baseline Automated Verification

- [x] `.\.venv\Scripts\python.exe -m pytest -q`
- [x] `.\.venv\Scripts\ruff.exe check server\src server\tests agency`
- [x] `.\.venv\Scripts\python.exe -m server.scripts.check_seed scenarios\dev_test`
- [x] `.\.venv\Scripts\python.exe -m agency.story.tool sweep scenarios\dev_test`
- [x] relational SSOT guard 실행 또는 Windows 대체 검증
- [x] prompt hot reload/cache 테스트 통과
- [x] client `npm run lint`
- [x] client `npx tsc --noEmit`
- [x] client `npm test -- --runInBand`
- [x] release web export와 `EXPO_PUBLIC_API_URL` 포함 검증
- [x] 수정 후 server 전체 테스트 재실행
- [x] 수정 후 client 전체 테스트 재실행
- [x] 수정 후 seed/story validation 재실행

## 2. API: Base, Auth, Session, Streams

- [x] `GET /health`
- [x] `GET /version`
- [x] `GET /profiles` 인증 성공
- [x] `GET /profiles` 인증 실패 401/403
- [x] `POST /session/graph/init` 정상 payload
- [x] `POST /session/graph/init` 잘못된 profile/race/payload 422
- [x] `GET /session/{game_id}/graph/state`
- [x] 존재하지 않는 `game_id` 404
- [x] malformed request 422
- [x] `POST /session/{game_id}/graph/intro`
- [x] `POST /session/{game_id}/graph/intro/stream`
- [x] `POST /session/{game_id}/graph/input`
- [x] `POST /session/{game_id}/graph/input/stream`
- [x] `POST /session/{game_id}/graph/turn`
- [x] `POST /session/{game_id}/graph/turn/stream`
- [x] `POST /session/{game_id}/graph/combat`
- [x] `POST /session/{game_id}/graph/combat/stream`
- [x] `POST /session/{game_id}/graph/confirm`
- [x] `POST /session/{game_id}/graph/confirm/stream`
- [x] `POST /session/{game_id}/graph/roll`
- [x] `POST /session/{game_id}/graph/roll/stream`
- [x] `GET /session/{game_id}/graph/level_up/options`
- [x] `POST /session/{game_id}/graph/level_up`
- [x] stream event order: `result -> narration_delta* -> final`
- [x] stream `final`과 저장 로그 일치
- [x] stream route error는 NDJSON `error` event로 반환
- [x] plain route fallback은 final response shape 유지
- [x] `think` payload는 서버 옵션으로만 동작하고 client toggle 없음

## 3. Server Pipeline, Canonical Actions, Legacy Removal

- [x] flow 순서: `classify -> normalize -> resolve -> pending/execute -> narrate`
- [x] pending이 있으면 새 자연어 입력을 해석하지 않음
- [x] candidate list가 현재 장소/보이는 대상/인벤토리/기술/recent anchors만 포함
- [x] canonical action 8개: `move`, `transfer`, `use`, `attack`, `speak`, `perceive`, `rest`, `query`
- [x] `pass`는 gameplay action이 아니라 no-op/refuse path로만 처리
- [x] alias `talk -> speak`
- [x] alias `inspect -> perceive`
- [x] alias `buy/sell/pickup/give/steal/loot/equip/unequip/accept_quest/abandon_quest -> transfer`
- [x] 공격형 `cast -> attack with`
- [x] 비공격형 `cast -> use with`
- [x] internal transfer `how`는 `free/trade/steal/equip/unequip/accept/abandon`만 사용
- [x] canonical action 이후 legacy dispatch/seed/compat branch 없음
- [x] removed legacy session routes는 404 유지
- [x] client는 legacy session route를 호출하지 않음
- [x] player-facing text에서 `스킬` 대신 canonical `기술` 사용
- [x] runtime은 seed/graph에 없는 장소/NPC/아이템/목표를 생성하지 않음

## 4. Graph Public State And Seed Contract

- [x] node type: character/item/location/quest/skill/race/chapter
- [x] edge type 전체 계약 검증
- [x] item은 위치/소유/장착/보상 예약 중 하나만 가짐
- [x] `equips`는 player에게만 허용
- [x] character 현재 위치는 하나만 허용
- [x] `connects_to` 없는 이동 거부
- [x] quest giver/target/reward/trigger reference 검증
- [x] hidden item/NPC/exit/quest는 PublicState에 노출되지 않음
- [x] raw action, pending action 원본, GraphChange는 client payload에 노출되지 않음
- [x] `xp_award_key`는 client payload에 노출되지 않음
- [x] rewards와 XP는 seed/engine 값만 사용
- [x] graph validation: duplicate id/reference/start location/reward cap
- [x] db graph/scenario 분리 구조와 import 경로 확인

## 5. Movement, Locations, Perception, Hidden Content

- [x] `move` connected location 성공
- [x] `move` disconnected/unknown location rejection
- [x] first visit 이동은 narration 생성
- [x] revisit 이동은 LLM narration 없이 server message
- [x] risky/hasty/flee movement는 roll policy 적용
- [x] 준비실 이동
- [x] 보급 구역 이동
- [x] 함정 통로 이동
- [x] 기록 보관실 이동
- [x] 위험 훈련장 이동
- [x] `query surroundings`
- [x] `query exits`
- [x] `perceive` public inspect
- [x] `주변을 자세히 살핍니다` 판정
- [x] `함정 통로에서 철사를 살핍니다` 판정
- [x] 숨겨진 아이템 reveal
- [x] 숨겨진 통로/access reveal
- [x] reveal은 seed/기존 graph 대상만 공개
- [x] reveal 실패 시 대상 미공개 유지

## 6. Inventory, Transfer, Trade, Equipment

- [x] `transfer free` public pickup
- [x] `transfer free` loot from defeated target
- [x] `transfer free` give
- [x] `transfer trade` buy
- [x] `transfer trade` sell
- [x] buy deducts player gold
- [x] buy increases merchant gold
- [x] buy moves merchant stock item to player inventory
- [x] sell increases player gold by sell ratio
- [x] sell moves item to merchant inventory
- [x] trade rejects insufficient gold
- [x] trade rejects low affinity merchant
- [x] trade candidates appear only for merchants with gold/stock
- [x] trade requires two different characters
- [x] trade must include player
- [x] equipped item cannot be sold/transferred before unequip
- [x] `transfer steal` asks confirmation first
- [x] `transfer steal` requires roll after confirm
- [x] steal success moves item without affinity gain
- [x] steal failure does not move item and lowers affinity
- [x] `transfer equip` server message, no roll, no LLM narration
- [x] `transfer unequip` server message, no roll, no LLM narration
- [x] weapon/armor/accessory slot 적용
- [x] 시작 장비 `훈련 단검` 표시
- [x] 인벤토리 `훈련 조끼`, `구리 반지` 표시
- [x] 바닥 아이템 `보급 표식` 표시
- [x] `보급 표식을 줍습니다`
- [x] `함정 통로에서 느슨한 철사를 줍습니다`
- [x] `기록 보관실에서 밀봉된 보고서를 줍습니다`

## 7. Companion And Party

- [x] `has_companion` edge follows player movement
- [x] 시작 시 `동행 점검자`가 동료로 표시
- [x] 시트/인물 패널에서 동료 표시
- [x] `준비실로 이동합니다` 뒤 동료가 함께 이동
- [x] companion은 equipment 없이 inventory만 보유
- [x] companion cannot equip
- [x] max companions rule
- [x] companion/social join request roll policy
- [x] 동료 합류 성공/실패 relationship 처리
- [x] 동료 관련 목표/할 일 표시
- [x] 파티/동료 관련 UI 용어 자연스러움 확인

## 8. Item Use, Rest, Resources

- [x] `use` item effect
- [x] `use` non-attack skill support
- [x] dangerous item/device use roll policy
- [x] focus charm/buff item 사용
- [x] full HP 상태에서 회복 약초 사용 guard
- [x] full MP 상태에서 마나 시약 사용 guard
- [x] HP 손실 후 회복 약초 사용 성공
- [x] MP 소비 후 마나 시약 사용 성공
- [x] target item use: `회복 약초를 부상 점검자에게 사용합니다`
- [x] quest item receive: `마을 주민에게 누락된 보급품을 받습니다`
- [x] quest item use: `누락된 보급품을 사용합니다`
- [x] `rest` safe recovery
- [x] `rest` risky/dangerous confirmation or encounter
- [x] `rest` blocked during combat
- [x] 휴식 narration은 낮/밤/시간 경과 표현을 만들지 않음
- [x] `보급 구역에서 잠을 잡니다`
- [x] `위험 훈련장에서 잠을 잡니다`

## 9. Speak, Social, Affinity, Dialogue History

- [x] `speak` visible NPC dialogue
- [x] `테스트 가이드에게 말을 겁니다`
- [x] `마을 주민에게 말을 겁니다`
- [x] `보급 담당자에게 회복 아이템을 묻습니다`
- [x] social roll success/failure
- [x] affinity positive lowers social DC
- [x] affinity negative raises social DC
- [x] social failure lowers affinity
- [x] critical failure uses critical affinity penalty
- [x] friendly/cooperative success can raise affinity
- [x] hostile/deceptive/steal success does not raise affinity
- [x] NPC response does not repeat the same silence/fallback phrase
- [x] `dialogue_entries.target_id` optional 저장
- [x] 대상이 분명한 대화는 target_id 채움
- [x] recent raw dialogue 5 turns and related history 15 turns used for narration

## 10. Pending, Confirmation, Roll, DC, XP

- [x] pending confirmation blocks new input
- [x] pending roll blocks new input
- [x] confirmation cancel clears pending and does not execute
- [x] confirmation confirm executes or starts roll
- [x] consumed pending id cannot re-execute action
- [x] confirmation mismatch returns 409 or 422
- [x] roll forbidden: `query`, `attack`, `rest`, `pass`
- [x] roll forbidden: equip/unequip, public pickup/info
- [x] roll required: `steal`
- [x] roll required: dangerous movement
- [x] roll required: dangerous use
- [x] roll required: companion/social request
- [x] roll required: hidden reveal
- [x] roll failure does not execute saved action
- [x] roll success executes saved action
- [x] DC tier random range easy 2-7
- [x] DC tier random range normal 8-13
- [x] DC tier random range hard 14-19
- [x] roll narration cannot flip success/failure
- [x] narration failure after `result` does not rollback state
- [x] meaningful roll success awards XP
- [x] critical success awards higher XP where applicable
- [x] repeated XP award key does not double-award

## 11. Combat Server Contract

- [x] outside-combat `attack` asks confirmation
- [x] outside-combat attack cancel leaves combat null
- [x] outside-combat attack confirm creates CombatState
- [x] start combat hearts player 3 enemy 3
- [x] direct `/graph/combat` command `precise`
- [x] direct `/graph/combat` command `guarded`
- [x] direct `/graph/combat` command `reckless`
- [x] direct `/graph/combat` command `create_distance`
- [x] direct `/graph/combat` command `talk`
- [x] free input combat intent maps attack/flee/talk/create-distance text to tactic
- [x] combat support skill validation
- [x] combat support item validation or explicit unsupported path
- [x] support missing/not known/not enough MP rejection
- [x] tactic `precise`: success enemy heart -1, failure player heart -1
- [x] tactic `guarded`: success enemy heart -1, failure no heart loss
- [x] tactic `reckless`: success enemy heart -2, failure player heart -1
- [x] tactic `create_distance`: success escape_ready or escaped, failure player heart -1
- [x] tactic `talk`: pressure/surrender/stop progression, failure player heart -1
- [x] enemy level affects combat DC
- [x] player-only d20 roll
- [x] victory when enemy hearts reach 0
- [x] defeat when player hearts reach 0 and HP loss applies
- [x] outcome `victory`
- [x] outcome `defeat`
- [x] outcome `escaped`
- [x] outcome `surrendered`
- [x] outcome `combat_stopped`
- [x] `character_defeat` quest trigger after victory
- [x] combat XP award once per combat id
- [x] combat narration receives raw_text/tactic/support/result
- [x] combat narration cannot invent damage/death/outcome
- [x] combat repeated narration fallback
- [x] combat failure text makes world/timing hard, not player silly

## 12. Quest And Growth

- [x] quest offer appears from seed/graph only
- [x] quest offer remains pending until confirm
- [x] quest accept confirmation
- [x] quest abandon confirmation
- [x] only one active quest
- [x] quest status: locked/pending/active/completed/failed/abandoned
- [x] quest trigger `location_enter`
- [x] quest trigger `character_defeat`
- [x] quest trigger `item_obtained`
- [x] quest trigger `item_use`
- [x] quest trigger `social_check`
- [x] quest rewards: item/gold/XP from seed only
- [x] quest completed state and front payload
- [x] quest failed/abandoned state and front payload
- [x] `level_up/options` requires enough XP
- [x] level-up consumes current level XP and increments level
- [x] max level 10 blocks level-up
- [x] stat +1 choice
- [x] max HP +1 choice
- [x] max MP +1 choice
- [x] learn new skill choice
- [x] upgrade skill tier up to 3
- [x] level-up choice list max 3
- [x] level-up choice list does not flash 2 then later grow
- [x] level-up applied feedback log visible
- [x] level-up no legacy skill term in player-facing text

## 13. LLM, Prompt, Fallback, Error Boundaries

- [x] `classify` prompt/schema/retry
- [x] `graph_intro` prompt/output
- [x] `graph_narrate` prompt/output/meta parse
- [x] `combat_narrate` prompt/output/meta parse
- [x] `recommend` level-up skill candidate prompt/schema
- [x] route env default/fallback resolution
- [x] LLM JSON retry failure returns in-game fallback for play routes
- [x] free narration failure returns fallback and preserves state
- [x] target ambiguous/unknown returns HTTP 200 in-game message
- [x] engine rejection returns HTTP 200 in-game message
- [x] storage/internal failures return 500 class
- [x] LLM narration does not emit JSON to player
- [x] LLM narration does not change graph facts
- [x] LLM narration does not invent movement/item/combat results
- [x] GM tone: player fan, readable, not bland result labels
- [x] combat text removes unnecessary filler/result-explanation phrases

## 14. Persistence And Reload

- [x] LocalFs graph persistence reload
- [x] LocalFs scenario repo reads graph/scenario folders correctly
- [x] Supabase graph rows codec round trip
- [x] Supabase progress rows codec round trip
- [x] `next_log_id` monotonic after reload
- [x] pending state restores after reload
- [x] combat state restores after reload
- [x] active quest restores after reload
- [x] current game pointer in client local storage updates after new game
- [x] story graph client storage updates per game id

## 15. Client API And Request Runner

- [x] `getVersion`
- [x] `listProfiles`
- [x] `initGraphSession`
- [x] `requestGraphIntro` stream first
- [x] `requestGraphIntro` plain fallback
- [x] `sendGraphInput` stream first
- [x] `sendGraphInput` plain fallback
- [x] `sendGraphAction` stream first
- [x] `sendGraphAction` plain fallback
- [x] `sendCombatCommand` stream first
- [x] `sendCombatCommand` plain fallback
- [x] `confirmGraphAction` stream first
- [x] `confirmGraphAction` plain fallback
- [x] `rollGraphPending` stream first
- [x] `rollGraphPending` plain fallback
- [x] `fetchLevelUpChoices`
- [x] `submitLevelUp`
- [x] abort/stop button cancels request without surfacing stale error
- [x] stale request generation cannot overwrite newer state
- [x] optimistic player log entries behave correctly
- [x] server suggestions preserve `inputText`

## 16. Client UI Screens And Components

- [x] NewGame profile/race/gender/name/locale controls
- [x] NewGame start disabled/enabled state
- [x] Shell loading state
- [x] Shell error/retry state
- [x] Playing screen stream/update flow
- [x] HeroStrip HP/MP/XP/gold/level
- [x] HeroStrip level-up button visibility
- [x] Composer input disabled/enabled
- [x] Composer suggestions max 3
- [x] StopButton during streaming
- [x] ConfirmDialog confirm/cancel
- [x] RollPanel required roll/d20 UI
- [x] RollingD20 visual not broken
- [x] LevelUpPrompt choices max 3 and stable
- [x] CombatStrip hearts/buttons/supports/result row
- [x] GameOverPanel if applicable
- [x] ContextCard tabs: map/notes/sheet
- [x] PanelBody actions horizontal scroll without visible ugly scrollbar
- [x] NeighborhoodPanel long list scrolls and hides scrollbar
- [x] StoryGraphCanvas web render and node selection
- [x] StoryGraphCanvas native fallback render
- [x] MiniMapPanel render
- [x] MapPanel action buttons
- [x] BGM/sound toggle
- [x] Korean labels live in locale files, not inline JSX where avoidable

## 17. Live Browser: New Game, Layout, Recovery

- [x] active browser target is current dev server
- [x] 새 게임 생성
- [x] 이름 입력/성별 선택/월드 선택/종족 선택/언어 선택
- [x] 인트로 스트리밍과 첫 로그 표시
- [x] 새로고침 후 현재 게임 복원
- [x] 메뉴에서 새로운 이야기로 돌아가기
- [x] 새 게임 생성 후 이전 게임 포인터 갱신
- [x] desktop width text overlap 없음
- [x] mobile width text overlap 없음
- [x] 주변 목록 긴 상태에서 스크롤 가능
- [x] 주변 목록 스크롤바 숨김
- [x] suggestion/nearby chip max 3
- [x] 빈 입력 전송 disabled
- [x] 입력 중 전송 enabled
- [x] 스트리밍 중 중단 버튼 표시
- [x] 스트리밍 완료 후 전송 버튼 복귀
- [x] 네트워크/API 오류 표시 확인
- [x] 중복 클릭 방지

## 18. Live Browser: dev_test README Flows

- [x] NPC 대화: `테스트 가이드에게 말을 겁니다`
- [x] 다중 NPC 대화 1: `마을 주민에게 말을 겁니다`
- [x] 다중 NPC 대화 2: `보급 구역으로 이동합니다`
- [x] 다중 NPC 대화 3: `보급 담당자에게 회복 아이템을 묻습니다`
- [x] 동료 표시: 시작 시 `동행 점검자`
- [x] 동행 이동: `준비실로 이동합니다`
- [x] 퀘스트 수락 확인창: 퀘스트 제안 카드 `수락`
- [x] 퀘스트 포기 확인창: 수락 뒤 패널 `포기`
- [x] 전투 시작 확인창: `훈련 일격으로 훈련용 허수아비를 공격합니다`
- [x] 즉시 승리 흐름
- [x] 강한 전투: `위험 훈련장으로 이동합니다`
- [x] 강한 전투: `중장 훈련 골렘을 공격합니다`
- [x] 강한 전투 도주
- [x] 전투 중 자유 입력: `조심스럽게 거리를 벌리며 상황을 봅니다`
- [x] 판정: `주변을 자세히 살핍니다`
- [x] 판정: `함정 통로에서 철사를 살핍니다`
- [x] 이동: `준비실로 이동합니다`
- [x] 이동: `함정 통로로 이동합니다`
- [x] 이동: `기록 보관실로 이동합니다`
- [x] 안전 휴식: `보급 구역에서 잠을 잡니다`
- [x] 위험 휴식: `위험 훈련장에서 잠을 잡니다`
- [x] 거래 준비: `보급 구역으로 이동합니다`
- [x] 거래 구매: `보급 담당자에게 상점 회복 약초를 삽니다`
- [x] 거래 판매: `보급 담당자에게 회복 약초를 팝니다`
- [x] 아이템 획득: `보급 표식을 줍습니다`
- [x] 아이템 획득: `함정 통로에서 느슨한 철사를 줍습니다`
- [x] 아이템 획득: `기록 보관실에서 밀봉된 보고서를 줍습니다`
- [x] 대상 지정 아이템 사용: `회복 약초를 부상 점검자에게 사용합니다`
- [x] 퀘스트용 아이템 받기: `마을 주민에게 누락된 보급품을 받습니다`
- [x] 퀘스트용 아이템 사용: `누락된 보급품을 사용합니다`
- [x] 아이템 사용: `집중 부적을 사용합니다`
- [x] full HP guard: 시작 직후 `회복 약초를 사용합니다`
- [x] full MP guard: 시작 직후 `마나 시약을 사용합니다`
- [x] HP 회복 성공: golem/flee 후 `회복 약초를 사용합니다`
- [x] MP 회복 성공: training strike 후 `마나 시약을 사용합니다`
- [x] 장비 확인: `훈련 단검`
- [x] 장비 확인: `훈련 조끼`
- [x] 장비 확인: `구리 반지`
- [x] 바닥 아이템 확인: `보급 표식`
- [x] 레벨업 UI에서 능력치 하나 올리기
- [x] API로 `집중 화살` 학습 레벨업 검증

## 19. Live Browser: Combat UX And Text

- [x] 전투 시작 확인 모달
- [x] 전투 시작 취소
- [x] 전투 시작 확정
- [x] 전투 시작 문구가 플레이어를 세우는 톤
- [x] 전투 카드 하트 표시
- [x] 전투 버튼 3개 이하 표시
- [x] 기술 버튼 이름 표시
- [x] 기술 사용 시 MP 감소
- [x] 전투 주사위 UI 깨짐 없음
- [x] 전투 결과 줄이 짧게 표시
- [x] 성공 묘사에 불필요한 결과 설명문 없음
- [x] 실패 묘사가 플레이어를 우습게 만들지 않음
- [x] 방어 행동
- [x] 정밀 행동
- [x] 무모한 행동
- [x] 거리 벌리기 행동
- [x] 이탈 행동
- [x] 대화/항복 유도 행동
- [x] 전투 종료 후 일반 입력 복귀
- [x] 전투 중 자유 채팅
- [x] 전투 중 불가능 행동 처리

## 20. Live Browser: Trade, Party, Items, Map

- [x] 보급 담당자가 거래 가능 대상으로 표시
- [x] 구매 후 소지금 감소와 소지품 증가
- [x] 판매 후 소지금 증가와 소지품 감소
- [x] 소지금 부족 구매 실패 문구
- [x] 장착 중인 아이템 판매 실패 문구
- [x] 동료가 시트/인물/주변 목록에 자연스럽게 표시
- [x] 이동 후 동료 위치/목록 갱신
- [x] 지도 캔버스 렌더링
- [x] 지도 노드 선택
- [x] 지도에서 이동 액션 실행
- [x] 노트/지도 정보 패널 내용 확인
- [x] 주변 인물/장소/할 일 카운트와 실제 목록 일치
- [x] 시트에서 소지품 표시
- [x] 시트에서 장비 표시
- [x] 아이템 사용 가능 시 사용
- [x] 장비 가능 아이템 장착
- [x] 장착 해제
- [x] 불가능한 아이템 사용 처리

## 21. API Scenario Smoke And Edge Cases

- [x] API로 fresh dev_test session 생성
- [x] API로 intro/input/turn/confirm/roll/combat/level_up happy path 실행
- [x] API로 stream event order 수집
- [x] API로 trade buy/sell state delta 확인
- [x] API로 companion 이동 edge 확인
- [x] API로 hidden reveal 전후 PublicState 비교
- [x] API로 quest accept/abandon/complete state 확인
- [x] API로 rest safe/risky result 확인
- [x] API로 combat direct commands 전체 확인
- [x] API로 invalid combat command 422 확인
- [x] API로 pending id mismatch 확인
- [x] API로 nonexistent game 404 확인
- [x] API로 malformed body 422 확인

## 22. QA Runs And Transcript Review

- [x] `.\.venv\Scripts\python.exe agency\run_qa.py --agent socialite --turns 25`
- [x] `.\.venv\Scripts\python.exe agency\run_qa.py --agent all --turns 25`
- [x] generated transcript 경로 확인
- [x] transcript turn number 기준으로 이슈 기록
- [x] 반복 침묵/불가능 행동/어색한 문구/잘못된 key 탐지
- [x] QA에서 발견된 문제 수정
- [x] 수정 후 관련 QA 재실행

## 23. Release Gate

- [x] `git diff --check`
- [x] server 전체 테스트 재실행
- [x] client lint/type/test 재실행
- [x] seed/story validation 재실행
- [x] live browser 핵심 플로우 재확인
- [x] release export 재실행
- [x] generated artifacts/untracked files 확인
- [x] 문서와 실제 behavior 불일치 수정
- [x] 전체 checklist 미완료 항목 검토
- [x] 알려진 잔여 위험을 최종 답변에 명시

