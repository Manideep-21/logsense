# Runbook: "Redundant addStoredBlock request received"

**Log pattern:** `WARN dfs.FSNamesystem: BLOCK* NameSystem.addStoredBlock: Redundant addStoredBlock request received for blk_... on <datanode> size <n>`
**Component:** NameNode (FSNamesystem, block management).

## What it means
A DataNode reported to the NameNode that it stores a block replica, but the NameNode already had that
replica recorded for that DataNode. The second report is "redundant" and is ignored.

## Why it happens
- A DataNode re-sent its block report after a timeout or a short network hiccup.
- A DataNode restarted and sent a full block report while the NameNode still remembered it.
- Retries during a slow or failed write pipeline.

## Is it serious?
Usually harmless bookkeeping noise. Many of them at once can mean a DataNode is flapping
(repeatedly disconnecting and reconnecting), or the NameNode is too slow to answer heartbeats.

## What to check
1. Count them per DataNode; one node with many reports may be flapping.
2. Check the NameNode for long garbage-collection pauses or high load around that time.
3. Look for nearby write failures for the same blocks.

## Fix
- Flapping DataNode: check its network link and restart it if needed.
- Overloaded NameNode: give it more heap, or reduce how often DataNodes send full block reports.
