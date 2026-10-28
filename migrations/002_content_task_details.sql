ALTER TABLE tasks ADD COLUMN title TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN platform TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN angle TEXT NOT NULL DEFAULT '';
ALTER TABLE tasks ADD COLUMN goal TEXT NOT NULL DEFAULT '';

UPDATE tasks
SET title = format,
    platform = CASE
        WHEN format IN ('Social video script', 'TikTok short-video script') THEN 'TikTok'
        WHEN format = 'Marketplace description' THEN 'Marketplace'
        ELSE ''
    END;
