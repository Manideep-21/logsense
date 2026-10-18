#!/usr/bin/env bash
# Create the Hive database and tables (safe to rerun; needed again after `docker compose down`).
docker exec hive /opt/hive/bin/beeline -u jdbc:hive2://localhost:10000 --silent=true \
  -f /opt/hive-scripts/create_tables.sql 2>&1 \
  | grep -vE "^SLF4J|^No such file or directory|Failed to create directory: /home/hive|^\s*$"; echo "tables ready"
