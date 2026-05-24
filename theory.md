# TRPG Project Theory

## Ideal Theory

이 프로젝트는 한국어 TRPG를 "확정된 graph world"와 "그 graph를 플레이어가 읽고 건드리는 단일 화면"으로 나눈다.

서버는 세계의 권위자입니다. 그래프 상태, 규칙, 판정, 퀘스트, 전투, 저장, LLM 호출, 서버 조합 한국어 텍스트를 확정합니다. 클라이언트는 플레이 표면입니다. 서버가 준 최신 스냅샷을 읽기 쉬운 맥락, 제한된 행동 affordance, 입력 피드백으로 바꾸지만 이야기 사실을 새로 소유하지 않습니다.

## Evidence

- `README.md`는 LLM이 플레이어 의도를 분류하고 나레이션을 쓰지만, engine이 state, rules, rolls, time을 처리한다고 말합니다.
- `AGENTS.md`는 `server/`가 graph runtime, persistence, LLM calls, API routes, server-composed Korean game text를 소유하고, `client/`가 Expo UI, client state, local storage pointer, client-owned Korean labels를 소유한다고 나눕니다.
- `server/AGENTS.md`는 runtime graph를 single source of truth로 두고, 관계 조회는 `characters_at`, `inventory_of`, `equipment_of`, `connections_of`, `known_skills_of` 같은 graph query helper를 통하라고 강제합니다.
- `server/src/game/runtime/flow/input.py`는 자유 입력을 LLM으로 분류한 뒤 pending confirmation/roll을 확인하고, action request나 roll/narrative path로 보냅니다. 입력은 곧바로 fiction이 아니라 runtime action 후보입니다.
- `server/src/game/runtime/flow/turn.py`는 action dispatch를 준비하고 graph/log/progress를 저장한 뒤, 나레이션을 GM log, turn history, exchange history로 붙입니다. 나레이션은 확정 결과의 표현이지 상태 확정자가 아닙니다.
- `server/src/game/runtime/flow/confirmation.py`와 `server/src/game/runtime/flow/roll.py`는 위험한 이동, 공격, 퀘스트 수락/포기, 판정을 pending state로 만들고 `/graph/confirm` 또는 `/graph/roll`에서만 해소합니다. 중요한 선택은 UI의 확인 모달이 아니라 서버 progress의 pending contract입니다.
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`는 graph narration에게 새 결과, 새 상태 변화, 새 보상, 새 퀘스트, 새 전투를 만들지 말고 engine이 확정한 결과만 장면화하라고 반복합니다.
- `server/src/game/runtime/narration/suggestions.py`는 LLM이 준 suggestion도 visible exits, visible characters, usable refs, current place 같은 현재 graph 근거로 다시 거릅니다. 추천 칩도 창작이 아니라 grounded affordance여야 합니다.
- `server/src/wire/graph/to_front.py`는 runtime state를 `GraphFrontStatePayload`로 접습니다. wire layer는 클라이언트가 필요한 표면만 주지만 source는 runtime graph입니다.
- `server/src/api/session_graph_routes.py`는 REST/stream route를 runtime flow에 얇게 연결하고 `GraphActionResponse`로 직렬화합니다. API는 게임 규칙을 새로 판단하지 않습니다.
- `client/AGENTS.md`는 `logic/game/useGame.ts`를 graph game state와 action의 single source로 두되, authoritative state는 graph REST response라고 못박습니다. localStorage에는 active `game_id` pointer만 둡니다.
- `client/logic/game/useGame.ts`는 server `FrontState`를 적용하고, pending confirmation/roll 동안 입력과 action을 막고, 모든 주요 행동을 `sendGraphInput`, `sendGraphAction`, `confirmGraphAction`, `rollGraphPending`, `sendGraphLevelUp`로 보냅니다.
- `client/services/api.ts`는 `expo/fetch`를 쓰는 유일한 graph REST boundary입니다. stream 중에는 optimistic/visible log를 보여줄 수 있지만 final payload를 다시 adapter에 통과시켜 서버 state로 수렴합니다.
- `client/services/graphAdapter.ts`, `client/logic/story-graph/presenters.ts`, `client/logic/story-graph/nearby.ts`는 server front state를 hero, place, combat, nearby/task/action UI model로 바꿉니다. 클라이언트의 계산은 현재 스냅샷을 조작 가능한 화면으로 만드는 일입니다.
- `client/locale/ko.ts`는 client-owned labels와 action text composition을 담습니다. 서버 조합 게임 텍스트와 클라이언트 라벨의 경계가 분리되어 있습니다.
- `agency/qa/SKILL.md`는 실제 UI 플레이를 QA 증거로 삼고 API 직접 호출로 대체하지 말라고 합니다. 최종 제품 품질은 graph correctness만이 아니라 플레이어가 화면에서 이해하고 선택할 수 있는가로 검증됩니다.
- `agency/story/SKILL.md`는 scenario seed를 graph seed로 검증하고 runtime smoke까지 확인하라고 합니다. 시나리오는 원재료이고, 런타임 의미는 graph 변환 뒤 시작됩니다.

## Strongest Gap

클라이언트를 "그냥 렌더러"라고 부르면 현재 구현을 설명하지 못합니다.

클라이언트는 nearby panel, decision state, suggestions, quick actions, combat strip, confirmation dialog, roll panel처럼 플레이어가 어떤 행동을 떠올리고 실행할지에 직접 관여합니다. `client/logic/story-graph/_nodeActions.ts`는 reachable node에서 move, attack, transfer 같은 graph action affordance를 만들고, `client/components/composer/Composer.tsx`는 suggestions와 nearby actions를 실제 입력 표면으로 노출합니다.

따라서 이론은 "서버는 진실, 클라이언트는 표시"가 아니라 "서버는 story authority, 클라이언트는 play-surface authority"여야 합니다. 클라이언트는 이야기 사실을 확정하지 않지만, 플레이어가 현재 상태를 이해하고 다음 입력을 고르는 방식을 소유합니다.

## Refined Theory

TRPG의 핵심 단위는 LLM 대화도, UI 화면도, seed JSON도 아니라 "graph가 확정한 현재 장면에서 플레이어가 다음 행동을 고를 수 있는가"입니다.

서버는 graph source of truth로 상태와 결과를 확정하고, LLM은 그 확정을 한국어 플레이 로그와 보조 cue로 장면화합니다. 클라이언트는 authoritative snapshot을 받아 단일 화면에서 현재 상황, 선택 제약, 행동 후보, 입력 피드백을 정리합니다.

그 바깥에는 authoring/QA loop가 있습니다. `scenarios/`와 `agency/story`는 graph runtime state가 될 수 있는 검증된 playable material을 공급하고, `agency/qa`는 실제 UI에서 그 material과 runtime/client 조합이 플레이 가능한지 reusable criteria로 확인합니다. 하지만 게임이 시작된 뒤 authority는 server graph/runtime을 통해 흐르고, client는 최신 snapshot을 player-facing affordance로 합성합니다.

## Implications

- 새 기능은 먼저 어느 authority를 바꾸는지 정해야 합니다. 상태, 규칙, 판정, quest/combat 결과, server-composed Korean text는 서버 작업입니다. 표시 밀도, action surface, modal/roll/composer behavior, client-owned labels는 클라이언트 작업입니다.
- 클라이언트에 새 story memory, local graph merge, hidden rule inference를 추가하면 이론을 약하게 만듭니다. 클라이언트 affordance는 서버 snapshot에서 다시 만들 수 있어야 합니다.
- 서버 prompt나 narration code가 UI label, nearby name, suggestion label을 player input보다 강한 근거처럼 쓰면 이론을 어깁니다. 실제 입력과 graph-current evidence가 우선입니다.
- LLM output은 항상 "candidate prose plus metadata"입니다. 상태 변경, 보상, 퀘스트, 관계 변화는 engine-confirmed path로만 들어가야 합니다.
- Scenario authoring은 prompt 우회가 아니라 graph-ready material 작성입니다. 시나리오 고유 사실은 scenario files나 `agency/story` guidance에 두고, 공통 runtime/UI 규칙은 server/client/agency QA 기준에 둡니다.
- QA는 API correctness만으로 닫히지 않습니다. 플레이어가 화면에서 목표, 위험, 가능한 행동, 성공/실패를 이해했는지 실제 UI로 확인해야 합니다.
- Authoring/QA는 runtime authority와 다릅니다. seed와 QA 기준은 어떤 세계가 실행 가능하고 좋은 플레이로 읽히는지 준비/검증하지만, live game의 확정 사실은 server graph/runtime에서 나옵니다.

## Next Moves

1. Server: narration brief와 suggestion grounding에서 "actual player input > target_view/current graph evidence > visible names/UI labels" 우선순위가 계속 유지되는지 주기적으로 점검합니다.
2. Server: pending confirmation/roll, quest progress, combat result처럼 선택을 막거나 여는 상태는 wire payload에 선명하게 유지하고, client-only fallback으로 복제하지 않습니다.
3. Client: nearby/actions/decision-state는 계속 "current snapshot presenter"로 유지합니다. map restore, local graph merge, offline story state가 필요해지면 별도 authority 재설계가 필요합니다.
4. Client: action affordance가 많아질수록 UI는 숨은 정답을 알려주는 대신 현재 가능한 범주와 제약을 보여주는 쪽으로 좁힙니다.
5. Agency: QA에서 반복 발견되는 플레이 기준은 `agency/qa/SKILL.md`로 올리고, 시나리오별 worldbuilding은 scenario files나 `agency/story/SKILL.md`에 둡니다.
6. Cross-boundary: UI에 새 표시가 필요하면 먼저 server wire payload가 authoritative fact를 갖고 있는지 확인합니다. 없다면 클라이언트 추론보다 서버 payload 확장이 우선입니다.

## Decision

Keep theory.

이 이론은 문서, runtime flow, prompt contract, wire conversion, client state root, UI presenter, authoring/QA tooling 증거를 모두 설명합니다. 가장 중요한 갭인 "클라이언트도 행동 후보를 만든다"는 이론을 폐기하지 않고 더 정확하게 만듭니다. final clean critic이 지적한 "agency/scenario outer loop"도 runtime authority와 authoring/QA contract를 분리하면 같은 이론 안에 들어옵니다. 클라이언트는 story authority가 아니라 play-surface authority입니다.

## Next Route

Open improvement candidates.

바로 구현할 단일 결함은 아직 없습니다. 후속 작업은 구체 이슈가 잡히는 위치에 따라 나뉩니다.

- narration grounding, rule result, quest/combat/pending state 문제: implementation task in `server/`
- action affordance, composer, modal, log readability, label ownership 문제: implementation task in `client/`
- 책임이 여러 폴더에 흩어져 변경이 위험해진 경우: `loopy-compose`
- 플레이 품질 기준이 애매한 경우: browser QA through `agency/qa/SKILL.md`

Last important gap considered: 클라이언트가 action affordance를 직접 만든다는 점. 이 갭은 "클라이언트는 단순 렌더러"라는 약한 표현만 버리게 만들었고, 최종 route를 바꾸지는 않습니다.
