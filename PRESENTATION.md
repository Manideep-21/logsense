# LogSense — Full Presentation (Part A: the files, Part B: the working demo)

Open the `logsense` folder in **VS Code** (in the Ubuntu terminal: `cd ~/logsense && code .`).
Go through the files **in the order below**. It follows the path the data takes, so the story builds up.
For each file: **open it → point at the line → read the SAY text**.

---

# PART A — Explaining the files

## Opening line
> "My project is LogSense, an assistant that answers plain-English questions about system failures.
> Number questions go to SQL on Hive, meaning questions go to a vector search, and an AI agent picks which
> one to use. I'll walk through the files in the same order the data flows: setup, then data, Kafka, Spark,
> Hive, documents, AI agent, and finally the website."

---

## 1. Setup files

### `CLAUDE.md`
> "This is my project plan: the goal, the tools I must use (Kafka, Spark Structured Streaming and Hive),
> my decisions, and the 7 stages I built one by one."

### `docker-compose.yml`
Point at **line 8 (kafka)**, **39 (spark)**, **59 (hive)**, **85 (qdrant)**.
> "This file starts all four services as Docker containers with one command, `docker compose up -d`.
> **Kafka** is the message queue. **Spark** processes the stream. **Hive** gives SQL access. **Qdrant** is
> the vector database. I set memory limits on each one (`mem_limit`), because my laptop only gives 11 GB
> to Linux.
> One important detail: Spark and Hive both mount the same folder, `./warehouse`. Spark writes results
> there and Hive reads them from there. That shared folder connects the two."

### `spark/Dockerfile`
> "A tiny file. It takes the official Spark image and adds a user with the same ID as mine, so the files
> Spark writes belong to me."

### `requirements.txt`
> "The Python libraries: the Kafka client, sentence-transformers for embeddings, the Qdrant client, PyHive to
> talk to Hive, Groq for the AI model, and Streamlit for the website."

### `.env.example` (do NOT open `.env`, it has your secret key)
> "The template for my Groq API key. The real key is kept in `.env`, which is private."

---

## 2. The data — `data/` folder

### `data/hdfs_subset.log`
Show the first lines.
> "These are real logs from a Hadoop file system (HDFS) cluster, recorded in November 2008, from the Loghub
> dataset. Each line has a date, time, process ID, level (INFO or WARN), the component, and a message.
> Most messages mention a **block ID**. HDFS stores files in pieces called blocks."

### `data/anomaly_label.csv`
> "Researchers labelled every block as **Normal** or **Anomaly**. An anomalous block is a failure.
> This is how I measure failures."

### `scripts/make_subset.py`
Point at **line 15, `keep()`**.
> "The full dataset is 11 million lines (1.5 GB), too big for my laptop. This script keeps every line for
> about 1 in 28 blocks. That gives **396,692 lines** and **20,434 blocks**, **614 of them anomalous**. Keeping
> whole blocks means the labels still make sense. Using a hash gives the same subset every time."

(Mention: `data/download` and `data/extract` hold the original big download. `.venv` holds the Python
libraries and `.ivy2` holds Spark's Kafka connector. These are support folders, not my code.)

---

## 3. Kafka — getting the logs in

### `scripts/replay.py`
Point at **line 22 (`LINE_RE`)**, **line 26 (`parse`)**, **line 70 (`producer.produce`)**.
> "This script plays the log file into Kafka as if a live system were sending its logs.
> The `parse` function uses a regular expression to split each line into fields: time, level, component,
> message and block IDs. It turns them into JSON.
> On line 70 it sends each message to the Kafka topic `hdfs-logs`. I keep the original 2008 timestamps.
> The `--rate` option only controls how fast it sends."

### `scripts/check_topic.sh`
> "A helper that reads back from Kafka to prove the messages are there: how many there are, plus the
> first few."

---

## 4. Spark Structured Streaming — processing

### `jobs/stream_counts.py` ← spend the most time here
Point at:
- **line 42**, `readStream.format("kafka")`
  > "Spark reads from Kafka as a **stream**, not as a one-time file."
- **line 51**, `withWatermark`
  > "The watermark tells Spark when a time window is complete, so each window is written only once."
- **line 19**, `WINDOW = "10 minutes"` and **line 54**, `window_counts()`
  > "It groups logs into **10-minute windows** by the log's own time. For each window it counts total lines,
  > WARN lines, how many different blocks were active, and how many of them were anomalous."
- **line 61**, `join(F.broadcast(labels) ...)`
  > "Here it joins every block with its Normal/Anomaly label. That's how it knows which blocks failed."
- **line 81**, `component_counts()`
  > "A second table counts lines per window, per component and per level."
- **line 103**, `format("parquet")` and **line 106**, `checkpointLocation`
  > "Results are written as **Parquet files** to the warehouse folder. The checkpoint remembers how far
  > Spark has read, so if I run it again, it only processes new messages."

### `scripts/run_spark.sh`
> "Runs the Spark job inside the Spark container. With `--sink console` it prints the counts on screen, and
> with `--sink files` it writes the Parquet files for Hive."

### `warehouse/` folder
> "This is Spark's output: the Parquet files for my two tables, plus the checkpoints."

---

## 5. Hive — SQL over Spark's results

### `hive/create_tables.sql`
Point at **line 8 (`CREATE EXTERNAL TABLE`)** and **line 17 (`LOCATION`)**.
> "This creates two **external tables** in Hive, `window_counts` and `component_counts`. 'External' means
> Hive doesn't copy the data. It just reads the Parquet files Spark wrote in the warehouse folder.
> After this, the streaming results can be queried with normal SQL."

### `scripts/hive_setup.sh` and `scripts/hive_query.sh`
> "Two helpers: one runs the CREATE TABLE file, the other runs any SQL query and prints the result
> as a table."

---

## 6. Documents and vector search — Qdrant

### `docs/runbooks/` (open one, e.g. `dead-datanode.md`)
> "These are **7 runbooks** I wrote: short guides for common HDFS problems, covering symptoms, causes,
> what to check, and how to fix it."

### `data/docs_download/post-mortems-README.md`
> "This is the public danluu/post-mortems list: real outage stories from companies like Google,
> Facebook and Amazon."

### `app/index_docs.py`
Point at **line 28 (`post_mortems`)**, **45 (`runbooks`)**, **64 (`main`)**.
> "This builds my knowledge base. It splits the post-mortem list into **240 outage stories** and the runbooks
> into **36 sections**. It then turns each one into a vector and stores all **276** in Qdrant.
> It also saves them in `data/documents.jsonl` so I can read them. To add a new note, I put a file in
> `docs/runbooks` and run this again."

### `app/vector_search.py`
Point at **line 13 (`MODEL_NAME`)** and **line 32 (`search`)**.
> "The embedding model is **all-MiniLM-L6-v2** from sentence-transformers. It's small and runs on my CPU.
> It turns any text into **384 numbers** that capture its meaning. To search, I turn the question into
> numbers too, and Qdrant finds the documents with the closest meaning. So the words don't have to match
> exactly."

---

## 7. The AI agent — the brain

### `app/hive_sql.py`
Point at **line 11 (`ALLOWED_TABLES`)**, **16 (`FORBIDDEN`)**, **32 (`check_select_only`)**.
> "This runs SQL on Hive, but first it does a **safety check**. Only a single SELECT on my two tables is
> allowed. Words like DROP, INSERT or DELETE are refused. This matters because the AI writes the SQL."

### `app/agent.py` ← second most important file
Point at:
- **line 25**, `SYSTEM_PROMPT`
  > "These are the instructions for the AI. They tell it: use `query_hive` for number questions and
  > `search_docs` for meaning questions. They also describe my tables, so it can write correct SQL, and
  > explain that 'last hour' means the end of the 2008 data."
- **line 58**, `TOOLS`
  > "The two tools the AI can call."
- **line 100**, `ask()`
  > "This is the loop. I send the question to the LLM on Groq. The LLM replies with which tool to call.
  > I run that tool and send back the result, and this repeats until the LLM writes the final answer.
  > It never makes up numbers. Every number comes from Hive, and every explanation comes from my documents."

---

## 8. The website

### `streamlit_app.py`
Point at **line 87 (the three tabs)**.
> "The website, built with Streamlit. It has three tabs: **Ask**, which talks to the AI agent and shows the SQL or
> documents it used; **SQL**, where you run your own query; and **Search docs**, which searches the documents
> directly. The sidebar shows whether the services are running."

### `tests/`
> "Tests: one checks the safety guard against 17 safe and unsafe queries, and one clicks through the website
> automatically."

### Closing Part A
> "So that's the full path: **log file → replay.py → Kafka → Spark → Parquet files → Hive → AI agent →
> website**, with Qdrant holding the documents on the side. Now let me show it working."

---

# PART B — Showing it working

**Before the presentation:** start Docker Desktop, then in Ubuntu:
```
cd ~/logsense
docker compose up -d
```
Wait 2 minutes. Then in one terminal:
```
.venv/bin/streamlit run streamlit_app.py
```
Open http://localhost:8501 and ask one question as a warm-up.

### B1. Services running (second terminal)
```
docker compose ps
```
> "All four containers are healthy."

### B2. Kafka has the logs
```
bash scripts/check_topic.sh hdfs-logs 2
```
> "396,692 messages in Kafka, here are the first two as JSON."

### B3. Spark processing live (takes ~40 s, keep talking)
```
bash scripts/run_spark.sh --sink console
```
> "Spark is reading the stream from Kafka and printing the counts for each 10-minute window."

### B4. Hive SQL
```
bash scripts/hive_query.sh "SELECT window_start, total_lines, anomalous_blocks FROM logsense.window_counts ORDER BY anomalous_blocks DESC LIMIT 5"
```
> "The worst window was 10th November 2008, 10:30, with 103 anomalous blocks."

### B5. The website: ask questions (open "How I got this" every time)

| Ask | Expected | Say |
|---|---|---|
| Which 10-minute window had the most anomalous blocks? | 10 Nov 10:30, 103 | "Number question, so it used SQL. Here's the SQL it wrote." |
| Which component logged the most warnings? | dfs.DataNode$DataXceiver (~12,504) | "It picked the second table by itself." |
| What does 'Could not read from stream' mean and how do I fix it? | Broken write pipeline + fix steps | "Meaning question, so it searched the documents." |
| Show me outages at other companies caused by a power failure. | Salesforce, Cloudflare, … | "Real outage stories, found by meaning." |
| When was the worst spike of anomalous blocks, and what usually causes that? | 10 Nov 10:30 + causes | "Needs both: SQL first, then documents." |

### B6. Safety
**SQL** tab → `DROP TABLE window_counts` → Run → *Refused by the safety check*.
> "The AI can only read data, never delete it."

### B7. (Optional) Add your own note live
```
cp demo/namenode-safe-mode.md docs/runbooks/
.venv/bin/python -m app.index_docs
```
Ask: *Nobody can write files after we restarted the cluster. What should I do?*
> "It immediately uses the note I just added, so the team learns from every failure."

(Afterwards: `rm docs/runbooks/namenode-safe-mode.md && .venv/bin/python -m app.index_docs`)

### Closing
> "To sum up: **Kafka** streams the logs, **Spark Structured Streaming** counts them every 10 minutes,
> **Hive** makes the counts available with SQL, **Qdrant** searches documents by meaning, and an **AI agent**
> picks the right tool and shows its working. It all runs on my laptop in Docker. Thank you!"

---

## If something breaks
- Hive error: `docker compose restart hive`, wait 1 minute, then `bash scripts/hive_setup.sh`.
- AI error: wait 10 seconds and ask again.
- First question slow: that's normal, because the models are loading.
