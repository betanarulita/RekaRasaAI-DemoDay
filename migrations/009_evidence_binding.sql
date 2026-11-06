-- Evidence binding: a verdict must be locatable, and a policy verdict must name an instrument.
--
-- Until now `findings` recorded the claim as a regex capture and nothing else:
-- no document, no offsets. 29 of 29 stored Pass/Fail rows therefore cite no
-- position and cannot be checked by anyone reading them later.
--
-- These columns are additive and nullable on purpose. The 29 historical rows
-- are NOT backfilled here: re-deriving them and marking them legacy are both
-- defensible and the choice has not been made. Leaving them NULL is the honest
-- record of what is actually known about them.
ALTER TABLE findings ADD COLUMN document_id TEXT;
ALTER TABLE findings ADD COLUMN span_start INTEGER;
ALTER TABLE findings ADD COLUMN span_end INTEGER;
ALTER TABLE findings ADD COLUMN evidence_item_id TEXT;
ALTER TABLE findings ADD COLUMN instrument_id TEXT;

-- A rule may now declare which decision function governs it and, for a policy
-- prohibition, which instrument it comes from. Both are nullable: no rule is
-- classified yet, and classifying them is a product and legal decision rather
-- than a migration. An unclassified rule is treated as evidence-governed, so
-- the enforcement below stays dormant until someone classifies.
ALTER TABLE rule_registry ADD COLUMN verdict_basis TEXT;
ALTER TABLE rule_registry ADD COLUMN instrument_id TEXT;

CREATE INDEX IF NOT EXISTS idx_findings_review ON findings(review_id);
