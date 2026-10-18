#!/usr/bin/env bash
# Read back from Kafka: message count and the first few messages.
# Usage: bash scripts/check_topic.sh [topic] [how_many]
TOPIC=${1:-hdfs-logs}
N=${2:-3}

echo "== messages stored in $TOPIC =="
docker exec kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic "$TOPIC"
echo "(format is topic:partition:count)"

echo "== first $N messages =="
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic "$TOPIC" --from-beginning --max-messages "$N" --property print.key=true 2>/dev/null
