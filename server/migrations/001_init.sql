-- 001_init.sql — initial schema for SupabaseSaveRepo (Phase 2).
--
-- Five tables, all keyed on game_id. `entities` mirrors the per-kind JSON
-- file tree under `saves/games/<game_id>/<kind>/<id>.json`; the three
-- *_entries tables mirror the matching .jsonl files.
--
-- The server uses the service-role key, so RLS is enabled with no policies
-- (default-deny) — anon/auth keys cannot reach these tables. If we later
-- expose any of this to client-side keys, add explicit policies then.

CREATE TABLE IF NOT EXISTS games (
    game_id    text PRIMARY KEY,
    meta       jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entities (
    game_id    text NOT NULL,
    kind       text NOT NULL,
    id         text NOT NULL,
    data       jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, kind, id),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS entities_game_kind_idx
    ON entities (game_id, kind);

CREATE TABLE IF NOT EXISTS log_entries (
    game_id text NOT NULL,
    log_id  int  NOT NULL,
    entry   jsonb NOT NULL,
    PRIMARY KEY (game_id, log_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history_entries (
    game_id text NOT NULL,
    seq     bigserial,
    entry   jsonb NOT NULL,
    PRIMARY KEY (game_id, seq),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS history_entries_tail_idx
    ON history_entries (game_id, seq DESC);

CREATE TABLE IF NOT EXISTS dialogue_entries (
    game_id text NOT NULL,
    seq     bigserial,
    entry   jsonb NOT NULL,
    PRIMARY KEY (game_id, seq),
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS dialogue_entries_tail_idx
    ON dialogue_entries (game_id, seq DESC);

ALTER TABLE games            ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities         ENABLE ROW LEVEL SECURITY;
ALTER TABLE log_entries      ENABLE ROW LEVEL SECURITY;
ALTER TABLE history_entries  ENABLE ROW LEVEL SECURITY;
ALTER TABLE dialogue_entries ENABLE ROW LEVEL SECURITY;
