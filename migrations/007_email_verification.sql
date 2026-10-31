-- Email verification support.
--
-- When SMTP is configured, new accounts receive a verification email with a
-- single-use token. Until verified, the account can still sign in (the demo
-- does not gate on this), but the verification status is visible in the API
-- and can be enforced by a future gate.
CREATE TABLE IF NOT EXISTS email_verifications(
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_verifications_user ON email_verifications(user_id);
