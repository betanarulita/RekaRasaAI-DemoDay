-- Track failed reset-code attempts so a short numeric code cannot be brute
-- forced. A six-digit code has only a million possibilities; without a cap the
-- endpoint would be a guessing oracle.
ALTER TABLE password_resets ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
