# LogSense — Demo Guide

## Before the demo (10 minutes early)

1. Start **Docker Desktop** on Windows and wait for "Engine running".
2. In WSL:
   ```bash
   cd ~/logsense
   docker compose up -d
   docker compose ps          # wait until all 4 say (healthy) — Hive takes ~1-2 min
   bash scripts/hive_setup.sh # safe to rerun; needed if Hive was recreated
   .venv/bin/streamlit run streamlit_app.py
   ```
3. Open http://localhost:8501. The sidebar should show **Qdrant: 276 documents** and **Groq key found**.
4. Ask one question once as a warm-up, so the embedding model is already loaded when you present.
5. Keep a second WSL terminal open for the live Kafka/Hive commands.

---

## The flow in one picture

```
 HDFS log file (2008)                                   danluu post-mortems + HDFS runbooks
        │                                                              │
        ▼                                                              ▼
 replay.py ──► KAFKA topic "hdfs-logs"                    index_docs.py (sentence-transformers)
               (396,692 JSON messages)                                 │
        │                                                              ▼
        ▼                                                     QDRANT (276 vectors)
 SPARK Structured Streaming                                            │
  - 10-minute windows on log time                                      │
  - joins anomaly labels per block                                     │
        │ writes Parquet files to ./warehouse                          │
        ▼                                                              │
 HIVE external tables                                                  │
  window_counts, component_counts                                      │
        │                                                              │
        └──────────────►  AGENT (Groq LLM picks a tool)  ◄─────────────┘
                          query_hive (SELECT-only SQL)  /  search_docs
                                      │
                                      ▼
                          STREAMLIT: answer + the SQL / documents used
```

---

## Script to read

### 1. Introduction (≈30 s)
> "My project is **LogSense**: an assistant that answers plain-English questions about system failures.
> Some questions are about **numbers**, like 'how many failures in the last hour?'. Those need exact
> data, so they go to **SQL over Hive**. Other questions are about **meaning**, like 'what does this error
> mean and how do I fix it?'. Those go to a **vector search** over incident write-ups. An **LLM agent**
> decides which one to use for each question, or both."

### 2. The data (≈30 s)
> "I use the **HDFS_v1** dataset from Loghub on Zenodo. It is real logs from a Hadoop file system cluster,
> recorded in November 2008. The full file is 11 million lines and 1.5 GB. To keep memory low on my laptop,
> I kept every line for about 1 in 28 blocks. That gives **396,692 lines** and **20,434 blocks**, of
> which **614 are labelled anomalous**.
> Labels are given per block, not per line, so I count *anomalous blocks per time window*.
> I keep the original 2008 timestamps, so 'last hour' means the last hour of the logs."

### 3. Kafka: ingestion (≈45 s)
> "Step one is **Kafka**, the message queue. My replay script reads the log file line by line, parses
> each line into JSON (time, level, component, message, block IDs) and sends it to the topic `hdfs-logs`.
> This simulates a live system streaming its logs."

**Show** (terminal):
```bash
bash scripts/check_topic.sh hdfs-logs 2
```
> "Kafka holds 396,692 messages. Here are the first two: real JSON with the 2008 timestamp."

### 4. Spark Structured Streaming: processing (≈60 s)
> "Step two is **Spark Structured Streaming**. It reads from Kafka as a stream and groups events into
> **10-minute windows** using the *log time*, not the current time. A watermark tells Spark when a window
> is complete. For each window it counts total lines, WARN lines, distinct blocks, and anomalous blocks.
> To get anomalous blocks, it joins each block with its anomaly label.
> Spark writes the results as **Parquet files** into a shared folder."

**Show** (optional, the code): `jobs/stream_counts.py`, the `window_counts` function.
**Show** (terminal): `ls warehouse/window_counts`
> "These Parquet files are Spark's output. A checkpoint remembers how far Spark has read, so a rerun only
> processes new messages."

### 5. Hive: the SQL layer (≈45 s)
> "Step three is **Hive**. I created **external tables** that point at that same folder. Hive does not copy
> the data, it just reads Spark's files. Now anyone can query the stream results with SQL."

**Show** (terminal):
```bash
bash scripts/hive_query.sh "SELECT window_start, total_lines, warn_lines, blocks, anomalous_blocks FROM logsense.window_counts ORDER BY anomalous_blocks DESC LIMIT 5"
```
> "The worst window was **10th Nov 2008, 10:30 to 10:40**, with **103 anomalous blocks**."

### 6. Qdrant: semantic search (≈45 s)
> "For meaning questions I built a small knowledge base: **240 real outage post-mortems** from the
> well-known danluu/post-mortems list, plus **7 HDFS runbooks** I wrote, split into 36 sections.
> Each text is turned into a 384-number vector with a **sentence-transformers** model that runs locally,
> and stored in **Qdrant**. Searching compares meaning, not exact words."

**Show** (Streamlit → **📄 Search docs** tab): search `a bad config change took everything down`
> "None of my words have to match exactly. It finds the Facebook and Google outages caused by bad configs."

### 7. The agent: the main part (≈2 min)
> "Now the main part. The agent uses an LLM on **Groq**. I give it two tools: `query_hive` and
> `search_docs`, and describe my table schema. For each question, the LLM decides which tool to call,
> I run the tool, and it writes the answer from the real results. It never invents numbers."

**Show** (Streamlit → **💬 Ask** tab). Click the examples one at a time and open *"How I got this"*:

1. **"How many anomalous blocks were there in the last hour?"** → **SQL**
   > "It wrote SQL itself. 'Last hour' is the last hour of the *log data*. Here's the exact query and the result."
2. **"What does 'Could not read from stream' mean and how do I fix it?"** → **documents**
   > "This is a meaning question, so it searched the runbooks instead. You can see which documents it used."
3. **"When was the worst spike of anomalous blocks, and what usually causes that?"** → **both**
   > "This question needs both. It first ran SQL to find the spike, 10:30 on 10th Nov, then searched the
   > runbooks for the causes, and combined the two."

### 8. Safety (≈30 s)
> "Because the LLM writes SQL, I added a **safety check**. Only a single SELECT on my two tables is allowed.
> Anything like DROP, INSERT or multiple statements is refused before it reaches Hive."

**Show** (Streamlit → **🗄️ SQL** tab): run `DROP TABLE window_counts` → *"Refused by the safety check"*.

### 9. Closing (≈20 s)
> "To summarise: **Kafka** carries the log stream, **Spark Structured Streaming** turns it into windowed
> counts, **Hive** makes those counts queryable with SQL, **Qdrant** handles meaning-based search, and an
> **LLM agent** chooses the right tool and shows its working. Everything runs on my laptop in Docker, within
> 11 GB of RAM. Thank you, happy to take questions."

---

## Likely questions — short answers

- **Why not just ask the LLM directly?** It would guess the numbers. The agent makes it look up real data and shows the SQL.
- **Why both SQL and vectors?** SQL gives exact counts but can't understand meaning. Vector search understands meaning but can't count.
- **Why Kafka in between?** It decouples the producer from processing. Spark can restart and continue from where it left off, and more consumers can be added.
- **Why 10-minute windows / watermark?** Windows turn a stream into time buckets. The watermark tells Spark when a window is finished, so it is written once.
- **Why no ERROR lines?** This dataset only has INFO and WARN, so I use the anomaly labels as "failures".
- **Hive lines (388,742) vs Kafka (396,692)?** The last window is still "open" under the watermark, because no later data arrives to close it. That's normal for append mode.
- **Why are the raw logs not in Qdrant?** Raw log lines are repetitive and have little meaning. Numbers about them belong in SQL.

## If something breaks live

- Hive not healthy: `docker compose restart hive`, wait about 1 minute, then `bash scripts/hive_setup.sh`.
- Hive query errors with "table not found": `bash scripts/hive_setup.sh`.
- Groq error or rate limit: wait a few seconds and ask again. The **SQL** and **Search docs** tabs still work without Groq.
