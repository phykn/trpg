# API

The boundary between the server and the client. Every route except `GET /health` needs Basic Auth (`local/local` with `--local`). The server composes the Korean sentences in responses, and the client shows them verbatim. The `/games/*` routes, the save's `schema_version`, request receipts and the browser's `trpg.game_id` stay unchanged unless a migration is requested.

## 1. Routes

| Route | Body | Response |
|---|---|---|
| `GET /health` | | `{ok: true, mode: "engine"}`, without auth |
| `GET /stories` | | Story list: `id`, title, premise, approach values, trait candidates and `pick` |
| `POST /games` | `{request_id, story, creation}`. `creation` is `{name, approaches, traits}`, and `name` is 1–10 characters after trimming whitespace | `{game_id, view}`. `game_id` is a hash of `request_id`, so resending the same request returns the same response for the game already created (409 if the body differs) |
| `GET /games/{id}` | | `view` |
| `POST /games/{id}/commands` | Section 2 | `CommandResult` |
| `GET /games/{id}/turns/{n}/narration` | | NDJSON (section 4) |
| `GET /games/{id}/chapters/{k}/recap` | | NDJSON (section 4) |

`request_id` is a string (a UUID, at most 64 characters) that the client creates fresh for each command.

| Error | When | Body |
|---|---|---|
| 404 | No such game | |
| 409 | Stale `revision`, or a different body for the same `request_id` | `{view}` — the client adopts this `view` |
| 409 | Incompatible save (`schema_version` or the story `digest` differs) | `{reason: "incompatible"}`, no `view` |
| 422 | Malformed request | `{reason}` |

A model that does not respond is not an error but an unreadable answer (engine.md 3.5). A narration model failure is an `error` in the stream.

## 2. Commands

The body of `POST /games/{id}/commands` is `{request_id, revision}` plus one of the following.

| Body | Meaning |
|---|---|
| `text` | The player's sentence |
| `action` | A button's action id (`view.buttons`, `view.growth`) |
| `card, pick` | An answer to a card. `pick` is an id from that card's `options` |
| `card, cancel: true` | Discards the card |

```
CommandResult
{ "kind": "turn" | "card" | "refused",
  "turn": 12 | null,          the turn number when there are steps ({n} in the narration route)
  "steps": [step record, …],  executed steps. If a card stopped the turn, the steps before it are still here
  "reason": "…" | null,       why it was refused (Korean)
  "view": GameView }
```

- `kind` is `card` whenever a card stopped the command, even if there are `steps`. The client decides whether to reveal from whether `steps` exist, and whether to show a card from `view.card`.
- `refused`: a layer-0 refusal, a sentence asking for an action that is not possible now (with its cause when the engine knows it: a blocking obstacle, someone not here, a thing not held), a sentence moving to where the player already is (engine.md 3.2, 3.3), an `action` outside the candidates, or, at the same `revision`, a `pick` outside the options or a stale card id. Neither the state nor the `revision` changes.
- The step that accepted a card is `steps[0]`.

## 3. Step records

There is one per executed step. It is built only from the `Step` (result, risk, `mods`), the player's projection of the events `seen[player]`, `λ`, and names from the presentation layer. It contains no hidden changes.

```json
{
  "t": 7, "action": "try:door:finesse;rely=thing:key", "label": "열쇠로 자물쇠를 연다",
  "result": "success", "risk": "normal", "dc": 8,
  "roll": {"d1": 4, "d2": 3},
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2},
           {"kind": "help", "label": "윤슬의 도움", "value": 1},
           {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "total": 9, "decisive": [0],
  "changes": [{"kind": "fill", "id": "door", "name": "녹슨 등대 문", "from": 0, "to": 2, "fit": 1}]
}
```

- `mods` is a list of chips, in the order `stat`, help or guard, hinder. Several hinder atoms still make a single hinder chip (value −1, names joined with `·`). The `stat` chip is present even when its value is 0; help and hinder have no chip when they are 0. A `guard` chip (a spent reliance, rule.md 3.2) always has value 0: it lowers a fail's cost, not the total. It has the same shape and order as the card's `preview.mods`, so the client pairs chips by index to move them.
- Only the server (`view.py`) computes `total` and `decisive`. The result is `success` if `total ≥ dc`, otherwise `fail`. `decisive` lists the indices (from 0) in `mods` of the chips whose removal would change the result against `dc`. In the example above, without the 2 from 솜씨 (finesse) the total would be 7, short of the target 8, and the roll would have failed.
- `changes` groups the atoms of `δ` into client-facing kinds, and `from` and `to` are visible values. Kinds: `fill` (obstacle boxes; `fit` is how many extra boxes the fitting approach filled), `clock`, `crisis` (`name` is the clock name), `tag_add` (`replaced`: the overwritten tag's name, when the ring was full), `tag_remove`, `wound`, `fall` (the wounds reset by a fall; it replaces `wound`), `scar`, `scene_end` (before the clocks it moved), `move` (`with: true` when a companion moves along with the player), `follow` (`state`: `start` or `stop`, with the person's `id` and `name`), `reveal`, `forget` (a person in sight gave up a belief; `text` is the belief), `consume` (a thing left the world), `flag` (a flag with texts took a value that has one; `text` is its line), `link`, `regards`, `promise`, `arrival` (`name` is the threat name), `fork` (a fork came to the player; `choices` are its choice names), `chapter` (`from: k, to: k+1`), `ending` (`id`). Beats go only through `view.player`.
- A step without a roll has `dc: null`, `roll: null`, `mods: []`, `total: null`, `decisive: []`, and its `result` is `none`. A hidden block has `result: "blocked"`, and its `changes` begin with `{kind: "reveal", id: <obstacle id>, name}`, followed by whatever the beat it spent brought (a scene end's clocks and tags, an arrival, a chapter change, an ending).
- The dice's `u` and `seed` are not sent. `u` only picks a complication and plays no part in the player's experience.

## 4. Narration stream

`GET /games/{id}/turns/{n}/narration` is NDJSON. Text is never sent before it passes the check, so the client never shows an invented sentence.

```
{"type": "stage", "stage": "writing"}      writing the draft
{"type": "stage", "stage": "checking"}     checking
{"type": "stage", "stage": "rewriting", "attempt": 2}
{"type": "text", "text": "…"}              the whole accepted narration
{"type": "done", "tags": [{"slot": 1, "owner": "player", "name": "젖은 발"}]}
{"type": "error", "message": "…"}          the model did not respond. A new request starts over
```

When a cache exists, only `text` and `done` are sent, immediately. Overlapping requests for the same turn produce it once, and the others wait for that result. `GET /games/{id}/chapters/{k}/recap` uses the same format. `k` is the `from` of the `chapter` change if the step records' `changes` contain one, or `view.chapter.k` if they contain an `ending`.

## 5. `GameView`

Everything is built from `Obs` and the presentation layer.

| Field | Contents |
|---|---|
| `revision` | The value to send with the next command |
| `story` | `{id, title, premise}` of this game's story. The first turn shows `premise` where the narration would go |
| `chapter` | `{k, title, aim}`: chapter number, title, aim sentence |
| `scene` | Place name, sensory cues, visible people (name, attitude word, `with` if a companion), things, obstacles (name, boxes, what they block), exits |
| `player` | Name (`creation.name`; an empty string in old saves), the four approaches, traits (name, whether used this chapter), tags (slot, kind, lifetime, name), things carried (name, whether used this chapter), wounds/boxes, beats/`B`, growth |
| `clocks` | Risk clocks in play, deadlines, active threats and forks (name, `fill`, boxes, kind) |
| `journal` | Beliefs (sentences in `B`, the order they were learned, whether they refer to something in the current scene, whether used this chapter), promises and debts (`owes`), relations per person, fork choices (name, chapter) |
| `buttons` | Suggestions (rule.md 9): action id, label, whether it rolls |
| `growth` | Growth actions `[{action, label, kind, name, text}]` (when growth is 1 or more). `kind` is `approach`, `trait` or `scar`, and `name` is a short name written under that branch ("뱃사람 → 토박이", sailor → islander). `text` is the new trait's description for a trait swap, otherwise empty |
| `card` | The pending card (below), or none |
| `last` | The last turn's number, its step records, and whether its narration is cached |
| `recaps` | Chapter numbers that have a recap |
| `ending` | Ending id and title, or none |
| `ledger` | Once the game has ended, per chapter what passed between the player and people: `[{chapter, lines: [{kind, state?, text}]}]`, `kind` being `give` (a thing handed over either way), `promise` (`state` made, kept, broken or closed), `follow` (`state` start or stop) or `regards` (a trust that ended the chapter elsewhere than it began). `text` is the step line, shown verbatim. Empty before the ending |

Cards (engine.md 4):

```
{ "id": "c42", "kind": "roll" | "clarify" | "confirm" | "move",
  "echo": {"text": "열쇠로 살살 돌려 본다", "slots": [{"slot": "approach", "label": "솜씨"}, {"slot": "strain", "label": "자연스럽게"}]},
  "plan": {"step": {"action": "try:door:finesse", "label": "녹슨 등대 문을 솜씨로 다룬다", "target": {"id": "door", "name": "녹슨 등대 문", "fill": 0, "boxes": 3}},
           "rest": ["등대 꼭대기로 간다"]},
  "options": [{"id": "try:door:finesse;rely=thing:key", "label": "등대 열쇠", "consumed": true, "note": "이번 장 1번",
               "rely": "thing:key", "forced": false, "preview": {…}},
              {"id": "try:door:finesse", "label": "기대지 않음", "consumed": false, "note": null, "rely": null, "forced": false,
               "preview": {…}}],
  "selected": "try:door:finesse;rely=thing:key" }
```

A clarification card's `options` are `{id: action id, label}`, plus `dc` and `risk` from the preview when the option is a roll on an obstacle (a way round a guard), and confirm and move cards' `options` are `[{id: action id, label, effects: [name]}]`. A give's confirm card has a second option, the show of the same thing (engine.md 4.3). A move card's option to go with someone asked first has `with` (that person's name) and an id that joins its plan's action ids with `+`; it is accepted like any other `pick`. None of the three has a `preview`. A move card's `selected` is the destination the sentence chose, and it is the first option; when the sentence named that place alone, a card comes only for a companion who stays behind, and that place is its only option (engine.md 4.4). A roll card option's `consumed` says relying on it uses it up, and `note` is the text for that ("1번 남음", 1 use left, for a tag; "이번 장 1번", once this chapter, for a trait, thing or belief); `rely` is its reliance value (null for none), and `forced` whether it is the forced twin of the same reliance: a card where forcing buys a box lists every option twice, the natural ones first (engine.md 4.2). Its `preview` holds the fields from rule.md 3.4.

```
{ "risk": "normal",
  "mods": [{"kind": "stat", "label": "솜씨", "value": 2}, {"kind": "guard", "label": "등대 열쇠", "value": 0}, {"kind": "hinder", "label": "흩날리는 물보라", "value": -1}],
  "z": 1, "dc": 8,
  "stakes": {"clock": 1, "weight": "light" | "heavy" | null},
  "clock": {"id": "clock.1", "name": "몰려오는 폭풍", "boxes": 4, "fill": 1},
  "gain": {"kind": "fill", "boxes": 2, "fit": 1, "forced": 0} | {"kind": "tag", "remove": "젖은 발" | null}
        | {"kind": "topic"} | {"kind": "favor", "effects": ["등대 열쇠를 받음"]} | {"kind": "follow"} }
```
