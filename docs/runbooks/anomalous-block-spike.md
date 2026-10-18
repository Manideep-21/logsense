# Runbook: investigating a spike in anomalous blocks

## What "anomalous block" means here
In the HDFS_v1 dataset every block ID has a label, Normal or Anomaly, assigned by experts who looked at
the whole life of the block (allocation, write pipeline, replication, deletion). A block is anomalous when
its life went wrong — usually a failed write, a missing replica, or an unexpected deletion — even if no
single line was logged at WARN or ERROR level. That is why we count anomalous **blocks** per time window,
not error lines.

## When to worry
- The number of anomalous blocks in a window is much higher than the usual background level.
- The *share* of anomalous blocks (anomalous_blocks / blocks) jumps, not just the raw count — a busy
  window naturally has more blocks of every kind.

## How to investigate
1. Find the worst windows: sort the 10-minute windows by anomalous_blocks (or by the anomalous share).
2. Look at what else rose in those windows: WARN lines, and which components logged them.
3. Read the log lines for a few anomalous blocks from that window and match them to a runbook:
   - write exceptions / EOF / "Could not read from stream" -> write pipeline failure runbook
   - "BlockInfo not found in volumeMap" -> block delete runbook
   - "PendingReplicationMonitor timed out" -> replication runbook
4. Check whether one DataNode IP appears in most of the anomalous blocks.

## Typical root causes
- A DataNode crash or network partition breaking many write pipelines at once.
- A large job overloading DataNodes, causing timeouts.
- Disk failure on one node.
