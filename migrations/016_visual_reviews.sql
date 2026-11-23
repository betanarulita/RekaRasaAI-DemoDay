CREATE TABLE visual_reviews (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    image_id TEXT NOT NULL REFERENCES generated_images(id) ON DELETE CASCADE,
    composition_id TEXT NOT NULL REFERENCES visual_compositions(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN ('Pass', 'Needs changes')),
    summary TEXT NOT NULL,
    findings_json TEXT NOT NULL,
    next_steps_json TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX visual_reviews_composition ON visual_reviews(composition_id, created_at DESC);
