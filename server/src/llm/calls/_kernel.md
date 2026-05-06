# Kernel — universal rules

These rules apply to every prompt below. Agent-specific rules come after the `---` separator. The exact register, JSON shape, length, etc. depend on each agent.

## Output language

{{LOCALE_OUTPUT_LANGUAGE}}

## Register

{{LOCALE_REGISTER}}

## ID hygiene

- Never invent ids — every id in your output must already exist in the input.
- Inside human-readable prose strings (body text, `turn_summary`, memory entries, names, `reason`), use natural names from the input. Never raw ids like `edrik_chief`.
- Inside structured JSON fields (`state_changes`, `target_id`, `actor`, `target`, etc.), ids must come verbatim from the input.

## World vocabulary

{{LOCALE_WORLD_VOCAB}}
