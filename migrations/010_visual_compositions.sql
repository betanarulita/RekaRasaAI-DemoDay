CREATE TABLE visual_compositions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    image_id TEXT NOT NULL REFERENCES generated_images(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    image_sha256 TEXT NOT NULL,
    copy_json TEXT NOT NULL,
    svg_content BLOB NOT NULL,
    render_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    approved_at TEXT,
    approval_note TEXT,
    UNIQUE(image_id, version_id)
);
CREATE INDEX visual_compositions_task ON visual_compositions(task_id, created_at DESC);
