# 부록 A: 레거시 CLI ↔ 신규 API/파이프라인 대응

> 상위: [plan.md](../plan.md)

레거시 `.venv/bin/python src/cli/main.py <command>` 에 대응하는 back 의 엔드포인트/함수:

| 레거시 CLI | 역할 | back 대응 |
|---|---|---|
| `init` | 새 게임 인스턴스 생성 | `POST /session/init` → `state.init.init_game` |
| `scene --actor ID` | surroundings + session + history 조립 | `GET /session/{id}/state` (프론트 슬롯으로) + 내부 `pipeline.context.build_*` |
| `target-view --actor --target` | target_view 조립 | 내부 `ontology.target_view.build` (직접 노출 없음, narrate 호출 때만 사용) |
| `validate-target --actor --target` | target 유효성 확인 | 내부 `pipeline.judge` 의 폴백 로직 |
| `roll --actor --stat --tier [--target]` | sigmoid 판정 + social_bonus | `POST /session/{id}/turn` (action=roll 분기) + `POST /session/{id}/roll` |
| `initiative --actors a,b,c` | 전투 이니셔티브 [P2] | 내부 `pipeline.combat.start_combat` [P2] |
| `attack --actor --target` | 무기 전투 판정 [P2] | `/turn` action=combat 분기 [P2] |
| `cast --actor --skill --targets` | 스킬 시전 [P3] | `/turn` + `pipeline.skill.cast` [P3] |
| `defend --actor` | 방어 자세 [P2] | `/turn` [P2] |
| `flee --actor` | 도주 판정 [P2] | `/turn` [P2] |
| `death-save --actor` | HP 0 회복 판정 [P2] | 자동 (`pipeline.turn` 내부) [P2] |
| `move --actor --destination` | 이동 + 잠금 + world_time | narrator `{type: "move"}` state_change |
| `rest --actor [--minutes N]` [P3] | HP/MP 회복 + 시간 경과 | `POST /session/{id}/rest` [P3] |
| `train --actor --stat` [P3] | XP → 스탯 | `POST /session/{id}/train` [P3] |
| `learn --actor` [P3] | 스킬 습득 | `POST /session/{id}/learn` [P3] |
| `use --actor --item` [P3] | 소비 아이템 사용 | `POST /session/{id}/use` [P3] |
| `search --actor` [P3] | 숨겨진 아이템/통로 공개 | `/turn` + narrator `set hidden_items` [P3] |
| `equip / unequip` [P3] | 장비 장착/탈착 | `POST /session/{id}/equip` [P3] |
| `buy / sell` [P3] | 상거래 | `POST /session/{id}/trade` [P3] |
| `combat-start / combat-next / combat-end` [P2] | 전투 루프 | 내부 자동 (SSE `combat_*` 이벤트) [P2] |
| `apply --changes JSON` | state_changes 적용 | 내부 `pipeline.apply.apply_changes` (narrator 가 호출) |
| `memory --targets JSON --content --importance` | 직접 메모리 저장 | 내부만 (narrator 의 `memorable=true` 로만 저장) |

P1 범위는 이 표의 **굵지 않은 6줄** (init / scene / validate / roll / move / apply).
