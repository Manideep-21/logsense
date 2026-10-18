-- External tables over the Parquet files Spark writes to ./warehouse.
-- "External" = Hive only reads the folder; dropping the table never deletes the files.
-- Safe to run again (IF NOT EXISTS). Run with: bash scripts/hive_setup.sh

CREATE DATABASE IF NOT EXISTS logsense;

-- One row per 10-minute window of log time (2008).
CREATE EXTERNAL TABLE IF NOT EXISTS logsense.window_counts (
  window_start     TIMESTAMP,
  window_end       TIMESTAMP,
  total_lines      BIGINT,   -- log lines in the window
  warn_lines       BIGINT,   -- WARN lines in the window
  blocks           BIGINT,   -- different HDFS blocks active in the window
  anomalous_blocks BIGINT    -- of those, blocks labelled Anomaly
)
STORED AS PARQUET
LOCATION 'file:///data/warehouse/window_counts';

-- One row per 10-minute window + component + level.
CREATE EXTERNAL TABLE IF NOT EXISTS logsense.component_counts (
  window_start TIMESTAMP,
  window_end   TIMESTAMP,
  component    STRING,       -- e.g. dfs.DataNode$PacketResponder
  level        STRING,       -- INFO or WARN
  lines        BIGINT
)
STORED AS PARQUET
LOCATION 'file:///data/warehouse/component_counts';
