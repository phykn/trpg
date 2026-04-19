# 2. Phase 현황

> 상위: [plan.md](../plan.md)

## 2.1 P1 (현재 구현 중)

- FastAPI 골격, 세션 생성·로드·저장 (파일 JSON)
- 턴 파이프라인: judge → (roll 분기 시 pending → 프론트 주사위 → /roll) → narrate → apply
- 컨텍스트 조립: surroundings, target_view, history
- 도메인 스키마, GameState 컨테이너, 내부↔프론트 매핑
- SSE: `judge / pending_check / narrative_delta / state_patch / log_entry / done / error`
- 단일 프로필 로더 (`config/profiles/default/`)
- 최소 메모리·호감도·월드 시간 (grade·intent까지, disposition 보정은 P3)
- LAN 내부만 (env fail-fast, 인증 없음)

## 2.2 구현된 확장 필드 (narrator 힌트용, P1 에서 이미 노출)

구조만 엔진이 제공하고 강제 규칙은 없는 "묘사용 힌트" 필드. narrator 가 자연어로 반영할지 판단.

- **날씨**: `Location.weather: list[str]` 가 surroundings 의 location 섹션에 노출. 엔진은 자동 변화시키지 않으며, narrator 가 `set locations.{id}.weather` state_change 로 갱신.
- **NPC 영업시간**: `Character.active_hours: str | None` (예: `"08:00-22:00"`, 자정 걸치는 `"22:00-06:00"` 지원). 값이 있으면 surroundings NPC 엔트리에 `active: bool` 플래그가 붙음. 엔진은 거래 등에서 강제하지 않음 (P3 에서 강제 고려).

## 2.3 P2 (전투)

- `combat_state`, 이니셔티브, `/turn` action=combat 분기
- 전투 DC (방어도 합산), 무기 range 기반 스탯 선택
- NPC AI (확률 규칙, `combat_behavior`)
- 도주 (기회 공격 포함), death save, revive_coins
- SSE 이벤트 추가: `combat_start / combat_turn / combat_end`
- 내부 `state_change` 타입 `death` 활성화

## 2.4 P3 (확장)

- 장비 장착/탈착, 인벤토리 무게, 거래 (buy/sell/흥정)
- 성장 루틴 (rest / train / learn)
- 스킬 시전 파이프라인 (`cast`), `ActiveBuff` 틱
- 퀘스트 자동 진행 (`check_quests`), 챕터·캠페인 전환
- 동반자 시스템
- 메타 액션 REST 엔드포인트 (버튼 기반 equip/rest 등)
- `rejected[]` 기반 내러티브 자가 보정 루프
- 월드 시간 세밀화 (이동·휴식·전투 턴별 경과)
- affinity disposition 보정 (lawful/aggressive/moral)
- 인증·외부 노출 (LAN 해제)
