# TRPG UI Session Notes

## Purpose

This file records the UI direction agreed during the May 10, 2026 design session so future Codex turns can continue after compaction without losing context.

The HTML files under `.superpowers/brainstorm/.../content/` are design references only. The production `client/` app is now being updated to follow this direction; keep the production implementation aligned with the decisions below.

## Reference Files

- Visual reference: `client-product-style.md`
- Current main state-gallery prototype: `.superpowers/brainstorm/manual-20260510132903/content/existing-ui-state-gallery.html`
- Current simple single-state prototype: `.superpowers/brainstorm/manual-20260510132903/content/existing-ui-warm-tone.html`
- Rejected/older exploration files remain in `.superpowers/brainstorm/manual-20260510132903/content/`
- Installed design skill: `C:\Users\KN\.codex\skills\frontend-design\SKILL.md`

## Overall Direction

Keep the existing TRPG play UI structure. Do not redesign it into a dashboard, landing page, illustrated RPG screen, or Zelda-style inventory clone.

Use `client-product-style.md` as the tone reference:

- Warm cream outer canvas.
- Dark product surface inside the phone.
- Coral/salmon accent used sparingly for active state, GM border, and primary buttons.
- Minimal shadows.
- Clean hairline borders.
- Serif prose for story log, sans for UI labels and controls.

The screen should feel like a polished text TRPG client, not a fantasy illustration. Do not add decorative character art, forest backgrounds, paper textures, large images, emoji, or ornamental icons.

## User Style Preferences

- Keep the log central.
- Avoid extra explanation text in the UI.
- Use labels only when they carry real information.
- Prefer compact, balanced controls over decorative panels.
- Remove controls that do not do anything in the current state.
- Buttons should use available width evenly when a control row is needed.
- Important state should be visible without forcing the user to inspect tiny UI.
- “주변” as a separate top pill was rejected; nearby summary belongs inside the composer.
- Text like `인물 2 · 장소 1 · 할 일 1` should stay terse. Do not add “주변”.
- The `열기` text/button next to that summary was rejected. The text itself is the tap target.

## Top Pill Behavior

Top pills are `주인공 / NPC / 미니맵`. The old `주변` pill should not return.

When a top pill is opened, its panel overlays the existing screen. It must not push the hero strip, log, or composer down. The background remains the normal play screen behind the opened panel.

The panel should feel like it opens from the top chip row, not like a separate modal window. Use a floating surface positioned below the chips.

### 주인공 Panel

Use the original client structure as the source of truth. The relevant code path is:

- `client/logic/hero/panel.ts`
- `client/components/info-panel/PanelBody.tsx`
- `client/components/hero/HeroStrip.tsx`

The panel should show:

- Title: hero name.
- Meta: level, race/job, gender.
- HP and MP bars with numbers.
- Ability row: e.g. `몸 11`, `민첩 10`, `정신 10`, `존재감 10`.
- Equipment.
- Inventory.
- Skills.
- Companions.
- Traits/status.

Do not show inventory/equipment action buttons inside the main `주인공` top-pill panel for this design pass. The user explicitly asked to delete the sample `집중 부적 사용` / `훈련 단검 해제` action row from the top panel.

The compact always-visible hero strip can still show `체력`, `마나`, `경험`, `소생` with numbers and bars.

### NPC Panel

Use the original client subject panel structure as the source of truth. The relevant code path is:

- `client/logic/subject/panel.ts`
- `client/logic/subject/types.ts`
- `client/components/info-panel/PanelBody.tsx`

The panel should show:

- Title: current subject/NPC name.
- Meta: level, race/job, gender.
- HP bar with number.
- Affinity/trust bar with signed number.
- Ability row.
- Equipment.
- Inventory.
- Skills.
- Role.
- Traits/known facts.

Do not reduce this to a list of NPC cards. The user specifically wants the stat/inventory/detail shape from the original client.

### 미니맵 Panel

The minimap should be a visual map, not a grid of place cards.

Use the original story graph map idea as the source of truth:

- `client/components/story-graph/MiniMapPanel.tsx`
- `client/components/story-graph/NeighborhoodPanel.tsx`
- `client/components/story-graph/MapPanel.tsx`
- `client/components/story-graph/StoryGraphCanvas.web.tsx`

For the concept prototype, represent this as a drawn full map with nodes and connecting edges. It should show the current location, nearby reachable places, and blocked/unreachable places if relevant.

The current prototype uses an SVG node graph in `.superpowers/brainstorm/manual-20260510132903/content/existing-ui-state-gallery.html`.

## Composer And Nearby Summary

The composer is the normal bottom input area.

It should include:

- Nearby summary line inside the composer: `인물 2 · 장소 1 · 할 일 1`.
- Input placeholder: `당신은 무엇을 합니까?`
- Send button: `전송`

The nearby summary itself is clickable. There should be no separate `열기` label or button.

When the nearby summary is tapped, show a nearby panel above the composer. The composer stays at the bottom. The nearby panel should list immediate one-hop actionable items:

- People.
- Places.
- Tasks/actions.

The nearby panel must float above the composer and must not cover the composer. Each nearby item should show the available action as a button on the right, e.g. `대화`, `관찰`, `이동`, `살펴보기`. Pressing that button will later submit/trigger that action.

The prototype state is named `주변 펼침` in `existing-ui-state-gallery.html`.

## Roll And Combat Bottom Behavior

When a roll panel is active, the bottom composer disappears. The roll panel replaces the composer area.

Roll panel rules:

- Show the roll title, e.g. `민첩 판정이 필요합니다`.
- Show the short reason.
- Show the required die using the old client visual format: 20 square cells labeled `1` through `20`, outcome-colored by range, with the required roll cell highlighted, e.g. `13`.
- Do not add a separate `필요 주사위` label or an extra boundary around the dice strip. Put the requirement value, e.g. `13 이상`, in the roll panel header and leave the dice strip as the only lower visual.
- Only show `굴리기`.
- Do not show `멈추기`.
- The roll button should stretch across the panel width.

When a combat panel is active, the bottom composer disappears. The combat panel replaces the composer area.

Combat panel rules:

- Show who the player is fighting, e.g. `어둠 속의 습격자와 전투 중`.
- Show combat context, e.g. `2번째 교환 · 가까운 거리`.
- Show player/enemy hearts on the right side of the combat panel header.
- No extra instruction line like `다음 행동을 고르거나 직접 입력합니다.`
- Action buttons should evenly fill the width: `공격`, `방어`, `도주`, `설득`.

## System Cards

System cards remain in the log stream, not in the composer area.

Use them for:

- Victory.
- Level-up.
- Major state changes.

They should be compact and information-dense. Do not make them feel like marketing cards.

## Current Prototype States

The current gallery prototype should include these states:

- `주인공 패널`
- `주변 펼침`
- `NPC 패널`
- `미니맵 패널 · 전체 지도`
- `전투`
- `주사위`
- `시스템 카드`

The gallery is for comparing states. It is not the production app. Each phone mockup should demonstrate one UI state clearly.

## Rejected Directions

Do not continue these directions unless the user explicitly asks:

- Figma workflow. It hit a limited monthly MCP call quota, and the user chose to continue with local HTML/CSS.
- Full Zelda-style UI recreation.
- Character/forest/scene illustration backgrounds.
- Decorative fantasy frames, heavy parchment, or icon-heavy game HUD.
- Action shortcut buttons at the bottom when they do not map to current functionality.
- Nearby as a top pill.
- Separate `열기` button for nearby.
- Player message as a chat bubble. The player entry should visually match GM narration and differ by text/border color.

## Production Implementation Notes

Before changing production code, read `client/AGENTS.md`.

Likely production touch points:

- `client/design/tokens.js` for the `client-product-style.md`-based color and surface tuning.
- `client/components/ui/Surface.tsx`, `Chip.tsx`, `Bar.tsx`, `Row.tsx`, `StatRow.tsx` for shared visual atoms.
- `client/components/info-panel/ContextCard.tsx` for floating top-pill overlay behavior.
- `client/components/info-panel/PanelBody.tsx` for hero/NPC panel detail layout.
- `client/components/story-graph/MiniMapPanel.tsx`, `MapPanel.tsx`, `StoryGraphCanvas.web.tsx` for the visual map.
- `client/components/combat/CombatStrip.tsx` for combat replacing composer.
- `client/components/composer/Composer.tsx` and roll-related composer components for roll replacing composer.
- `client/components/log/LogItem.tsx` for GM/player/system log styling.

Client-owned Korean labels must live in `client/locale/ko.ts`. Do not add inline Korean literals in production React components.

Do not hardcode colors directly in production components. Use NativeWind classes backed by `client/design/tokens.js` or import token values where the existing app already does that.

## Current Production Implementation State

The current production pass has been applied in `client/`.

Implemented touch points:

- `client/design/tokens.js` now uses a warm dark product surface, muted coral accent, warm borders, and larger but still restrained radii.
- `client/components/ui/Surface.tsx`, `Chip.tsx`, `Bar.tsx`, `InlineNodes.tsx`, and `LabeledRow.tsx` were adjusted so the shared atoms support the warmer direction and wrapped stat pills.
- `client/components/info-panel/ContextCard.tsx` shows only `주인공 / NPC / 미니맵` and opens panels as floating overlays below the chip row.
- `client/logic/hero/panel.ts` keeps the detailed hero panel but removes inventory/equipment action rows from the top-pill panel.
- `client/logic/subject/panel.ts` remains the source for the detailed NPC panel; its chip label is now `NPC`.
- `client/components/story-graph/MiniMapPanel.tsx` uses the full map panel instead of the neighborhood card list.
- `client/components/hero/HeroStrip.tsx` shows hero name/meta, 소지금, and numbered `체력 / 마나 / 경험 / 소생` meters.
- `client/components/composer/Composer.tsx` owns the nearby summary line and expands a nearby panel above the composer without covering the input.
- `client/logic/story-graph/nearby.ts` builds the one-hop nearby summary and action rows from the story graph.
- `client/components/combat/CombatStrip.tsx` replaces the composer during combat, shows opponent context and hearts, and stretches `공격 / 방어 / 도주 / 설득` evenly.
- `client/components/log/Log.tsx` and `LogItem.tsx` remove bottom suggestion strips and make player log entries follow the GM narration rhythm.

Implemented pending-roll contract:

- The graph server exposes `state.pendingRoll` while a roll is waiting. The public payload contains only display fields: id, kind, title, body, stat, stat label, and required roll.
- Internal action payloads stay in `GameProgress.pending_roll` and are not sent to the client.
- The client renders `pendingRoll` as the bottom roll panel, replacing the composer until `/session/{game_id}/graph/roll` resolves it.
- The current first live trigger is `perceive`, so inputs like “주변을 자세히 살펴본다” can create the roll panel.

## Latest User Request State

The latest prototype feedback applied here:

- Remove the `주인공` panel action row.
- Keep the nearby panel above the composer without covering it, and add right-side action buttons per nearby item.
- Add player/enemy hearts to the right side of the combat panel header.
- Replace the roll requirement text-only row with the old client-style 1-20 square dice strip. Highlight the required roll cell; do not add an extra marker above it.
- Keep the roll strip tight: no `필요 주사위` label inside the strip and no separate strip boundary. Move `13 이상` up into the roll header.
- Apply the design to the real `client/` app. The user explicitly said the implementation does not need to be minimal and can change as much as needed.
- Resolve the hook dependency warning before calling the pass finished.
