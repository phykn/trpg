# Character fragment (NPC / monster)

## Schema (core fields only)

```json
{
  "id": "<ASCII snake_case, e.g. smith_01, goblin_02>",
  "name": "<Korean>",
  "race_id": "<id from races/>",
  "job": "<short Korean, e.g. 대장장이 / 정찰병 / 마을 장로>",
  "role": "<one-line backstory>",
  "appearance": "<one-line appearance>",
  "description": "<one or two Korean sentences — personality and role>",
  "tone_hint": "<one-line speech tone>",
  "level": <int 1~15>,
  "location_id": "<id from locations/, or null>",
  "max_hp": <int — computed by formula>,
  "hp": <same value as max_hp>,
  "max_mp": <int — computed by formula>,
  "mp": <same value as max_mp>,
  "stats": {"STR":<0-20>, "DEX":<0-20>, "CON":<0-20>, "INT":<0-20>, "WIS":<0-20>, "CHA":<0-20>},
  "disposition": {"lawful":<0-100>, "moral":<0-100>, "aggressive":<0-100>},
  "xp_reward": <int — set only for hostile NPCs; see rule below>,
  "inventory_ids": ["<item id>", ...],
  "equipment": {"<slot>": "<item id>"},
  "combat_behavior": {"attack_priority": "...", "flee_hp_percent": <int>},
  "racial_skill_ids": ["<skill id>", ...],
  "learned_skill_ids": ["<skill id>", ...]
}
```

## Rules

- `race_id` — **must exist in the scenario's races**.
- `location_id` — must exist in the scenario's locations (or be `null`).
- Every value in `inventory_ids` and the `equipment` slots must exist in the scenario's items.

### Stats — pair-trade (never violate)

The 6 stats split into three pairs, each summing to exactly 20:

- `STR + CHA = 20`
- `DEX + WIS = 20`
- `CON + INT = 20`

Total always 60. Default 10/10/10/10/10/10 (= 20×3 across pairs). Trade within a pair to fit the concept: a tough enemy → STR 14 / CHA 6; a slow giant → DEX 6 / WIS 14; a frail genius → CON 6 / INT 14. Each pair must keep the sum of 20.

### Level and HP / MP — apply the formulas

- `level` matches the concept: commoner / elderly = 1; rank-and-file soldier or bandit = 3~5; elite or captain = 6~10; ancient beast or boss = 10~15.
- `max_hp = (10 + CON) + level × (5 + CON ÷ 4)`
- `max_mp = (5 + INT) + level × (3 + INT ÷ 4)`
- `hp = max_hp`, `mp = max_mp` (seeds start at full).

Example) level=5, CON=14, INT=10 → max_hp = (10+14) + 5×(5+14÷4) = 24 + 5×(5+3) = 64. max_mp = (5+10) + 5×(3+10÷4) = 15 + 5×(3+2) = 40.

### Equipment — slot mapping (guidance)

- `equipment` has 3 slots: `weapon / armor / accessory`.
- weapons → `weapon`. ArmorEffect items → `armor` slot; a second defense piece (a shield, or a ring with +1 to a defense effect) may go in `accessory`. Consumables cannot go into equipment.
- Decorative items (`effects=null`) go in `accessory`.
- Every id used in equipment must also appear in `inventory_ids` (enforced).
- Total inventory weight cannot exceed `STR × 10` kg (enforced).
- Place each `inventory_ids` item in a slot that fits its concept — a rogue's dagger → `weapon`; an outer coat → `armor`; an amulet or ring → `accessory`. Naturalness matters; not strictly enforced.

### Possessions — fit the job and world (guidance, not enforced)

Outfit each character with inventory and equipment that fit the period and tone in `world.md`. Empty-handed NPCs feel off; fill in 1~3 items that match the job and role.

World-tone mapping — same as the decomposer (`_decompose_*.md`):

| World tone | Armor | Weapon | Personalization |
|---|---|---|---|
| 중세 판타지 | 천옷·가죽·갑주 | 검·활·도끼 | 약초·부적·룬·잠금쇠·지팡이 |
| 동양 무협·삼국 | 도복·관복·갑옷 | 검·창·암기 | 죽간·인장·금화·서신 |
| 근세 (조선·에도) | 한복·기모노 | 칼·총포 | 회중시계·인장·종이지폐·곰방대 |
| 현대 | 셔츠·정장·청바지 | 권총·칼 | 스마트폰·지갑·신분증·열쇠·노트북 |
| 사이버펑크 | 합성 의류·코트 | 권총·블레이드 | 단말기·해킹툴·암호 칩·임플란트 |
| 포스트 아포칼립스 | 누더기·방한구 | 임시 무기·총 | 통조림·라디오·약병·낡은 사진 |

Job / role mapping — within the tone above:

- Social (merchant / bureaucrat / diplomat / informer) → status token + light defense
- Martial (warrior / soldier / bandit / captain) → 1~2 weapons + armor (boss tier = full set + a trophy)
- Scholar / healer (sage / healer / scholar / elder) → portable tools, salves, references
- Stealth / informant (spy / thief / assassin) → infiltration / decryption tools + a small weapon

**Beasts, monsters, natural hostiles**: leaving items / weapons empty is fine. They fight with natural weapons (system fallback).

### combat_behavior — hostiles only

- Hostile NPC: `aggressive` 70~100 plus `combat_behavior` set (e.g., `{"attack_priority":"nearest", "flee_hp_percent":25}`).
- `attack_priority` is exactly one of 5 values: `"nearest"` | `"lowest_hp"` | `"highest_threat"` | `"healer_first"` | `"random"`.
- Non-hostile NPC: `aggressive` < 70 plus `combat_behavior` left empty.

### xp_reward — hostiles only

The xp the player gains for killing this NPC. Non-hostile NPCs are 0 (omit = 0).

| character.level | recommended xp_reward |
|---|---|
| 1 (mooks, rats, petty thieves) | 40~80 |
| 2~3 (elite bandits, guards) | 100~200 |
| 4~5 (lieutenants, elite mages) | 250~400 |
| 6~10 (boss-tier captains) | 500~1000 |
| 11~15 (legendary tier) | 1500+ |

The player's level-up cost is `100 × current_level` (linear). Tune `xp_reward` so a single kill never jumps the player by more than 1~2 levels.

### Skills — list ids only (the skill body is its own step)

- The protagonist starts with no skills and learns them in play; seed NPCs ship with 1~3 `learned_skill_ids` matching their race and job.
- At this stage, list **ids only** (e.g., `["drill_strike", "guard_focus"]`). The actual Skill JSON is authored in the separate `skill` step.
- `racial_skill_ids` typically lists the race's racial skill ids unchanged. Fill it explicitly only if a specific seed NPC needs an extra racial beyond the race default; otherwise leave it empty (the race's defaults inherit automatically).
- Concept mapping examples: rogue / fighter — STR/DEX-based attack; mage — INT-based attack/buff; elder / informant — WIS-based buff/debuff; large monster — STR/CON-based area attack.
- Multiple characters in the same scenario can share the same skill — ids are unique, but multiple characters may reference one.

### Other

- Leave `is_player`, `gold`, `xp_pool`, `active_buffs`, `memories`, etc. blank — the runtime fills them. `xp_reward` is the exception (set it at seed time, hostile NPCs only).
- `tone_hint` is short and concrete (e.g., "퉁명스러운 단답, 가끔 긴 한숨").
- Do not duplicate the name or role of an existing character.

## Validation

Each authored character is validated automatically during the build by `check.seed_character` in `server/src/engines/invariants.py`. Rule violations come back through the self-correction loop — every violation is reported in one shot, so fix them all together.
