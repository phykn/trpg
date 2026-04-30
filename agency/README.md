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

Works like hiring a QA tester to play the game. Each turn an LLM generates the next input, the harness hits the server API in-process via ASGI, and collects SSE events into a transcript. There is no LLM reviewer — Claude Code reads the transcripts in chat and writes the review there (the local model hallucinates turn numbers and misclassifies normal pending_check waits as desyncs, so we removed it).

### Layout

```
agency/run_qa.py        # CLI entrypoint
agency/qa/
  agents/               # 9 phased personas, one .md per agent (25 turns each)
    socialite.md        # 친교 → 의뢰·bluff → 적대전환·집착 (호감도 라이프사이클 + combat 가드)
    fighter.md          # victory → broken_off/flee → downed/death_save → non-combat flee 폴백
    shopkeeper.md       # 인벤·거래·장비 → 성장·휴식·기술 학습 → 가드 (장착 중 sell·만피 use·affinity)
    scout.md            # 6 stat 강제 순환 → 환경 prop 수색 (hidden_items / hidden_connections)
    caster.md           # skill 의미 매칭 다양화 → MP·회피 표현 평타 폴백 → 회복 사이클
    survivor.md         # rest 분기 (safe → risky → dangerous, sleep_encounter)
    questor.md          # 첫 퀘스트 완료 → 둘째 퀘스트·fail_trigger → 검증 불가 주장·chapter 경계
    provocateur.md      # judge 15종 분기 fuzz (reject·chain·tail_intent·semantic 폴백)
    mourner.md          # 친교·살해 → 시체 호명·시신 검사 혼합 → off-screen 호명 (시체 발화 회귀)
  harness/
    agent.py            # PlayerAgent — system prompt + per-turn LLM call
    state_view.py       # front_state → input text for the player LLM
    transcript.py       # SSE → markdown / jsonl
    runner.py           # runs one session for a single agent

# Run output lands at the repo root under reports/qa/<timestamp>/ (gitignored)
```

`AGENTS` in `run_qa.py` is the source of truth for membership. See [agency/CLAUDE.md](./CLAUDE.md) for the full playbook.

### How it works

- `httpx.AsyncClient(transport=ASGITransport(app))` calls the FastAPI app in-process. No port, no separate process, but the HTTP surface (auth/SSE/error) still exercised end-to-end.
- The LLM is the same external server you'd use otherwise (`BASE_URL`, e.g. llama.cpp).
- Each run uses its own isolated `saves/` directory — never mixed with production saves.
- Per-session flow: `POST /session/init` → `POST /session/{id}/intro` (optional) → `(read state → agent picks the next input → POST /turn → if pending_check, auto POST /roll)` repeated.

### Run

```bash
# every agent once (default 25 turns) against the `default` profile
.venv/bin/python agency/run_qa.py

# a specific agent
.venv/bin/python agency/run_qa.py --agent socialite --turns 25

# a different profile
.venv/bin/python agency/run_qa.py --agent all --profile <scenario_id>
```

`.env` is auto-loaded from `server/.env`. As long as `BASE_URL` is reachable, that's enough. `--profile` defaults to `default` — make sure `scenarios/default/` exists, or pass `--profile <name>` to point at another seed.

### Output

```
reports/qa/<timestamp>/
  index.md                      # per-agent turn count + error count + transcript links
  socialite/
    transcript.md               # human-readable per-turn record
    sse.jsonl                   # raw SSE events (for replay/debugging)
    final_state.json            # the full GameState at the end
    saves/                      # per-run isolated saves (a fresh dir each run)
  fighter/...
  scout/...
```

### Using the output to fix code

After a change, run `run_qa.py` and read the artifacts in chat. Per agent: one verdict (PASS / WARN / FAIL), 1–3 wins, 1–3 issues with severity + turn-numbered evidence. Then a cross-agent summary that calls out repeated patterns. The full playbook (background launch, Monitor filter, verdict grading, reviewer pitfalls) is in [agency/CLAUDE.md](./CLAUDE.md).

### Limits

- Real-time guidance, not authoritative QA. Reviews are written by Claude Code in chat — they're a summary of the artifacts, not a separate verification pass.
- LLM call volume is heavy (1 player per turn + the server's own judge / narrate / combat_narrate / encounter_summon / skill_recommend calls). Short runs and fast feedback work best.
- Non-deterministic. Identical prompts produce different transcripts. Pinning regressions precisely needs a scenario mode (an explicit input sequence), not implemented yet.

## Story — scenario seed authoring

The team that LLM-writes the seed files in the repo-root `scenarios/<name>/`. Two CLI subcommands share one set of prompt rules — `run_story.py <kind>` for one entity at a time, and `run_story.py scenario` for a prose document → full directory build.

### Layout

```
agency/run_story.py    # CLI (entity / scenario subcommands)
agency/story/
  agents/
    _base.md             # rules layered on top of every fragment (Korean only, JSON-only output, id pattern)
    _decompose_setup.md  # prose → setup phase (world / races / skills / locations / start_location)
    _decompose_cast.md   # setup + prose → cast phase (characters / items / start_subject)
    _decompose_arc.md    # setup + cast + prose → arc phase (quests / chapters / start_quest)
    _critic.md           # post-write critic — coherence with world.md / role / other entities
    race.md            # per-entity domain rules (schema, required fields, references)
    location.md
    item.md
    character.md
    skill.md
    quest.md
    chapter.md
  harness/
    runner.py          # generic write_entity(kind, ...) — LLM + Pydantic + 5-shot self-correction + invariants + cross-ref + disk write + optional one critic pass
    critic.py          # critic LLM call + CriticOutput parsing (advisory; advisory failure → one writer retry)
    scenario.py        # one prose document → full scenario build pipeline

# Per-call prompt/response logs land at the repo root under reports/story/<ts>/<kind>_writer/ (gitignored)
```

### How it works

- Imports the server's `LLMClient` and the Pydantic models in `domain/entities.py` directly.
- `SPECS` maps each entity kind (race / skill / location / item / character / quest / chapter) to (model · sub_dir · fragment · referenced kinds · cross-ref check function).
- One cycle per call: bundle `_base.md` + `<kind>.md` + the scenario's `world.md` + existing instances of that kind + existing instances of referenced kinds as system context, call the LLM, extract JSON, validate via `<Model>.model_validate_json` + id-pattern check + entity-specific cross-ref check (e.g. `character.race_id` actually exists in the scenario's `races/`) + entity-level invariants from `server/src/engines/invariants.py` (stat pair-trade, HP/MP formula, slot-effect matching, etc.). On failure, append the response and the error to the messages and retry — up to 5 self-correction attempts (same shape as the judge runner).
- After invariants pass, the optional critic (`agents/_critic.md`) runs once with `think=False` for a coherence read (role / tone / world.md fit). If the critic returns `ok=false`, the writer retries once with the feedback. Critic is advisory — if the retry result fails invariants, the original is kept.
- On success, write `scenarios/<scenario>/<sub_dir>/<id>.json` with `indent=2`. If the file already exists, error out instead of overwriting.
- Every messages exchange is preserved at `reports/story/<ts>/<kind>_writer/messages.jsonl` for debugging.

### Reference integrity

The cross-ref check for each entity validates these ID references against other manifests in the same scenario:

| Kind | Validated references |
|---|---|
| race | `racial_skill_ids[*]` → skills |
| skill | (none — schema-only validation) |
| location | `connections[*].target_id` → other locations in the scenario (self-reference forbidden), `item_ids[*]` and `hidden_items[*]` → items |
| item | (none — `required: Stats` and effect shapes are enforced by Pydantic) |
| character | `race_id` → races, `location_id` → locations, `racial_skill_ids[*]` and `learned_skill_ids[*]` → skills (other invariants — pair-trade, HP/MP, slot-effect matching, carry weight — come from `server.engines.invariants.check_seed_character`) |
| quest | `giver_id` → characters, `triggers[*]` and `fail_triggers[*]` `.target_id` → varies by type (character_death→characters, location_enter→locations, item_use→items), `prerequisite_ids[*]` → quests |
| chapter | `quest_ids[*]` → quests, `prerequisite_ids[*]` → other chapters (DAG, no cycles) |

### Run

```bash
.venv/bin/python agency/run_story.py race      --scenario <name> --hint "달밤에 활동하는 종족"
.venv/bin/python agency/run_story.py skill     --scenario <name> --hint "그림자 보행"
.venv/bin/python agency/run_story.py character --scenario <name> --hint "은퇴한 노검사"
.venv/bin/python agency/run_story.py item      --scenario <name> --hint "녹슨 단검"
.venv/bin/python agency/run_story.py location  --scenario <name>
.venv/bin/python agency/run_story.py quest     --scenario <name>
.venv/bin/python agency/run_story.py chapter   --scenario <name>
```

Only `BASE_URL` from `server/.env` needs to be reachable (in-process consumer).

### Whole scenario (`scenario` mode)

Given one prose document (`<prose-path>.md`), build a complete scenario directory. Pipeline:

1. **Decompose (3 sequential phases)** — single decompose was splitting the LLM's attention across too many decisions and hitting the server ctx ceiling on retries. So it runs three smaller calls, each with its own fragment, Pydantic model, and self-correction loop:
   - **Phase A (setup)** — `_decompose_setup.md` → `DecomSetup` (world / profile / races / skills / locations / start_location_id). `_check_setup` validates the location graph, BFS reachability, and racial-skill pool.
   - **Phase B (cast)** — `_decompose_cast.md` (system context: phase A JSON) → `DecomCast` (characters / items / start_subject_id). `_check_cast` validates cross-refs to phase A, item ownership, and the humanoid-armor / enemy-weapon presence rule.
   - **Phase C (arc)** — `_decompose_arc.md` (system context: phase A + B JSON) → `DecomArc` (quests / chapters / start_quest_id). `_check_arc` validates quest target/giver rules, prereq DAGs (quests + chapters, no cycles), chapter quest partition, and the opening-chapter rules.
   - The three phases compose into the final `Decomposition`; `_check_decomp` runs all three checks again as a paranoia step.
2. **world.md** — write the decomposition's `world_md` body to disk as markdown.
3. **race → item → location → character → quest → chapter** — at each stage, call `write_entity` for every entry in the corresponding roster. The stage order follows the reference dependencies, so each completed stage becomes context for the next. Item-on-character / item-on-location ownership and per-character `is_enemy` consistency (combat_behavior + xp_reward) are enforced through hint clauses + an `extra_check`. Each step optionally runs the critic (advisory).
4. **Meta files** — `profile.json` / `start.json` / `player_template.json` (with `for_player_template` items folded into `inventory_ids`).
5. **Final invariant sweep** — `engines/invariants.check_scenario` over the assembled directory; any violation aborts the build.

**id enforcement** — entity stages must use the ids decided during decomposition. `write_entity(force_id=...)` compares the LLM's id against `X` inside `_check_id` and raises an `EntityWriterError` on mismatch, kicking off the self-correction loop so the next attempt fixes it. `_base.md` also says "do not change a single character of the id forced via the user message".

```bash
.venv/bin/python agency/run_story.py scenario \
  --name <name> \
  --prose path/to/prose.md
```

### Limits

- Runtime entity injection during a game (adding a new NPC/item to a live save) belongs to the server and isn't designed yet.
