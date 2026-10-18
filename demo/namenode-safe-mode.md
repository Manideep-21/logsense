# Runbook: HDFS stuck in safe mode after a restart

## What happened
On our cluster the NameNode was restarted, and for 20 minutes nobody could write files.
Every write failed with "Cannot create file. Name node is in safe mode."

## What it means
After a restart the NameNode waits in read-only "safe mode" until enough DataNodes report their blocks.
If some DataNodes are down, it never reaches the threshold and stays read-only.

## Fix
1. Check status: `hdfs dfsadmin -safemode get`.
2. Bring the missing DataNodes back online, then wait a few minutes.
3. Only if you are sure the missing blocks are not needed: `hdfs dfsadmin -safemode leave`.

## How to stop it happening again
Restart DataNodes before the NameNode, and alert when fewer than 90% of DataNodes are alive.
