-- Notify coverage worker when new device readings arrive
CREATE OR REPLACE FUNCTION notify_new_device_reading()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_notify('new_readings', NEW.id::text);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_device_readings_notify ON device_readings;

CREATE TRIGGER trg_device_readings_notify
AFTER INSERT ON device_readings
FOR EACH ROW
EXECUTE FUNCTION notify_new_device_reading();
