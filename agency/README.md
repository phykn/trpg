# Agency — LLM office

Where the LLM staff that helps run the game works in teams. Each team owns its own directory holding agent prompts, the harness, and run output.

```
agency/
  run_qa.py     # QA team CLI entrypoint
  run_story.py  # Story team CLI entrypoint
  qa/           # The QA team — plays the game and catches regressions
  story/        # The Story team — authors scenario seeds (race / character / ...)
```

## QA — game testing via AI players

Works like hiring a QA tester to play the game. Each turn an LLM generates the next input, the harness hits the backend API and collects SSE events into a transcript, then a separate reviewer LLM analyses the transcript and emits a verdict.

### Layout

```
agency/run_qa.py        # CLI entrypoint
agency/qa/
  agents/
    diplomat.md         # Diplomat — focused on NPC affinity and dialogue
    explorer.md         # Explorer — movement, observation, inventory
    provocateur.md      # Provocateur — edge cases, judge-branch triggers
    reviewer.md         # Analyst — reads the transcript and emits a verdict JSON
  harness/
    agent.py            # PlayerAgent — system prompt + per-turn LLM call
    state_view.py       # front_state → input text for the player LLM
    transcript.py       # SSE → markdown / jsonl
    review.py           # reviewer call + Verdict validation
    runner.py           # runs one session for a single agent

# Run output lands at the repo root under reports/qa/<timestamp>/ (gitignored)
```

### How it works

- `httpx.AsyncClient(transport=ASGITransport(app))` calls the FastAPI app in-process. No port, no separate process, but the HTTP surface (auth/SSE/error) still exercised end-to-end.
- The LLM is the same external server you'd use otherwise (`BASE_URL`, e.g. llama.cpp).
- Each run uses its own isolated `saves/` directory — never mixed with production saves.
- Per-session flow: `POST /session/init` → `POST /session/{id}/intro` (optional) → `(read state → agent picks the next input → POST /turn → if pending_check, auto POST /roll)` repeated.

### Run

```bash
# every agent once (default 15 turns)
.venv/bin/python agency/run_qa.py

# a specific agent
.venv/bin/python agency/run_qa.py --agent diplomat --turns 20

# a different profile
.venv/bin/python agency/run_qa.py --agent all --profile other_world
```

`.env` is auto-loaded from `backend/.env`. As long as `BASE_URL` is reachable, that's enough.

### Output

```
reports/qa/<timestamp>/
  index.md                      # cross-agent comparison table + extracted high/medium issues
  diplomat/
    transcript.md               # human-readable per-turn record
    sse.jsonl                   # raw SSE events (for replay/debugging)
    final_state.json            # the full GameState at the end
    verdict.json                # structured evaluation (consumed when fixing code)
    review.md                   # reviewer's human-readable comments
    saves/                      # per-run isolated saves (a fresh dir each run)
  explorer/...
  provocateur/...
```

`verdict.json` schema:

```json
{
  "agent": "diplomat",
  "run_id": "...",
  "verdict": "pass" | "warn" | "fail",
  "wins": ["..."],
  "issues": [
    {
      "severity": "low" | "medium" | "high",
      "category": "narrative" | "state" | "judge" | "memory" | "input" | "schema" | "기타",
      "summary": "...",
      "evidence": ["턴 N: ..."]
    }
  ],
  "questions": ["..."]
}
```

### Using the output to fix code

After a change, run `run_qa.py` once and review the high/medium issues in `index.md` plus the per-agent `verdict.json`. When a regression shows up, jump to the turn number cited in `evidence` and read that section of the transcript. If something that used to land in `wins` is gone, treat it as a regression signal.

### Limits

- Real-time guidance, not authoritative QA. The reviewer LLM's judgment is itself subject to review.
- LLM call volume is heavy (1 narrator + 1 player per turn, plus 1 reviewer at the end). Short runs and fast feedback work best.
- Non-deterministic. Identical prompts produce different transcripts. Pinning regressions precisely needs a scenario mode (an explicit input sequence), not implemented yet.

## Story — scenario seed authoring

The team that LLM-writes the seed files in the repo-root `scenarios/<name>/`. Currently single-entity-at-a-time (race / location / item / character / quest / chapter). Whole-scenario builds (prose → entire directory) are a follow-up.

### Layout

```
agency/run_story.py    # CLI (entity / scenario subcommands)
agency/story/
  agents/
    _base.md           # rules layered on top of every fragment (Korean only, JSON-only output, id pattern)
    _decompose.md      # prose → Decomposition prompt
    race.md            # per-entity domain rules (schema, required fields, references)
    location.md
    item.md
    character.md
    quest.md
    chapter.md
  harness/
    runner.py          # generic write_entity(kind, ...) — LLM + Pydantic + 5-shot self-correction + semantic checks + disk write
    scenario.py        # one prose document → full scenario build pipeline

# Per-call prompt/response logs land at the repo root under reports/story/<ts>/<kind>_writer/ (gitignored)
```

### How it works

- Imports the backend's `LLMClient` and the Pydantic models in `domain/entities.py` directly.
- `SPECS` maps each entity kind to (model · sub_dir · fragment · referenced kinds · semantic-check function).
- One cycle per call: bundle `_base.md` + `<kind>.md` + the scenario's `world.md` + existing instances of that kind + existing instances of referenced kinds as system context, call the LLM, extract JSON, validate via `<Model>.model_validate_json` + id-pattern check + entity-specific reference-integrity check (e.g. `character.race_id` actually exists in the scenario's `races/`). On failure, append the response and the error to the messages and retry — up to 5 self-correction attempts (same shape as the judge runner).
- On success, write `scenarios/<scenario>/<sub_dir>/<id>.json` with `indent=2`. If the file already exists, error out instead of overwriting.
- Every messages exchange is preserved at `reports/story/<ts>/<kind>_writer/messages.jsonl` for debugging.

### Reference integrity

The semantic check for each entity validates these ID references:

| Kind | Validated references |
|---|---|
| race | (none) |
| location | `connections[*].target_id` → other locations in the scenario (self-reference forbidden) |
| item | (none — `required: Stats` is enforced by Pydantic) |
| character | `race_id` → races, `location_id` → locations, `inventory_ids[*]` → items, `equipment.<slot>` → items |
| quest | `giver_id` → characters, `triggers[*].target_id` → varies by type (character_death→characters, location_enter→locations, item_use→items), `prerequisite_ids[*]` → quests |
| chapter | `quest_ids[*]` → quests |

### Run

Two tracks — the local LLM for automation, Claude Code when you want one careful build:

**(a) Local LLM (`run_story.py`)**

```bash
.venv/bin/python agency/run_story.py race      --scenario default --hint "달밤에 활동하는 종족"
.venv/bin/python agency/run_story.py character --scenario default --hint "은퇴한 노검사"
.venv/bin/python agency/run_story.py item      --scenario default --hint "녹슨 단검"
.venv/bin/python agency/run_story.py location  --scenario default
.venv/bin/python agency/run_story.py quest     --scenario default
.venv/bin/python agency/run_story.py chapter   --scenario default
```

Only `BASE_URL` from `backend/.env` needs to be reachable (in-process consumer).

**(b) Claude Code slash command (`/story-write`)**

```
/story-write character default 은퇴한 노검사
/story-write quest default
/story-write race default 달밤에 활동하는 종족
```

The body is `.claude/commands/story-write.md`. Claude (the model in the conversation) Reads `_base.md` + `<kind>.md` + `world.md` + existing instances directly and Writes one entity JSON to `scenarios/<scenario>/<sub_dir>/<id>.json`. No separate LLM server needed, and no `reports/` log left behind (the conversation transcript is the log).

### Whole scenario (`scenario` mode)

Given one prose document (`<prose-path>.md`), build a complete scenario directory. Pipeline:

1. **Decompose** — the `_decompose.md` prompt compresses the prose into one `Decomposition` (Pydantic): `world_md` + the 6 entity rosters (each entry has `id` + `role` + extra hints) + `start_*` triple + profile metadata. Decomposition itself runs 5-shot self-correction + consistency checks (id pattern, duplicates, cross-refs).
2. **world.md** — write the decomposition's `world_md` body to disk as markdown.
3. **race → location → item → character → quest → chapter** — at each stage, call `write_entity` for every entry in the corresponding roster. The stage order follows the reference dependencies, so each completed stage becomes context for the next.
4. **Three meta files** — `profile.json` / `start.json` / `player_template.json`. Built directly from the decomposition as dicts and JSON-dumped.

**id enforcement** — entity stages must use the ids decided during decomposition. `write_entity(force_id=...)` compares the LLM's id against `X` inside `_check_id` and raises an `EntityWriterError` on mismatch, kicking off the self-correction loop so the next attempt fixes it. `_base.md` also says "do not change a single character of the id forced via the user message".

```bash
.venv/bin/python agency/run_story.py scenario \
  --name default_cli \
  --prose path/to/prose.md
```

The Claude Code track takes the same steps via:

```
/story-scenario default_claude path/to/prose.md
```

The body is `.claude/commands/story-scenario.md`. Claude (the model in the conversation) handles decomposition and the per-stage Read/Write directly. From the same prose you can compare the two tracks' results (`scenarios/default_cli/` vs `scenarios/default_claude/`).

### Limits

- `racial_skills` is always an empty list (skill synthesis is separate).
- Chapter is currently single-mode (every quest in the decomposition's roster goes into the first chapter).
- Runtime entity injection during a game (adding a new NPC/item to a live save) belongs to the backend and isn't designed yet.
