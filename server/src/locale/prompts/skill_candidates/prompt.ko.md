플레이어의 최근 행동과 능력치를 보고 레벨업 때 배울 수 있는 스킬 후보 1-2개를 만든다.

출력은 JSON 하나만 쓴다.

```json
{"skills":[{"name":"", "description":"", "action":"attack", "effect_template":"dc_down", "support_bonus":2, "mp_cost":2, "tags":[""]}]}
```

규칙:
- `action`은 `attack`, `defend`, `flee`, `social` 중 하나다.
- `effect_template`은 `dc_down`, `extra_heart_damage`, `prevent_heart_loss`, `escape_boost` 중 하나다.
- `support_bonus`와 `mp_cost`는 1-3의 정수다.
- 피해량, 회복량, 재사용 대기, 대상 수를 만들지 않는다.
- 스킬은 행동을 대체하지 않고 전투 판정에 붙는 보조다.
- 이미 배운 스킬과 이름이나 역할이 겹치지 않게 한다.
