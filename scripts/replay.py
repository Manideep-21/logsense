"""Replay HDFS log lines into Kafka, one JSON message per line.

Usage: .venv/bin/python scripts/replay.py [--file data/hdfs_subset.log]
           [--rate 5000] [--limit 0] [--topic hdfs-logs] [--bootstrap localhost:9094]

Example message:
  {"ts": "2008-11-09 20:35:32", "pid": 147, "level": "INFO",
   "component": "dfs.DataNode$DataXceiver", "content": "Receiving block ...",
   "block_ids": ["blk_8026466674001363449"]}

The original 2008 timestamps are kept; --rate only controls how fast we send.
"""
import argparse
import json
import re
import time

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

# 081109 203532 147 INFO dfs.DataNode$DataXceiver: Receiving block blk_...
LINE_RE = re.compile(r"^(\d{6}) (\d{6}) (\d+) (\w+) ([^:]+): (.*)$")
BLOCK_RE = re.compile(r"blk_-?\d+")


def parse(line):
    m = LINE_RE.match(line)
    if not m:
        return None
    date, clock, pid, level, component, content = m.groups()
    ts = f"20{date[:2]}-{date[2:4]}-{date[4:]} {clock[:2]}:{clock[2:4]}:{clock[4:]}"
    return {
        "ts": ts,
        "pid": int(pid),
        "level": level,
        "component": component,
        "content": content,
        "block_ids": BLOCK_RE.findall(content),
    }


def ensure_topic(bootstrap, topic):
    admin = AdminClient({"bootstrap.servers": bootstrap})
    if topic not in admin.list_topics(timeout=10).topics:
        admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])[topic].result()
        print(f"created topic {topic}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/hdfs_subset.log")
    ap.add_argument("--rate", type=int, default=5000, help="messages per second, 0 = no limit")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many lines, 0 = all")
    ap.add_argument("--topic", default="hdfs-logs")
    ap.add_argument("--bootstrap", default="localhost:9094")
    args = ap.parse_args()

    ensure_topic(args.bootstrap, args.topic)
    producer = Producer({"bootstrap.servers": args.bootstrap, "linger.ms": 50})

    sent = skipped = 0
    start = time.time()
    with open(args.file, encoding="utf-8") as f:
        for line in f:
            msg = parse(line.rstrip("\n"))
            if msg is None:
                skipped += 1
                continue
            key = msg["block_ids"][0] if msg["block_ids"] else None
            producer.produce(args.topic, key=key, value=json.dumps(msg))
            producer.poll(0)  # lets the client send in the background
            sent += 1

            if sent % 50000 == 0:
                print(f"sent {sent} (log time {msg['ts']})")
            if args.rate and sent % 500 == 0:
                # sleep if we're ahead of the target rate
                ahead = sent / args.rate - (time.time() - start)
                if ahead > 0:
                    time.sleep(ahead)
            if args.limit and sent >= args.limit:
                break

    producer.flush()
    print(f"done: sent {sent}, skipped {skipped} unparseable, {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
