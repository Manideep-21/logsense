"""Click through the web page without a browser. Run: .venv/bin/python -m tests.test_streamlit_app

Needs Hive and Qdrant running. Uses a fake agent, so no Groq key is needed.
"""
import os
from unittest import mock

from streamlit.testing.v1 import AppTest

FAKE_RESULT = {
    "answer": "There were **18** anomalous block-windows in the last hour (09:50-10:50 log time).",
    "steps": [
        {"tool": "query_hive", "args": {"sql": "SELECT SUM(anomalous_blocks) AS n FROM window_counts"},
         "result": {"sql": "...", "columns": ["n"], "rows": [[18]], "truncated": False}},
        {"tool": "search_docs", "args": {"query": "anomalous blocks", "source": "runbook"},
         "result": {"documents": [{"title": "Runbook: spike", "source": "runbook", "score": 0.7,
                                   "url": "docs/runbooks/anomalous-block-spike.md", "text": "What it means"}]}},
    ],
}


def run(thing):
    """Rerun the page. `thing` is the page, or a widget we just clicked / typed into."""
    at = thing.run(timeout=180)
    assert not at.exception, [e.value for e in at.exception]
    return at


def main():
    os.environ.pop("GROQ_API_KEY", None)
    at = run(AppTest.from_file("streamlit_app.py", default_timeout=180))
    print("sidebar:", [s.value for s in at.sidebar.success] + [w.value[:40] for w in at.sidebar.warning])
    assert any("Qdrant" in s.value for s in at.sidebar.success)
    assert at.sidebar.warning, "should warn that the Groq key is missing"

    # SQL tab: a real query and a refused one
    run_btn = next(b for b in at.button if b.label == "Run query")
    at = run(run_btn.click())
    df = at.dataframe[0].value
    print("SQL tab rows:", len(df), "| first window:", df.iloc[0]["window_start"], df.iloc[0]["anomalous_blocks"])
    assert len(df) == 10
    at.text_area[0].set_value("DROP TABLE window_counts")
    at = run(next(b for b in at.button if b.label == "Run query").click())
    print("SQL tab refused:", at.error[0].value)
    assert "safety check" in at.error[0].value

    # Search tab
    at = run(next(b for b in at.button if b.label == "Search").click())
    titles = [m.value for m in at.markdown if " · score " in m.value]
    print("Search tab:", titles[:2])
    assert len(titles) == 5

    # Ask tab without a key -> friendly error
    at = run(at.button[0].click())
    print("Ask without key:", at.error[0].value[:60])
    assert "Groq API key" in at.error[0].value

    # Ask tab with a (fake) key and a fake agent -> answer + SQL + documents shown
    os.environ["GROQ_API_KEY"] = "gsk_fake_for_test"
    with mock.patch("app.agent.ask", return_value=FAKE_RESULT):
        at = run(AppTest.from_file("streamlit_app.py", default_timeout=180))
        at = run(at.chat_input[0].set_value("How many anomalous blocks in the last hour?"))
    shown = [m.value for m in at.markdown]
    assert any("**18**" in v for v in shown), shown
    assert at.code[0].value.startswith("SELECT SUM"), at.code
    assert any("Runbook: spike" in v for v in shown)
    print("Ask with fake agent: answer, SQL and document all shown")
    os.environ.pop("GROQ_API_KEY")
    print("\nall UI checks passed")


if __name__ == "__main__":
    main()
