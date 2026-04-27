# Character fragment (NPC / 몬스터)

## 스키마 (핵심 필드만)

```json
{
  "id": "<ASCII snake_case, 예: smith_01, goblin_02>",
  "name": "<한국어>",
  "race_id": "<races/ 의 id 중 하나>",
  "job": "<짧은 한국어, 예: 대장장이 / 정찰병 / 마을 장로>",
  "role": "<배경 한 줄>",
  "appearance": "<외형 한 줄>",
  "description": "<한두 문장 — 성격·역할>",
  "tone_hint": "<말투 한 줄>",
  "level": <int 1~15>,
  "location_id": "<locations/ 의 id, 또는 null>",
  "max_hp": <int — 공식으로 계산>,
  "hp": <max_hp 와 같은 값>,
  "max_mp": <int — 공식으로 계산>,
  "mp": <max_mp 와 같은 값>,
  "stats": {"STR":<0-20>, "DEX":<0-20>, "CON":<0-20>, "INT":<0-20>, "WIS":<0-20>, "CHA":<0-20>},
  "disposition": {"lawful":<0-100>, "moral":<0-100>, "aggressive":<0-100>},
  "xp_reward": <int — hostile NPC 만 박는다, 아래 규칙 참조>,
  "inventory_ids": ["<item id>", ...],
  "equipment": {"<slot>": "<item id>"},
  "combat_behavior": {"attack_priority": "...", "flee_hp_percent": <int>},
  "racial_skill_ids": ["<skill id>", ...],
  "learned_skill_ids": ["<skill id>", ...]
}
```

## 규칙

- `race_id` — **반드시 시나리오의 races 안에 존재**.
- `location_id` — 시나리오의 locations 안에 존재 (또는 `null`).
- `inventory_ids` 와 `equipment` 슬롯의 모든 값들 — 시나리오의 items 안에 존재.

### 스탯 — 페어 트레이드 (절대 위반 금지)

6 스탯은 세 페어로 묶이고, 각 페어 합이 정확히 20:

- `STR + CHA = 20`
- `DEX + WIS = 20`
- `CON + INT = 20`

총합 항상 60. 기본값 10/10/10/10/10/10 (= 페어 20×3). 컨셉에 따라 페어 안에서 트레이드: 강한 적 → STR 14 / CHA 6, 둔한 거구 → DEX 6 / WIS 14, 영리한 약골 → CON 6 / INT 14. 페어 합 20 유지.

### Level 과 HP / MP — 공식대로 박기

- `level` 은 컨셉에 맞게: 평민·노파 1, 일반 병사·도적 3~5, 정예·우두머리 6~10, 고대 괴수·보스 10~15.
- `max_hp = (10 + CON) + level × (5 + CON ÷ 4)`
- `max_mp = (5 + INT) + level × (3 + INT ÷ 4)`
- `hp = max_hp`, `mp = max_mp` (시드는 풀체력 시작).

예) level=5, CON=14, INT=10 → max_hp = (10+14) + 5×(5+14÷4) = 24 + 5×(5+3) = 64. max_mp = (5+10) + 5×(3+10÷4) = 15 + 5×(3+2) = 40.

### Equipment — 슬롯 매핑 (가이드)

- `equipment` 슬롯은 `head/top/bottom/feet/leftHand/rightHand/acc1/acc2` 중 하나.
- weapon → `leftHand` 또는 `rightHand`. armor → `head/top/bottom/feet`. consumable 은 equipment 에 못 박는다.
- two-handed weapon 은 `leftHand` 와 `rightHand` 양쪽에 같은 id 를 박는다.
- decorative item (effects=null) 은 `acc1`/`acc2` 슬롯.
- equipment 슬롯의 id 는 `inventory_ids` 안에도 있어야 한다 (강제).
- 인벤 무게 합은 `STR × 10` kg 을 넘으면 안 된다 (강제).
- `inventory_ids` 의 item 은 컨셉에 맞으면 적절한 슬롯에 박아라 — 도적이 단검을 갖고 있으면 `rightHand` 에, 외투를 갖고 있으면 `top` 에. 자연스러움 우선, 강제 X.

### 소지품 — 직업·세계관에 맞게 (가이드, 강제 X)

`world.md` 의 시대·톤에 맞는 inventory + equipment 를 자연스럽게 갖추게 한다. 빈손·맨몸 NPC 가 어색해 보이면 직업·역할에 어울리는 소지품 1~3 개를 채워라.

세계관 톤 매핑 — 분해기와 동일 (`_decompose.md`):

| 세계관 | 의복(armor) | 무기 | personalization |
|---|---|---|---|
| 중세 판타지 | 천옷·가죽·갑주 | 검·활·도끼 | 약초·부적·룬·잠금쇠·지팡이 |
| 동양 무협·삼국 | 도복·관복·갑옷 | 검·창·암기 | 죽간·인장·금화·서신 |
| 근세 (조선·에도) | 한복·기모노 | 칼·총포 | 회중시계·인장·종이지폐·곰방대 |
| 현대 | 셔츠·정장·청바지 | 권총·칼 | 스마트폰·지갑·신분증·열쇠·노트북 |
| 사이버펑크 | 합성 의류·코트 | 권총·블레이드 | 단말기·해킹툴·암호 칩·임플란트 |
| 포스트 아포칼립스 | 누더기·방한구 | 임시 무기·총 | 통조림·라디오·약병·낡은 사진 |

직업·역할 매핑 — 위 톤 안에서:

- 사회적 (상인·관료·외교관·정보꾼) → 신분 표식 + 호신구
- 무력 (전사·병사·도적·우두머리) → 무기 1~2 + 방어구 (보스급은 풀세트 + 트로피)
- 지식·치유 (현자·치료사·학자·노파) → 휴대 도구·약·자료
- 정보·은밀 (첩자·도둑·암살자) → 잠입·해독 도구 + 작은 무기

**짐승·괴수·자연적 적**: 옷·무기 inventory 비워도 OK. 자연 무기로 싸운다 (시스템 fallback).

### combat_behavior — 적대 NPC 에만

- 적대 NPC: `aggressive` 70~100 + `combat_behavior` 박기 (예: `{"attack_priority":"nearest", "flee_hp_percent":25}`).
- `attack_priority` 는 정확히 5 개 중 하나: `"nearest"` | `"lowest_hp"` | `"highest_threat"` | `"healer_first"` | `"random"`.
- 비적대 NPC 는 `aggressive` 70 미만 + `combat_behavior` 박지 말 것.

### xp_reward — 적대 NPC 에만

플레이어가 이 NPC 를 죽였을 때 받을 xp. 비적대 NPC 는 0 (생략 = 0).

| character.level | 권장 xp_reward |
|---|---|
| 1 (잡몹·들쥐·소도둑) | 40~80 |
| 2~3 (정예 도적·경비) | 100~200 |
| 4~5 (소대장·정예 마법사) | 250~400 |
| 6~10 (보스급 우두머리) | 500~1000 |
| 11~15 (전설급) | 1500+ |

플레이어 레벨업 비용 = `100 × current_level` (linear). level 0 → 1 = 100. xp_reward 는 한 번의 킬로 1~2 레벨 이상 점프하지 않게.

### Skill — id 만 박는다 (스킬 본체는 별도 단계)

- 주인공은 빈 채로 시작해 게임 중에 배우지만, 시드 NPC 는 race · job 에 어울리는 `learned_skill_ids` 1~3 개를 갖고 등장.
- 이 단계에서는 **id 만** 박고 (예: `["drill_strike", "guard_focus"]`), 실제 Skill JSON 은 별도 `skill` 단계에서 만든다.
- `racial_skill_ids` 는 보통 race 가 정한 racial skill 의 id 가 그대로 들어가지만, 시드 NPC 가 race 외 추가 racial skill 을 가져야 할 경우만 직접 박는다 (대부분 비워두면 race 의 기본값이 자동 상속).
- 컨셉 매핑 예) 도적·전사: STR/DEX 기반 attack · 마법사: INT 기반 attack/buff · 노인·정보꾼: WIS 기반 buff/debuff · 거대 몬스터: STR/CON 기반 area attack.
- 같은 시나리오 안의 다른 캐릭터가 같은 skill 을 공유해도 OK — id 는 유일하지만 참조는 여러 명이 가능.

### 그 밖에

- `is_player`·`gold`·`xp_pool`·`active_buffs`·`memories` 등은 박지 말 것 (런타임이 채움). `xp_reward` 는 예외 — 시드 단계에서 박는 게 맞다 (hostile NPC 한정).
- `tone_hint` 는 짧고 구체 ("퉁명스러운 단답, 가끔 긴 한숨" 식).
- 기존 character 와 이름·역할 중복 금지.

## 검증

작성된 character 는 빌드 단계에서 `backend/src/engines/invariants.py` 의 `check.seed_character` 로 자동 검증된다. 룰 어기면 위반 메시지가 self-correction 루프로 돌아온다 — 한 번에 모든 위반이 보고되니 그에 맞춰 모두 고쳐라.
