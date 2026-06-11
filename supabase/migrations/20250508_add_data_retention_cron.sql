-- Enable pg_cron for job scheduling
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Index for coordinate dedup performance
CREATE INDEX IF NOT EXISTS idx_device_readings_coords
  ON device_readings (latitude, longitude)
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- Function that performs all data retention steps
CREATE OR REPLACE FUNCTION perform_data_retention()
RETURNS TABLE(step TEXT, rows_affected BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_count BIGINT;
BEGIN
  -- Step 1: Remove test readings
  DELETE FROM device_readings
  WHERE source IN ('live-test-device', 'live-test-device-2', 'test', 'azure_test_001', 'docker_test');
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := '1 - test readings removed'; rows_affected := v_count;
  RETURN NEXT;

  -- Step 2: Remove exact duplicate rows (all columns identical)
  DELETE FROM device_readings
  WHERE id IN (
    SELECT id FROM (
      SELECT id, ROW_NUMBER() OVER (
        PARTITION BY source, timestamp, latitude, longitude, level, asu, rsrp, rssi, dbm, rsrq,
                     network_type, operator, cell_id, physical_cell_id, tracking_area_code,
                     altitude, country, city, rsrq_uncertainty, rsrp_uncertainty, gps_accuracy
        ORDER BY id
      ) AS rn
      FROM device_readings
    ) sub WHERE rn > 1
  );
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := '2 - exact duplicates removed'; rows_affected := v_count;
  RETURN NEXT;

  -- Step 3: Remove rows with invalid coordinates
  DELETE FROM device_readings
  WHERE latitude IS NULL OR longitude IS NULL
     OR (latitude = 0 AND longitude = 0);
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := '3 - invalid coordinates removed'; rows_affected := v_count;
  RETURN NEXT;

  -- Step 4: Keep only the most recent reading per coordinate
  DELETE FROM device_readings
  WHERE id IN (
    SELECT id FROM (
      SELECT id, ROW_NUMBER() OVER (
        PARTITION BY latitude, longitude
        ORDER BY GREATEST(
          COALESCE(timestamp, '1970-01-01'),
          COALESCE(created_at, '1970-01-01')
        ) DESC, id DESC
      ) AS rn
      FROM device_readings
      WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        AND NOT (latitude = 0 AND longitude = 0)
    ) sub WHERE rn > 1
  );
  GET DIAGNOSTICS v_count = ROW_COUNT;
  step := '4 - coordinate duplicates deduped'; rows_affected := v_count;
  RETURN NEXT;
END;
$$;

-- Revoke execution from public API roles (only pg_cron superuser should run this)
REVOKE EXECUTE ON FUNCTION perform_data_retention() FROM PUBLIC, anon, authenticated;

-- Schedule to run every Sunday at 3:00 AM
SELECT cron.schedule(
  'weekly-data-retention',
  '0 3 * * 0',
  'SELECT perform_data_retention();'
);
