# Table Notes GM UI Design

## Goal

Make the play screen feel like sitting with a GM at a TRPG table, while keeping every system detail accessible when the player needs it.

The default experience should be conversation-first. System information must not interrupt the GM narration unless the player explicitly opens a tool or the game enters a mode where visible mechanics are part of the fantasy, such as combat.

This design supersedes earlier UI notes that kept the minimap or broad combat actions prominent by default. Future implementation should prefer folded map access and the three combat actions defined here.

## Product Feel

The player should feel that the GM is carrying the scene forward. The UI should support the conversation instead of turning each turn into a dashboard review.

The design uses a table metaphor:

- GM narration is the conversation at the table.
- The map is a folded table map.
- Notes are a notebook for facts, objectives, relationship changes, and system logs.
- The character sheet contains detailed player state.
- Combat is a temporary board placed on the table.

## Default Play Surface

The default screen shows only what the player needs while talking to the GM:

- GM narration and player entries.
- The input composer.
- A small player HUD with HP, MP, experience, and revive count.
- Folded entry points for map, notes, and character sheet.

The default screen must not show:

- combat hearts outside combat
- NPC or monster stat cards
- detailed system logs
- quest detail cards
- expanded map content
- roll or combat result cards between GM messages

The GM narration should describe meaningful state changes in natural language. For example, instead of showing a separate `affinity -1` card, the GM should describe how the NPC closes off, hesitates, or becomes wary.

## Folded Tools

All detailed information remains available, but it starts folded.

### Map

The map is useful, but it should not stay open by default. The folded map entry point should be visible enough that the player knows it exists.

Opening the map shows:

- current location
- reachable adjacent locations
- blocked or risky routes when known
- important visible NPCs or threats when relevant

The map should behave like a reference tool, not the main play surface.

### Notes

Notes are the primary place for information the player might forget.

Opening notes shows:

- recent important changes
- active objectives
- clues and known facts
- relationship changes
- compact system log entries

Notes should read like a useful table notebook. They should not feel like a live telemetry feed.

### Character Sheet

The character sheet stores detailed player information:

- HP and MP details
- experience
- revive count
- abilities
- skills
- inventory
- equipment
- traits and statuses

Only HP, MP, experience, and revive count belong in the always-visible HUD.

## Combat Mode

Combat is the exception where visible mechanics are expected. When combat starts, a compact combat card appears under the GM conversation or directly above the composer.

The card shows:

- player hearts
- opponent hearts
- player HP
- player MP
- revive count
- current opponent
- a short combat context line
- three action buttons: `공격`, `막기`, `기술`

Hearts are temporary combat resources. They should be visible only during combat.

## Combat Actions

Combat buttons execute immediately.

- `공격` runs the basic attack.
- `막기` runs the basic defense action.
- `기술` automatically selects and uses the skill that best fits the current scene.

The `기술` button prioritizes scene fit over numerical efficiency. It should choose the skill that makes the current moment feel coherent. It should avoid clearly invalid choices, such as using a skill the player cannot afford, but it should not behave like an optimization engine.

After a combat action resolves, the result appears as GM narration. The UI should not insert a separate result card such as `attack success` or `enemy hearts -1` into the conversation.

The combat card quietly updates hearts and resources after the GM narration.

## GM Narration Contract

The GM should explain state changes through the scene whenever possible.

Good:

```text
당신이 방패를 끌어올리는 순간, 상대의 칼끝이 금속을 긁고 지나갑니다. 충격은 팔을 저리게 만들지만, 자세는 무너지지 않습니다.
```

Bad:

```text
막기 성공. 플레이어 하트 +1.
```

The engine may still produce structured results internally, but the player-facing conversation should prioritize scene language.

## Failure Handling

Failure should move the scene forward. The UI and runtime should avoid presenting failure as a dead stop.

When an action cannot be accepted as stated, the GM explains what pressure, cost, danger, or altered opportunity the action creates.

This design does not require every impossible action to succeed. It requires the game to preserve the feeling that the GM is on the player's side and looking for the most interesting valid continuation.

## Information Distance

Information is organized by distance from the conversation.

Always visible:

- GM conversation
- composer
- HP
- MP
- experience
- revive count
- folded map, notes, and sheet entry points

Visible only in active mode:

- combat hearts
- combat action buttons
- roll controls, if a roll mode is active

Visible on demand:

- full map
- notes
- detailed system log
- active objectives
- relationship changes
- character sheet details
- inventory, equipment, and skills

## Out Of Scope

This design does not change:

- combat math
- skill effect templates
- scenario content
- LLM provider behavior
- persistence schema
- map graph rules

This design also does not remove system information. It changes where and when that information is shown.

## Acceptance Criteria

The design is successful when:

- normal play reads as GM conversation first
- system cards do not appear between ordinary GM turns
- map, notes, and sheet are available without being open by default
- the always-visible HUD contains only HP, MP, experience, and revive count
- combat visibly enters a separate mode with hearts and three buttons
- combat buttons execute immediately
- `기술` chooses a scene-fitting usable skill
- combat results are narrated by the GM, not displayed as standalone result cards
- detailed logs remain accessible from notes
