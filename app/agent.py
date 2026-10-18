"""The LogSense agent: an LLM (on Groq) that picks a tool for each question.

  number questions  -> query_hive   (SELECT-only SQL over the Hive tables)
  meaning questions -> search_docs  (semantic search over post-mortems + runbooks in Qdrant)

Try it:  .venv/bin/python -m app.agent "How many anomalous blocks were there in the last hour?"
Needs GROQ_API_KEY in the .env file (see .env.example).
"""
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal

from dotenv import load_dotenv
from groq import BadRequestError, Groq

from app.hive_sql import MAX_ROWS, UnsafeSQL, run_sql
from app.vector_search import search

load_dotenv()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_STEPS = 6          # tool calls per question before we give up

SYSTEM_PROMPT = f"""You are LogSense, an assistant that answers questions about failures in an HDFS
cluster (logs from November 2008) and about system outages in general.

You have two tools. Always use a tool; never make up numbers or facts.
- query_hive: for questions about NUMBERS from the HDFS logs (counts, totals, trends, worst/busiest
  times, components, warnings, anomalous blocks). Write one Hive SQL SELECT query.
- search_docs: for questions about MEANING (what an error means, why something happens, how to fix it,
  examples of similar outages at other companies). Searches HDFS runbooks and public post-mortems.
Some questions need both: get the numbers first, then search for explanations.

Hive tables (database logsense; times are 2008 log time, in 10-minute windows):
  window_counts(window_start TIMESTAMP, window_end TIMESTAMP, total_lines BIGINT,
                warn_lines BIGINT, blocks BIGINT, anomalous_blocks BIGINT)
    one row per 10-minute window. blocks = different HDFS blocks active in the window;
    anomalous_blocks = how many of those are labelled Anomaly.
  component_counts(window_start TIMESTAMP, window_end TIMESTAMP, component STRING, level STRING, lines BIGINT)
    one row per window + component (e.g. 'dfs.DataNode$DataXceiver') + level ('INFO' or 'WARN').

Data covers 2008-11-09 20:30 to 2008-11-11 11:00. Levels are only INFO and WARN (no ERROR lines),
so for "errors" or "failures" use anomalous_blocks (and warn_lines), not a level = 'ERROR' filter.

SQL rules:
- Hive SQL, SELECT only, one statement, no semicolon, at most {MAX_ROWS} rows (use LIMIT).
- "Now" means the end of the data, not today's date. "The last hour" means:
  WHERE window_start >= (SELECT MAX(window_end) - INTERVAL '1' HOUR FROM window_counts)
- Time literals look like TIMESTAMP '2008-11-10 10:00:00'. Hourly buckets: date_format(window_start, 'yyyy-MM-dd HH').
- A block can be active in several windows, so SUM(anomalous_blocks) over many windows counts
  "anomalous block-windows", not unique blocks. Say so when you report such a sum.
- If a query fails, read the error, fix the SQL, and try again.

Answer in plain, short English. Mention the time period your numbers cover. When you use documents,
name them (company or runbook title)."""

TOOLS = [
    {"type": "function", "function": {
        "name": "query_hive",
        "description": "Run one read-only Hive SQL SELECT query over the logsense tables and return the rows.",
        "parameters": {"type": "object", "properties": {
            "sql": {"type": "string", "description": "A single Hive SQL SELECT statement."}},
            "required": ["sql"]}}},
    {"type": "function", "function": {
        "name": "search_docs",
        "description": "Semantic search over HDFS runbook notes and public outage post-mortems.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "What to look for, in plain words."},
            "source": {"type": "string", "enum": ["any", "runbook", "post-mortem"],
                       "description": "runbook = HDFS how-to notes; post-mortem = outages at other companies."}},
            "required": ["query"]}}},
]


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def run_tool(name, args):
    """Run one tool. Errors are returned (not raised) so the LLM can read them and retry."""
    try:
        if name == "query_hive":
            return run_sql(args["sql"])
        if name == "search_docs":
            source = args.get("source")
            hits = search(args["query"], k=4, source=None if source in (None, "any") else source)
            return {"documents": [{**h, "text": h["text"][:800]} for h in hits]}
        return {"error": f"unknown tool {name}"}
    except UnsafeSQL as e:
        return {"error": f"query refused by safety check: {e}"}
    except Exception as e:   # bad SQL, Hive/Qdrant down, ...
        return {"error": f"{type(e).__name__}: {str(e)[:500]}"}


def ask(question, client=None):
    """Answer one question. Returns {"answer": str, "steps": [{"tool", "args", "result"}, ...]}."""
    client = client or Groq()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    steps = []

    for _ in range(MAX_STEPS + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0)
        except BadRequestError as e:
            # Sometimes the model writes a malformed tool call; ask it to try again once.
            if "tool_use_failed" not in str(e) or any(m.get("role") == "user" and "valid tool call" in m["content"]
                                                      for m in messages):
                raise
            messages.append({"role": "user", "content": "Your last tool call was malformed. Please make a valid tool call."})
            continue

        msg = response.choices[0].message
        if not msg.tool_calls:
            return {"answer": msg.content, "steps": steps}

        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = (run_tool(tc.function.name, args) if len(steps) < MAX_STEPS
                      else {"error": "too many tool calls; answer with what you have"})
            steps.append({"tool": tc.function.name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, default=_json_default)[:6000]})

    return {"answer": "Sorry, I couldn't finish answering within the step limit.", "steps": steps}


def main():
    result = ask(" ".join(sys.argv[1:]))
    for i, step in enumerate(result["steps"], 1):
        print(f"--- step {i}: {step['tool']}")
        if step["tool"] == "query_hive":
            print("SQL:", step["args"].get("sql"))
        else:
            print("search:", step["args"].get("query"), f"(source={step['args'].get('source', 'any')})")
        res = step["result"]
        if "error" in res:
            print("error:", res["error"])
        elif "rows" in res:
            print(res["columns"], res["rows"][:5], "..." if len(res["rows"]) > 5 else "")
        else:
            print("docs:", [f"{d['title']} ({d['score']})" for d in res["documents"]])
    print("\n=== answer ===\n" + (result["answer"] or ""))


if __name__ == "__main__":
    main()
