-- ============================================================================
-- 02_anomaly_detection.sql
-- Anomaly detection pipeline using Confluent Cloud's built-in ML functions.
--
-- ML_DETECT_ANOMALIES is a scalar function that uses ARIMA modeling to detect
-- outliers. It requires an OVER window clause for ordering.
--
-- Flow:
--   1. Window sensor readings into 10-second tumbling windows per machine/sensor
--   2. Compute average values per window
--   3. Apply ML_DETECT_ANOMALIES with OVER window ordered by time
--   4. Filter for detected anomalies and write to equipment-alerts topic
--
-- ML_DETECT_ANOMALIES returns a ROW with these fields (snake_case):
--   forecast_value, lower_bound, upper_bound, is_anomaly, anomaly_score, rmse
--
-- Reference:
--   https://docs.confluent.io/cloud/current/ai/builtin-functions/detect-anomalies.html
--   https://github.com/confluentinc/flink-ai-examples/blob/master/demos/AI%20Functions/anomaly_detection.md
-- ============================================================================

INSERT INTO `equipment-alerts`
WITH windowed_sensors AS (
    SELECT
        machine_id,
        sensor_type,
        unit,
        facility,
        window_time,
        AVG(`value`) AS avg_value
    FROM TABLE(
        TUMBLE(TABLE `sensor-readings`, DESCRIPTOR(event_time), INTERVAL '10' SECONDS)
    )
    GROUP BY machine_id, sensor_type, unit, facility, window_start, window_end, window_time
),
anomaly_results AS (
    SELECT
        machine_id,
        sensor_type,
        avg_value,
        unit,
        facility,
        window_time,
        ML_DETECT_ANOMALIES(
            avg_value,
            window_time,
            JSON_OBJECT(
                'minTrainingSize' VALUE 30,
                'p' VALUE 1,
                'q' VALUE 1,
                'd' VALUE 1
            )
        ) OVER (
            PARTITION BY machine_id, sensor_type
            ORDER BY window_time
            RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS anomaly
    FROM windowed_sensors
)
SELECT
    CAST(NULL AS BYTES) AS `key`,
    machine_id,
    sensor_type,
    avg_value       AS `value`,
    unit,
    anomaly.forecast_value AS anomaly_score,
    anomaly.is_anomaly AS is_anomaly,
    window_time     AS event_time,
    facility,
    CAST(CURRENT_TIMESTAMP AS TIMESTAMP(3)) AS detected_at
FROM anomaly_results
WHERE anomaly.is_anomaly = TRUE
  AND (avg_value > anomaly.upper_bound * 1.1 OR avg_value < anomaly.lower_bound * 0.9);
