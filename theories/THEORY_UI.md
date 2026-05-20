# UI Theory

## Current claim

The optimal UI architecture is authority-preserving projection with bounded client continuity.

The UI renders committed server state into decision surfaces. It may keep client continuity memory for orientation, but that memory cannot invent executable authority.

## Minimum condition

A UI change is well-placed when it satisfies all of these:

- `services/api` and `services/wire` own transport and contract adaptation.
- `useGame` owns authoritative state application and server actions.
- Logic domains derive decision-relevant panels and affordances.
- Components render stable domain surfaces.
- UI primitives and design tokens own visual consistency.
- Locale files own client labels; server-composed game text renders verbatim.
- Client continuity caches are explicitly non-authoritative and stale cached facts are demoted or disabled before becoming actions.
- No one-tap affordance that initiates a server request may be derived solely from cached continuity. This includes structured graph actions, quest/combat actions, and generated free-text actions.
- Cached-only nodes may provide orientation text. Composer language from cached-only nodes must be exploratory and require ordinary user submission, not immediate execution.

## Boundary or decision forced

Put a change where its UI authority lives:

- Network contract or fetch behavior: services.
- Game state application or server action dispatch: `logic/game/useGame.ts` or request runner.
- Domain calculation: `logic/<domain>/`.
- Domain view: `components/<domain>/`.
- Reusable visual primitive: `components/ui/`.
- Token value: `design/tokens.js`.
- Client-owned label: `locale/`.

Reject changes that duplicate server state as client authority, inline player-visible labels in components, or let cached continuity create stale executable actions. Treat "executable" by effect: anything that sends a server request is executable, even if it is free text rather than a structured `GraphAction`.
