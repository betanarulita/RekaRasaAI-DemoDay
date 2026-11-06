CREATE TABLE IF NOT EXISTS pending_registrations(
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    challenge_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    requested_at TEXT NOT NULL
);
