# LLM TTRPG 엔진 설계 (back)

> 북극성 설계 노트. 전체 시스템의 모양과 이유. 체크리스트가 아니라 참조용.
> Phase 마커: **[P1]** 현재 구현 중 · **[P2]** 전투 · **[P3]** 확장.
> Phase 마커 없는 절은 전 구간 공통 원칙.
> 구현 단위 플랜은 `back/docs/superpowers/plans/` 아래.

섹션별로 파일이 쪼개져 있습니다. 본문 내 교차참조(`§N.M`)는 동일 번호 체계를 쓰며, 해당 번호는 아래 목차에서 파일을 찾아 들어갑니다.

## 본문

1. [설계 철학](./plan/01-philosophy.md) — 역할 분리 (LLM vs 엔진)
2. [Phase 현황](./plan/02-phase.md) — P1 / P2 / P3 구현 범위
3. [에이전트](./plan/03-agents.md) — DC판정 · 내러티브 · LLM 런타임
4. [파이프라인](./plan/04-pipeline.md) — 1턴 흐름, pending_check, SSE, 세션 생명주기
5. [컨텍스트 레이어](./plan/05-context-layers.md) — 월드 · 세션 · 히스토리 · 장면 (surroundings / target_view)
6. [온톨로지](./plan/06-ontology.md) — 그래프 구조, target_view 조립
7. [DC 시스템](./plan/07-dc.md) — 시그모이드 DC, grade, social_bonus
8. [상태 업데이트](./plan/08-state-updates.md) — state_changes 4종 + 프론트 반영
9. [메모리 시스템](./plan/09-memory.md) — 엔티티 기억, importance
10. [전투 [P2]](./plan/10-combat.md) — 전투 DC, NPC AI, 도주, death save
11. [확장 시스템](./plan/11-extensions.md) — 호감도, 월드 시간, 성장, 장비, 스킬, 진행, 동반자
12. [프론트 경계](./plan/12-frontend-boundary.md) — 슬롯, API, 에러 매핑
13. [코드 지도](./plan/13-code-map.md) — 모듈 구조, 레이어 경계, 오류 계층
14. [설계 결정 히스토리](./plan/14-design-decisions.md) — 각 선택의 "왜"

## 부록

- A. [레거시 CLI ↔ 신규 API/파이프라인 대응](./plan/appendix-a-legacy-cli.md)
- B. [환경 변수](./plan/appendix-b-env.md)
- C. [명시적 제외 & 알려진 간극](./plan/appendix-c-exclusions.md)
