-- Password reset without a mail server.
--
-- There is no SMTP configuration in this build, so a reset link cannot be
-- emailed. Instead the server mints a single-use token, prints it to the
-- console it is already running in, and the person pastes it back. That is a
-- real reset flow with a real secret, not a fake one; it simply delivers the
-- token over a channel the operator already controls.
--
-- Only the hash is stored. A stolen database does not yield a working token,
-- for the same reason a stolen database does not yield a password.
CREATE TABLE IF NOT EXISTS password_resets(
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
