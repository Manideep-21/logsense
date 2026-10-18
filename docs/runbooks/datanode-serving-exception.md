# Runbook: DataNode "Got exception while serving block"

**Log pattern:** `WARN dfs.DataNode$DataXceiver: <datanode>:Got exception while serving blk_... to /<client>:`
**Component:** DataNode (DataXceiver thread). This is by far the most common WARN in the HDFS logs.

## What it means
A DataNode was sending (serving) a block to a reader — a client or another DataNode — and the transfer
broke part-way. The DataNode logs the exception and drops the connection. Usually the *reader* went away:
a map task finished early or was killed, a speculative task duplicate was cancelled, or the client timed out.

## Is it serious?
Usually not on its own. A single occurrence is noise. It matters when:
- many of these appear for the **same block** from different DataNodes (the block itself may be bad), or
- they spike together with write failures and anomalous blocks in the same time window, or
- they all come from **one DataNode** (that node's disk or network may be failing).

## What to check
1. Count WARN lines per 10-minute window and look for a sudden spike rather than a steady background rate.
2. Check whether the affected blocks are labelled anomalous.
3. Group by source DataNode IP: one noisy node points to hardware or network trouble on that node.
4. Look for slow-disk or network symptoms on that node (socket timeouts, connection resets).

## Fix
- Steady low rate: no action needed.
- One noisy DataNode: take it out of service (decommission), check disk and network, let HDFS re-replicate its blocks.
- Cluster-wide spike: look for a network event or an overloaded job that killed many readers at once.
