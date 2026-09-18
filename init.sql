-- Azure SQL Database / SQL Server only. All measurement times are UTC.
-- Run via: docker compose run --rm --no-deps api python -m app.init_db
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.sensors', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sensors (
        sensor_id nvarchar(64) NOT NULL PRIMARY KEY,
        sensor_type nvarchar(128) NOT NULL,
        location nvarchar(256) NULL,
        unit nvarchar(32) NOT NULL
    );
END;

IF OBJECT_ID(N'dbo.measurements', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.measurements (
        measurement_id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        time datetime2(6) NOT NULL,
        sensor_id nvarchar(64) NOT NULL REFERENCES dbo.sensors(sensor_id),
        value float NOT NULL,
        quality nvarchar(32) NOT NULL DEFAULT N'GOOD'
    );
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.measurements') AND name = N'IX_measurements_sensor_time')
    CREATE INDEX IX_measurements_sensor_time
    ON dbo.measurements(sensor_id, time DESC, measurement_id DESC)
    INCLUDE (value, quality);

INSERT INTO dbo.sensors(sensor_id, sensor_type, location, unit)
SELECT seed.sensor_id, seed.sensor_type, seed.location, seed.unit
FROM (VALUES
    (N'ACC_01', N'Accelerometer', N'Deck midspan', N'm/s2'),
    (N'SG_01', N'Strain gauge', N'Girder G1', N'microstrain'),
    (N'TEMP_01', N'Temperature', N'Deck surface', N'C'),
    (N'DISP_01', N'Displacement', N'Abutment', N'mm')
) AS seed(sensor_id, sensor_type, location, unit)
WHERE NOT EXISTS (SELECT 1 FROM dbo.sensors s WHERE s.sensor_id = seed.sensor_id);

DECLARE @i int = 1;
WHILE @i <= 200
BEGIN
    DECLARE @id nvarchar(64) = N'TEST_' + RIGHT(N'000' + CAST(@i AS nvarchar(3)), 3);
    IF NOT EXISTS (SELECT 1 FROM dbo.sensors WHERE sensor_id = @id)
        INSERT INTO dbo.sensors(sensor_id, sensor_type, location, unit)
        VALUES (@id, N'Test sensor', N'Test only', N'unit');
    SET @i += 1;
END;
