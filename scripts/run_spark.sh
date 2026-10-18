#!/usr/bin/env bash
# Run the Spark job inside the spark container.
# Usage: bash scripts/run_spark.sh [--sink console|files] [--follow]
docker exec spark /opt/spark/bin/spark-submit \
  --master "local[2]" \
  --driver-memory 1g \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.6 \
  /opt/jobs/stream_counts.py "$@"
