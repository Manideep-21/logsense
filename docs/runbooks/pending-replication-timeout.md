# Runbook: "PendingReplicationMonitor timed out block" / under-replicated blocks

**Log pattern:** `WARN dfs.PendingReplicationBlocks$PendingReplicationMonitor: PendingReplicationMonitor timed out block blk_...`
**Component:** NameNode replication monitor.

## What it means
When a block has fewer replicas than its target (usually 3), the NameNode asks a DataNode to copy it to
another DataNode and puts the block on a "pending replication" list. If no DataNode confirms the new
replica in time, the request times out and the block goes back on the under-replicated queue to be retried.

## Why it happens
- The source or target DataNode died or is overloaded.
- The network between racks is saturated (e.g. many blocks re-replicating after a node failure).
- The source replica is corrupt, so the copy keeps failing.

## Why it matters
Under-replicated blocks are at risk: if the remaining replicas are lost too, the data is gone.
Repeated timeouts for the same block are a sign that something is stuck.

## What to check
1. Run `hadoop fsck / -blocks -locations` and look for under-replicated or missing blocks.
2. Check whether a DataNode recently went dead (stopped sending heartbeats).
3. Check whether the same block times out repeatedly.

## Fix
- Bring the dead DataNode back, or let re-replication finish.
- If re-replication is overloading the network, limit it (fewer concurrent replication streams per node).
- If a replica is corrupt, delete it so HDFS copies from a healthy replica.
