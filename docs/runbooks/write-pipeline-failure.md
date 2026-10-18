# Runbook: block write pipeline failures

**Log patterns:**
- `dfs.DataNode$DataXceiver: writeBlock blk_... received exception java.io.IOException: Could not read from stream`
- `writeBlock ... received exception java.io.EOFException` / `java.net.SocketTimeoutException` / `Connection reset by peer`
- `dfs.DataNode$BlockReceiver: Exception in receiveBlock for block blk_...`
- `dfs.DataNode$PacketResponder: PacketResponder ... Exception` or `... Interrupted.`

**Component:** DataNode write path. These lines are logged at INFO level, so counting WARN/ERROR lines misses them.

## What it means
HDFS writes a block through a *pipeline* of DataNodes (usually 3 replicas): client -> DN1 -> DN2 -> DN3.
Each DataNode receives packets (BlockReceiver) and passes acknowledgements back (PacketResponder).
If any link in the chain breaks — a node crashes, a disk stalls, the network drops, or the writer dies —
the nodes downstream see "Could not read from stream" or EOF, and the PacketResponder is interrupted.

## Why it matters
These failures are strongly linked to blocks labelled **anomalous**: the block may end up with fewer
replicas than intended, or a partial replica that has to be cleaned up later.

## What to check
1. Find windows where anomalous blocks spike, and see whether write exceptions rise at the same time.
2. Find which DataNode appears in most of the failing pipelines — it is often the broken link.
3. SocketTimeoutException points to a slow or overloaded node; Connection reset points to a crash or network drop.
4. Check that affected blocks were later re-replicated (look for replication requests from the NameNode).

## Fix
- Restart or decommission the faulty DataNode.
- For timeouts under heavy load: reduce concurrent writers, or raise the DataNode transfer thread limit and socket timeouts.
- Run `hadoop fsck /` to list under-replicated or corrupt blocks after the incident.
