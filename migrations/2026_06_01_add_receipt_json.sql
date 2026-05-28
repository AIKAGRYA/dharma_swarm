-- Runtime Truth Spine: add receipt_json column to delegation_runs.
-- This stores the serialized EvidenceReceipt for each dispatch attempt.
-- See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §9.
ALTER TABLE delegation_runs ADD COLUMN receipt_json TEXT;
