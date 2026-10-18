# Runbook: DataNode dead or unresponsive

## Symptoms
- The NameNode marks a DataNode dead after it stops sending heartbeats (about 10 minutes by default).
- Write pipelines that include the node fail (EOF, "Could not read from stream", connection reset).
- Readers get "Got exception while serving block" or retry on another replica.
- A wave of re-replication follows, and PendingReplicationMonitor timeouts may appear if the cluster is busy.

## Common causes
- The machine crashed or rebooted.
- The disk is full or failing, so the DataNode process stops or hangs.
- Long Java garbage-collection pauses make the DataNode miss heartbeats.
- A network switch or cable problem cuts the node (or a whole rack) off.

## What to check
1. Is the DataNode process running? Check its own log for the last messages before it went quiet.
2. Disk space and disk health (`df -h`, SMART errors in the system log).
3. Network: can the NameNode reach the node? Is a whole rack affected?
4. Under-replicated block count on the NameNode (`hadoop fsck /`).

## Fix
- Restart the DataNode once the disk or network problem is fixed.
- If the hardware is bad, decommission the node so HDFS re-replicates its blocks in a controlled way.
- For GC pauses: give the DataNode more heap or reduce load on that machine.
