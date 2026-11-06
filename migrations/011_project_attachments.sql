CREATE TABLE IF NOT EXISTS project_assets (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 media_type TEXT NOT NULL,
 content BLOB NOT NULL,
 sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(project_id, sha256)
);
CREATE INDEX IF NOT EXISTS project_assets_project ON project_assets(project_id);
