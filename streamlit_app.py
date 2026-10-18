"""LogSense web interface.

Run:  .venv/bin/streamlit run streamlit_app.py
Then open http://localhost:8501 in your browser.
"""
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.hive_sql import UnsafeSQL, run_sql
from app.vector_search import COLLECTION, get_client, search

st.set_page_config(page_title="LogSense", page_icon="🔎", layout="wide")

EXAMPLES = [
    "How many anomalous blocks were there in the last hour?",
    "Which 10-minute window had the most anomalous blocks?",
    "What does 'Could not read from stream' mean and how do I fix it?",
    "Show me outages at other companies caused by a bad config change.",
    "When was the worst spike of anomalous blocks, and what usually causes that?",
]


def has_groq_key():
    load_dotenv(override=True)   # re-read .env each time, so a key added later is picked up
    return os.getenv("GROQ_API_KEY", "").startswith("gsk_")


def show_rows(result):
    df = pd.DataFrame(result["rows"], columns=result["columns"])
    st.dataframe(df, hide_index=True, use_container_width=True)
    if result["truncated"]:
        st.caption("Only the first 200 rows are shown.")


def show_docs(docs):
    for d in docs:
        st.markdown(f"**{d['title']}** · {d['source']} · score {d['score']}")
        st.caption(d["text"][:400] + ("…" if len(d["text"]) > 400 else ""))
        if d.get("url", "").startswith("http"):
            st.caption(d["url"])
        elif d.get("url"):
            st.caption(f"file: {d['url']}")


def show_steps(steps):
    """The 'working': every tool the agent used, with its SQL or documents."""
    if not steps:
        st.caption("No tools were used for this answer.")
    for i, step in enumerate(steps, 1):
        result = step["result"]
        if step["tool"] == "query_hive":
            st.markdown(f"**Step {i} · Hive SQL**")
            st.code(step["args"].get("sql", ""), language="sql")
            if "error" in result:
                st.error(result["error"])
            else:
                show_rows(result)
        else:
            src = step["args"].get("source") or "any"
            st.markdown(f"**Step {i} · Document search** — “{step['args'].get('query', '')}” (source: {src})")
            if "error" in result:
                st.error(result["error"])
            else:
                show_docs(result["documents"])


# ---------- sidebar: are the services up? ----------
with st.sidebar:
    st.header("LogSense")
    st.caption("Ask plain-English questions about HDFS failures (Nov 2008 logs) and outages in general.")
    st.subheader("Status")
    try:
        n_docs = get_client().count(COLLECTION).count
        st.success(f"Qdrant: {n_docs} documents")
    except Exception as e:
        st.error(f"Qdrant not reachable: {type(e).__name__}")
    if has_groq_key():
        from app.agent import MODEL
        st.success(f"Groq key found · model {MODEL}")
    else:
        st.warning("No Groq key in .env — the Ask tab needs it. The SQL and Search tabs work without it.")
    st.caption("Hive is checked when you run a query (each query takes a few seconds).")

ask_tab, sql_tab, docs_tab = st.tabs(["💬 Ask", "🗄️ SQL", "📄 Search docs"])

# ---------- Ask: the agent ----------
with ask_tab:
    if "history" not in st.session_state:
        st.session_state.history = []   # list of {"question", "answer", "steps"}

    st.write("Try an example:")
    cols = st.columns(len(EXAMPLES))
    clicked = None
    for col, example in zip(cols, EXAMPLES):
        if col.button(example, use_container_width=True):
            clicked = example

    for turn in st.session_state.history:
        with st.chat_message("user"):
            st.write(turn["question"])
        with st.chat_message("assistant"):
            st.markdown(turn["answer"])
            with st.expander("How I got this (SQL / documents used)"):
                show_steps(turn["steps"])

    question = st.chat_input("Ask about HDFS failures…") or clicked
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            if not has_groq_key():
                st.error("I need a Groq API key to answer. Add GROQ_API_KEY to the .env file, then ask again.")
            else:
                from app.agent import ask
                with st.spinner("Thinking… (Hive queries take a few seconds)"):
                    try:
                        result = ask(question)
                    except Exception as e:
                        result = None
                        st.error(f"Something went wrong: {type(e).__name__}: {e}")
                if result:
                    st.markdown(result["answer"] or "")
                    with st.expander("How I got this (SQL / documents used)", expanded=True):
                        show_steps(result["steps"])
                    st.session_state.history.append({"question": question, **result})

# ---------- SQL: run a query directly ----------
with sql_tab:
    st.write("Run a read-only query yourself. Tables: `window_counts`, `component_counts`.")
    sql = st.text_area("SQL (SELECT only)", height=120,
                       value="SELECT window_start, total_lines, warn_lines, blocks, anomalous_blocks\n"
                             "FROM window_counts\nORDER BY anomalous_blocks DESC\nLIMIT 10")
    if st.button("Run query"):
        with st.spinner("Running on Hive…"):
            try:
                show_rows(run_sql(sql))
            except UnsafeSQL as e:
                st.error(f"Refused by the safety check: {e}")
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")

# ---------- Search docs: semantic search directly ----------
with docs_tab:
    st.write("Search post-mortems and HDFS runbooks by meaning, not exact words.")
    query = st.text_input("Search for", value="a bad config change took everything down")
    source = st.radio("Source", ["any", "runbook", "post-mortem"], horizontal=True)
    if st.button("Search") and query:
        with st.spinner("Searching…"):
            show_docs(search(query, k=5, source=None if source == "any" else source))
