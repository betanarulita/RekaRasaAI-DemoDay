CREATE TABLE IF NOT EXISTS archived_sources (
 source_id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
 archived_at TEXT NOT NULL
);
