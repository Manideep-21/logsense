# LogSense — Demo Video Script (about 8 minutes)

How to read this: **[SCREEN]** = what to show, **[DO]** = what to type or click, **[SAY]** = read this out loud.

---

## PART 0 — Get ready (before you press record)

1. Start **Docker Desktop** on Windows. Wait until it says "Engine running".
2. Open the **Ubuntu** terminal and run:
   ```
   cd ~/logsense
   docker compose up -d
   ```
   Wait 2 minutes, then check that all four say **(healthy)**:
   ```
   docker compose ps
   ```
3. Start the website in this terminal (leave it running):
   ```
   .venv/bin/streamlit run streamlit_app.py
   ```
4. Open a **second** Ubuntu terminal and run `cd ~/logsense`. You will type commands here in the video.
   Make the font big: Ctrl + mouse wheel.
5. Open **http://localhost:8501** in the browser. Ask any question once as a warm-up, then refresh the page
   (F5) so the chat is empty.
6. Close other apps and notifications. Record with **Win + Alt + R** (Xbox Game Bar) or OBS.
7. Make sure the file `docs/runbooks/namenode-safe-mode.md` does **not** exist yet (you will add it live in Part 7).

Tip: if you make a mistake, just pause, then continue from the start of that part. You can cut it later.

---

## PART 1 — Introduction (30 s)

**[SCREEN]** The LogSense website.

**[SAY]**
> "Hello, my project is called **LogSense**.
> Big computer systems write millions of log lines, a kind of diary of everything they do. When something
> fails, finding the answer in those logs is very hard.
> LogSense is an assistant where you just ask a question in plain English, like 'how many failures happened
> in the last hour?' or 'what does this error mean?', and it finds the answer from real data."

---

## PART 2 — The data and the big picture (60 s)

**[SCREEN]** Open `DEMO.md` and scroll to the diagram "The flow in one picture". Or draw it on a slide.

**[SAY]**
> "I used the **HDFS dataset** from Loghub. It is real logs from a Hadoop storage cluster, recorded in
> November 2008. HDFS stores files in pieces called blocks, and researchers labelled every block as normal
> or anomalous, which means failed. I used about **400,000 log lines** with about **20,000 blocks**,
> **614 of them anomalous**.
>
> My project has two kinds of questions.
> **Number questions**, like 'how many' or 'when', need exact counts, so they go to a database with SQL.
> **Meaning questions**, like 'what does this error mean' or 'how do I fix it', go to a search over documents.
> An **AI agent** decides which one to use.
>
> The data flows like this: **Kafka** receives the logs, **Spark** processes them live, **Hive** stores the
> results for SQL, and **Qdrant** holds the documents. Let me show each part."

---

## PART 3 — Docker: everything running (20 s)

**[SCREEN]** Second terminal.
**[DO]** `docker compose ps`

**[SAY]**
> "Everything runs on my laptop in Docker containers: Kafka, Spark, Hive and Qdrant, all healthy."

---

## PART 4 — Kafka: the logs arrive (45 s)

**[DO]** `bash scripts/check_topic.sh hdfs-logs 2`

**[SAY]**
> "First, Kafka. Kafka is a message queue, like a conveyor belt for data.
> My replay script reads the log file line by line, turns each line into JSON with the time, level,
> component, message and block ID, and sends it to Kafka. This simulates a live system streaming its logs.
> You can see Kafka holds **396,692 messages**, and here are the first two. Notice I keep the original
> 2008 time."

---

## PART 5 — Spark Streaming: processing live (70 s)

**[DO]** `bash scripts/run_spark.sh --sink console`
(It takes about 40 seconds. Talk while it runs.)

**[SAY]** (while it runs)
> "Next is **Spark Structured Streaming**. Spark reads the messages from Kafka as a stream and groups them
> into **10-minute windows** based on the log time.
> For every window it counts the total lines, the warnings, how many different blocks were active, and how
> many of those blocks were anomalous. To know which blocks failed, it joins each block with the
> anomaly labels."

**[SCREEN]** When the tables appear, scroll up a little to show one table.

**[SAY]**
> "Here's the output. Each row is one 10-minute window from 2008, with its counts.
> Here I printed them to the screen. In the real pipeline, Spark writes these results as **Parquet files**
> into a shared folder. Spark remembers how far it has read, so when new logs arrive it only processes the
> new ones."

---

## PART 6 — Hive: asking with SQL (45 s)

**[DO]**
```
bash scripts/hive_query.sh "SELECT window_start, total_lines, warn_lines, anomalous_blocks FROM logsense.window_counts ORDER BY anomalous_blocks DESC LIMIT 5"
```

**[SAY]**
> "Next is **Hive**. Hive reads the files Spark wrote and lets me query them with SQL, like a normal database.
> This query asks for the windows with the most failures.
> The worst one was **10th November 2008, 10:30 to 10:40**, with **103 anomalous blocks**."

---

## PART 7 — Qdrant: search by meaning + adding my own notes (90 s)

**[SCREEN]** Browser → **📄 Search docs** tab.
**[DO]** Search: `a bad config change took everything down`

**[SAY]**
> "Now the documents. I collected **240 real outage stories** from companies like Facebook, Google and
> Amazon, plus HDFS fix-it guides called runbooks. Each one is turned into a vector, a list of numbers that
> captures its meaning, using a sentence-transformers model on my laptop. The vectors are stored in
> **Qdrant**, a vector database.
> I searched 'a bad config change took everything down', and it found the Facebook and Google outages
> caused by bad configs. The words don't have to match exactly. It searches by meaning."

**[SAY]**
> "You can also add your own notes, so the system learns from new failures and the team doesn't repeat them.
> First, let me search for a problem that has no note yet."

**[DO]** Search: `nobody can write files after we restarted the cluster`
(The results are general and not a good match.)

**[SAY]**
> "Nothing really fits. Now I add a note I wrote about this problem and reload the documents."

**[DO]** In the terminal:
```
cp demo/namenode-safe-mode.md docs/runbooks/
.venv/bin/python -m app.index_docs
```
**[DO]** Search again: `nobody can write files after we restarted the cluster`

**[SAY]**
> "Now my new note, 'HDFS stuck in safe mode after a restart', is the top result. Anyone who hits this
> problem later will find the fix straight away."

---

## PART 8 — The AI agent: the main part (2 min)

**[SCREEN]** Browser → **💬 Ask** tab.

**[SAY]**
> "Now the main part, the **AI agent**. It uses an LLM on Groq. I gave it two tools: one runs SQL on Hive,
> the other searches the documents in Qdrant. For every question, the AI decides which tool to use.
> It answers only from what the tools return, so it doesn't make up numbers."

**Question 1 — a number question**
**[DO]** Click: *How many anomalous blocks were there in the last hour?* Then open **"How I got this"**.
**[SAY]**
> "This is a number question, so the AI wrote an SQL query by itself and ran it on Hive. You can see the
> exact SQL and the result. 'Last hour' means the last hour of the log data, in 2008."

**Question 2 — a meaning question**
**[DO]** Click: *What does 'Could not read from stream' mean and how do I fix it?*
**[SAY]**
> "This is a meaning question, so it searched the runbooks instead. It explains the error and the fix, and
> shows which documents it used."

**Question 3 — needs both**
**[DO]** Click: *When was the worst spike of anomalous blocks, and what usually causes that?*
**[SAY]**
> "This question needs both. First it ran SQL and found the spike at 10:30 on 10th November. Then it searched
> the runbooks for the usual causes, and combined both into one answer."

**Question 4 — your new note** (optional)
**[DO]** Type: `Nobody can write files after we restarted the cluster. What should I do?`
**[SAY]**
> "And it already uses the note I added a minute ago."

---

## PART 9 — Safety (30 s)

**[SCREEN]** Browser → **🗄️ SQL** tab.
**[DO]** Replace the text with `DROP TABLE window_counts` and click **Run query**.

**[SAY]**
> "Because the AI writes SQL, I added a safety check. Only read-only SELECT queries on my tables are allowed.
> A command like DROP TABLE, which would delete data, is refused before it ever reaches Hive."

---

## PART 10 — Conclusion (40 s)

**[SCREEN]** The Ask tab with the answers visible.

**[SAY]**
> "To sum up:
> **Kafka** carries the stream of logs.
> **Spark Structured Streaming** turns it into counts every 10 minutes.
> **Hive** makes those counts available with SQL.
> **Qdrant** searches outage reports and my own notes by meaning.
> An **AI agent** picks the right tool for each question and always shows how it got the answer.
>
> In the future I'd like to support other log formats, so any company can feed in its own live logs.
> Thank you for watching."

---

## AFTER recording: clean up the demo note (so you can record again)

```
rm docs/runbooks/namenode-safe-mode.md
.venv/bin/python -m app.index_docs
```

## If something goes wrong while recording
- **Hive query fails:** `docker compose restart hive`, wait 1 minute, then `bash scripts/hive_setup.sh`.
- **The AI gives an error:** wait 10 seconds and click the question again. Groq sometimes limits requests.
- **The page looks stuck:** the first question is slow, because the models are loading. That's why you warm up first.
