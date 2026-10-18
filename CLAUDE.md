# LogSense — Big Data mini project
I'm a beginner. Explain things simply and work one stage at a time. Don't start a new stage until I confirm the current one works.

Goal: an assistant that answers plain-English questions about system failures. Number questions go to SQL over Hive; meaning questions go to vector search; an LLM agent picks which to use.

Required tools (all three genuinely used): Kafka, Spark Structured Streaming, Hive.

Environment: Windows laptop, WSL2 Ubuntu 24.04, Docker Desktop, WSL given 11GB RAM. Keep memory use low.

Decisions:
- Official apache/kafka (KRaft, no Zookeeper), apache/spark (local mode, single container), apache/hive images. No Bitnami images.
- Qdrant container as the vector store.
- Embeddings: sentence-transformers locally (Groq does not offer embeddings). Groq only for the LLM.
- Logs: HDFS_v1 full dataset from Zenodo (the Loghub GitHub repo only has a 2k-line sample); use a subset of ~300k–500k lines. Anomaly labels are per block ID, so count anomalous blocks per window, not just ERROR lines.
- Keep original 2008 log timestamps; "last hour" means last hour of log time.
- Spark writes results as files to a shared folder; Hive reads them via external tables.
- Documents: entries from the danluu/post-mortems README, plus a few hand-written HDFS runbook notes. No raw log lines in the vector store.

Stages:
1. Docker Compose: Kafka, Spark, Hive, Qdrant all healthy
2. Replay script → Kafka, verified by reading back
3. Spark reads Kafka, prints windowed counts to console
4. Counts written to Hive, queryable with SQL
5. Documents embedded into Qdrant, semantic search working
6. Agent with tool routing (SELECT-only SQL)
7. Streamlit interface showing the answer plus the SQL or documents used
