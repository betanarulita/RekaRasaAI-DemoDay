CREATE TABLE IF NOT EXISTS archived_assets (
 asset_id TEXT PRIMARY KEY REFERENCES project_assets(id) ON DELETE CASCADE,
 archived_at TEXT NOT NULL
);
