"""Checks for the SELECT-only guard. Run: .venv/bin/python -m tests.test_sql_guard"""
from app.hive_sql import UnsafeSQL, check_select_only

ALLOWED = [
    "SELECT * FROM window_counts LIMIT 5",
    "select sum(lines) from logsense.component_counts where level = 'WARN';",
    "SELECT SUM(anomalous_blocks) FROM window_counts "
    "WHERE window_start >= (SELECT MAX(window_end) - INTERVAL '1' HOUR FROM window_counts)",
    "WITH w AS (SELECT * FROM window_counts) SELECT COUNT(*) FROM w",
    "SELECT date_add(window_start, 1), regexp_replace(component, 'dfs.', '') FROM component_counts c "
    "JOIN window_counts w ON c.window_start = w.window_start",
    "SELECT * FROM component_counts WHERE component = 'DROP TABLE; x'",   # words inside text are fine
]

BLOCKED = [
    "DROP TABLE window_counts",
    "SELECT 1; DROP TABLE window_counts",
    "INSERT INTO window_counts SELECT * FROM window_counts",
    "SELECT * FROM window_counts; SET hive.exec.mode=local",
    "CREATE TABLE x AS SELECT * FROM window_counts",
    "SELECT * FROM other_db.secret_table",
    "SELECT TRANSFORM(total_lines) USING 'rm -rf /' FROM window_counts",
    "INSERT OVERWRITE DIRECTORY '/tmp/x' SELECT * FROM window_counts",
    "/* hi */ DELETE FROM window_counts",
    "SHOW TABLES",
    "SELECT * FROM `window_counts`",
]


def main():
    failures = 0
    for sql in ALLOWED:
        try:
            check_select_only(sql)
        except UnsafeSQL as e:
            failures += 1
            print(f"FAIL (should be allowed): {sql}\n    -> {e}")
    for sql in BLOCKED:
        try:
            check_select_only(sql)
            failures += 1
            print(f"FAIL (should be blocked): {sql}")
        except UnsafeSQL as e:
            print(f"blocked ok: {sql[:60]:60} -> {e}")
    print(f"\n{len(ALLOWED) + len(BLOCKED) - failures}/{len(ALLOWED) + len(BLOCKED)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
