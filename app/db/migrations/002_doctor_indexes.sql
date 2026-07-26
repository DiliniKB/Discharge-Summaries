-- Backs the doctor filter in the Advanced Search dialog (created_by OR
-- last_edited_by) — a plain equality/OR comparison an index actually
-- helps, unlike the date(...)-wrapped range filters in the same query.
CREATE INDEX idx_summaries_created_by ON summaries(created_by);
CREATE INDEX idx_summaries_last_edited_by ON summaries(last_edited_by);
