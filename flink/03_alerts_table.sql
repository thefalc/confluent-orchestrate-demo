-- ============================================================================
-- 03_alerts_table.sql
-- Sink table for writing detected equipment anomalies to Kafka.
--
-- This table must be explicitly created since it doesn't exist until the
-- anomaly detection pipeline starts writing to it. Uses json-registry format
-- to auto-register the schema in Schema Registry.
-- ============================================================================

CREATE TABLE `equipment-alerts` (
    machine_id    STRING,
    sensor_type   STRING,
    `value`       DOUBLE,
    unit          STRING,
    anomaly_score DOUBLE,
    is_anomaly    BOOLEAN,
    event_time    TIMESTAMP(3),
    facility      STRING,
    detected_at   TIMESTAMP(3)
) WITH (
    'value.format' = 'json-registry'
);
