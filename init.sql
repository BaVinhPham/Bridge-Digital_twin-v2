CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensors (
  sensor_id TEXT PRIMARY KEY,
  sensor_type TEXT NOT NULL,
  location TEXT,
  unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
  time TIMESTAMPTZ NOT NULL,
  sensor_id TEXT NOT NULL REFERENCES sensors(sensor_id),
  value DOUBLE PRECISION NOT NULL,
  quality TEXT DEFAULT 'GOOD'
);

SELECT create_hypertable('measurements', 'time', if_not_exists => TRUE);

INSERT INTO sensors(sensor_id, sensor_type, location, unit) VALUES
('ACC_01','Accelerometer','Deck midspan','m/s2'),
('SG_01','Strain gauge','Girder G1','microstrain'),
('TEMP_01','Temperature','Deck surface','C'),
('DISP_01','Displacement','Abutment','mm')
ON CONFLICT (sensor_id) DO NOTHING;

-- ============================================================
-- 200 TEST SENSORS
-- ============================================================
INSERT INTO sensors (sensor_id, sensor_type, location, unit)
SELECT
    'TEST_' || LPAD(i::text, 3, '0'),
    'Test sensor',
    'Test only',
    'unit'
FROM generate_series(1, 200) AS i
ON CONFLICT (sensor_id) DO NOTHING;
