-- Fly Swat Rampage global leaderboard (Cloudflare D1 / SQLite)
-- One best row per (level, player, board), board = revived 0/1.
CREATE TABLE IF NOT EXISTS scores (
  level       INTEGER NOT NULL,
  player_id   TEXT    NOT NULL,
  name        TEXT    NOT NULL,
  value       INTEGER NOT NULL,
  time_ms     INTEGER NOT NULL,
  misses      INTEGER NOT NULL DEFAULT 0,
  revived     INTEGER NOT NULL DEFAULT 0,
  updated_at  INTEGER NOT NULL,
  PRIMARY KEY (level, player_id, revived)
);

CREATE INDEX IF NOT EXISTS idx_scores_value
  ON scores(level, revived, value DESC, time_ms ASC);
CREATE INDEX IF NOT EXISTS idx_scores_time
  ON scores(level, revived, time_ms ASC, misses ASC);

-- Sliding-window submission limit (20 / minute / player).
CREATE TABLE IF NOT EXISTS rate (
  player_id TEXT NOT NULL,
  ts        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate ON rate(player_id, ts);
