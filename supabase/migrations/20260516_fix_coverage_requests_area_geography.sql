-- The area column was created as varchar because geoalchemy2 was not installed.
-- This migration converts it to the proper PostGIS geography(POLYGON, 4326) type.

-- Step 1: Add a temporary geography column
ALTER TABLE coverage_requests ADD COLUMN area_geo geography(POLYGON, 4326);

-- Step 2: Convert existing JSON string data to proper geography
UPDATE coverage_requests
SET area_geo = ST_GeomFromGeoJSON(TRIM(BOTH FROM area))::geography(POLYGON, 4326)
WHERE area IS NOT NULL AND TRIM(BOTH FROM area) != '';

-- Step 3: Fix null defaults on existing row
UPDATE coverage_requests
SET status = COALESCE(status, 'OPEN'),
    current_density_score = COALESCE(current_density_score, 0)
WHERE id = 1;

-- Step 4: Drop the old varchar column
ALTER TABLE coverage_requests DROP COLUMN area;

-- Step 5: Rename the geography column to area
ALTER TABLE coverage_requests RENAME COLUMN area_geo TO area;

-- Step 6: Make the column NOT NULL (now that data is migrated)
ALTER TABLE coverage_requests ALTER COLUMN area SET NOT NULL;
