ALTER TABLE coverage_requests
ADD COLUMN created_by_display VARCHAR(255) NULL;

-- backfill existing rows with a fallback (first char of UUID for privacy)
UPDATE coverage_requests
SET created_by_display = LEFT(created_by, 8)
WHERE created_by_display IS NULL;
