-- Indexes for the lookups the application actually performs.
-- Added after the query paths stabilised; every statement is idempotent so
-- this file is safe to re-run against an existing database.

-- Audit is a product feature, not a log file: it is read on every workbench
-- view and on the audit page, newest first.
CREATE INDEX IF NOT EXISTS audit_owner_time ON audit_events(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_task_time ON audit_events(task_id, created_at DESC);

-- Session expiry sweep and the per-request session lookup.
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires ON sessions(expires);

-- "latest review for this version" runs on every approve, reject and serialize.
CREATE INDEX IF NOT EXISTS reviews_version ON review_runs(version_id, created_at DESC);
CREATE INDEX IF NOT EXISTS findings_review ON findings(review_id);

-- Workbench history and image galleries.
CREATE INDEX IF NOT EXISTS runs_task ON agent_runs(task_id, created_at);
CREATE INDEX IF NOT EXISTS images_task ON generated_images(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS approvals_version ON approvals(version_id, created_at DESC);

-- Conversation replay walks briefs, plans and messages by parent id.
CREATE INDEX IF NOT EXISTS briefs_conversation ON briefs(conversation_id);
CREATE INDEX IF NOT EXISTS plans_brief ON plans(brief_id);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
