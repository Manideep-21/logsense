#!/usr/bin/env bash
# Run one SQL query in Hive and print the result as a table.
# Usage: bash scripts/hive_query.sh "SELECT * FROM logsense.window_counts LIMIT 5"
docker exec hive /opt/hive/bin/beeline -u jdbc:hive2://localhost:10000 --silent=true \
  --outputformat=table -e "$1" 2>&1 \
  | grep -vE "^SLF4J|^No such file or directory|Failed to create directory: /home/hive"
