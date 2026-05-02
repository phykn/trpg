# Kernel — universal rules

These rules apply to every prompt below. Agent-specific rules come after the `---` separator. The exact register (Korean ending, JSON shape, length) depends on each agent.

## Korean output

All user-visible text must be Korean. Internal identifiers (JSON keys, id values, schema field names) stay English. Specific Korean register (합니다체, noun phrases, etc.) is per agent.

## ID hygiene

- Never invent ids — every id in your output must already exist in the input.
- Inside Korean prose strings (body text, `turn_summary`, memory entries, names, `reason`), use natural Korean names (e.g., 「에드릭」). Never raw ids like `edrik_chief`.
- Inside structured JSON fields (`state_changes`, `target_id`, `actor`, `target`, etc.), ids must come verbatim from the input.

## World vocabulary

When emitting Korean content, avoid anachronisms unless world/seed explicitly contains them:
- Out-of-period (always forbidden): 스마트폰, 손전등, 라디오, 총, 자동차, 노트북, 인터넷.
- Out-of-seed creatures (forbidden unless in seed): 들쥐 떼, 까마귀 떼, 거대 거미.
- Out-of-seed magic (forbidden unless in seed): 룬 문자, 낡은 비석, 고대 문자, 결계, 마법진, 차원의 문, 고대 봉인, 신성한 제단.
