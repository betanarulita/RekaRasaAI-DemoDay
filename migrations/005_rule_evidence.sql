-- Not every rule can cite a source for a pass.
--
-- DEMO-FACT-001 asserts something about the product ("this is made from
-- ginger"), so a Pass must point at the source that says so.
--
-- DEMO-CLAIM-001, DEMO-HALAL-001 and DEMO-TONE-001 are prohibitions: a Pass
-- means "checked, nothing prohibited is present". There is no source to cite
-- for an absence, so requiring one made those rules impossible to pass. They
-- are compensated by deterministic guards in save_review(), not by trust.
ALTER TABLE rule_registry ADD COLUMN requires_evidence INTEGER NOT NULL DEFAULT 1;

UPDATE rule_registry SET requires_evidence = 0
 WHERE id IN ('DEMO-CLAIM-001', 'DEMO-HALAL-001', 'DEMO-TONE-001');
