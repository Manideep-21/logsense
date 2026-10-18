# Runbook: "Unexpected error trying to delete block ... BlockInfo not found in volumeMap"

**Log pattern:** `WARN dfs.FSDataset: Unexpected error trying to delete block blk_.... BlockInfo not found in volumeMap.`
**Component:** DataNode storage layer (FSDataset).

## What it means
The NameNode told a DataNode to delete a block replica (for example after a file was deleted, or because
the block had extra replicas), but the DataNode has no record of that block in its volume map.
The replica is already gone, was never fully written, or was written to a different node.

## Why it happens
- A block write failed part-way, so the replica was never finalized on this DataNode, but the NameNode
  still scheduled its deletion.
- The same delete command was sent twice (e.g. after a NameNode retry).
- The DataNode restarted and lost track of a temporary (unfinished) replica.

## Is it serious?
On its own it is harmless — there is nothing left to delete. But it is a common **after-effect of a failed
write**, so a burst of these often follows a burst of write pipeline failures, and the blocks involved are
frequently labelled anomalous.

## What to check
1. See whether the same blocks had write exceptions (`writeBlock ... received exception`) shortly before.
2. Check whether the deletes concentrate on one DataNode.
3. Run `hadoop fsck` on the affected paths to confirm the files still have enough healthy replicas.

## Fix
No direct fix needed. Investigate the earlier write failure that caused it (see the write pipeline runbook).
