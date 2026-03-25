-- ============================================================================
-- 01_sensor_table.sql
-- Source table for ingesting raw sensor readings from Kafka.
--
-- In Confluent Cloud Flink, tables are auto-created from Kafka topics that
-- have a JSON schema registered in Schema Registry. The producer registers
-- the schema automatically on first message.
--
-- After the table is auto-created, we ALTER it to add:
--   1. A computed event_time column (parsed from the timestamp string)
--   2. A watermark for event-time windowing
--
-- Run these statements in the Flink SQL workspace after the producer has
-- started and registered the schema.
-- ============================================================================

-- Step 1: Add computed event_time column
ALTER TABLE `sensor-readings`
    ADD event_time AS TO_TIMESTAMP(`timestamp`);

-- Step 2: Set watermark for event-time processing
ALTER TABLE `sensor-readings`
    MODIFY WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND;
