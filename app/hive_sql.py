"""Run read-only SQL against Hive, with a safety check that only allows SELECT.

Try it:  .venv/bin/python -m app.hive_sql "SELECT * FROM window_counts ORDER BY anomalous_blocks DESC LIMIT 3"
"""
import re
import sys

from pyhive import hive

HIVE_HOST, HIVE_PORT, DATABASE = "localhost", 10000, "logsense"
ALLOWED_TABLES = {"window_counts", "component_counts"}
MAX_ROWS = 200

# Words that change data or settings, or run programs. Matched as whole words,
# so functions like date_add or regexp_replace are still fine.
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|UPSERT|DROP|CREATE|ALTER|TRUNCATE|LOAD|GRANT|REVOKE|"
    r"SET|RESET|ADD|DFS|MSCK|EXPORT|IMPORT|REPLACE|USE|LOCK|UNLOCK|ANALYZE|COMPACT|KILL|"
    r"RELOAD|OVERWRITE|DIRECTORY|TRANSFORM|MAP|REDUCE|EXPLAIN|DESCRIBE|SHOW)\b", re.I)


class UnsafeSQL(ValueError):
    pass


def _strip_comments_and_strings(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)           # /* block comments */
    sql = re.sub(r"--[^\n]*", " ", sql)                         # -- line comments
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", sql)  # 'text' -> ''


def check_select_only(sql):
    """Raise UnsafeSQL unless sql is a single SELECT over our tables. Returns the cleaned SQL."""
    sql = sql.strip().rstrip(";").strip()
    code = _strip_comments_and_strings(sql)
    if ";" in code:
        raise UnsafeSQL("only one statement is allowed")
    if not re.match(r"\s*(SELECT|WITH)\b", code, re.I):
        raise UnsafeSQL("only SELECT queries are allowed")
    bad = FORBIDDEN.search(code)
    if bad:
        raise UnsafeSQL(f"keyword not allowed: {bad.group(1).upper()}")
    if "`" in code:
        raise UnsafeSQL("backtick-quoted names are not allowed")

    # Every table after FROM / JOIN must be one of ours (or a WITH ... AS name).
    ctes = {m.lower() for m in re.findall(r"(?:\bWITH|,)\s*(\w+)\s+AS\s*\(", code, re.I)}
    for name in re.findall(r"\b(?:FROM|JOIN)\s+([\w.]+)", code, re.I):
        table = name.lower().removeprefix(f"{DATABASE}.")
        if table not in ALLOWED_TABLES | ctes:
            raise UnsafeSQL(f"unknown table: {name} (allowed: {', '.join(sorted(ALLOWED_TABLES))})")
    return sql


def run_sql(sql):
    """Check, run, and return {"sql", "columns", "rows", "truncated"}. Raises on unsafe or bad SQL."""
    sql = check_select_only(sql)
    conn = hive.connect(host=HIVE_HOST, port=HIVE_PORT, username="hive", database=DATABASE, auth="NONE")
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql)
        except hive.OperationalError as e:
            # Pull Hive's readable message out of the Thrift response object
            status = getattr(e.args[0], "status", None) if e.args else None
            raise RuntimeError(getattr(status, "errorMessage", None) or str(e)) from None
        rows = cur.fetchmany(MAX_ROWS + 1)
        columns = [d[0].split(".")[-1] for d in cur.description]   # "window_counts.blocks" -> "blocks"
    finally:
        conn.close()
    return {"sql": sql, "columns": columns, "rows": [list(r) for r in rows[:MAX_ROWS]],
            "truncated": len(rows) > MAX_ROWS}


if __name__ == "__main__":
    result = run_sql(sys.argv[1])
    print(" | ".join(result["columns"]))
    for row in result["rows"]:
        print(" | ".join(map(str, row)))
