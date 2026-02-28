"""
db.py — PostgreSQL connection pool and SQL execution helpers.
Uses psycopg2 with a simple connection pool via psycopg2.pool.
"""

import os
import psycopg2
from psycopg2 import pool, OperationalError
from psycopg2.extras import RealDictCursor
from typing import Tuple, List, Dict, Any, Optional


_pool: Optional[pool.SimpleConnectionPool] = None
PREVIEW_ROW_LIMIT = 10   


def _get_dsn() -> str:
    """Build DSN from individual env vars or a DATABASE_URL fallback."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host     = os.environ.get("DB_HOST", "localhost")
    port     = os.environ.get("DB_PORT", "5432")
    dbname   = os.environ.get("DB_NAME", "analytics")
    user     = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        try:
            _pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=_get_dsn(),
            )
        except OperationalError as exc:
            raise ConnectionError(f"Could not connect to PostgreSQL: {exc}") from exc
    return _pool



def execute_query(sql: str) -> Tuple[List[str], List[Dict[str, Any]], int]:
    """
    Execute a SQL SELECT and return (columns, rows, total_row_count).

    Args:
        sql: A valid SELECT statement.

    Returns:
        columns        — list of column name strings
        rows           — list of dicts (up to PREVIEW_ROW_LIMIT)
        total_count    — total rows the query returned (before preview cap)

    Raises:
        psycopg2.Error on any database error.
    """
    connection = _get_pool().getconn()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            all_rows = cur.fetchall()           # fetch everything to get total count
            total_count = len(all_rows)
            preview_rows = [dict(r) for r in all_rows[:PREVIEW_ROW_LIMIT]]
            columns = list(preview_rows[0].keys()) if preview_rows else []
        connection.rollback()                   # always rollback (read-only intent)
        return columns, preview_rows, total_count
    finally:
        _get_pool().putconn(connection)


def format_slack_table(columns: List[str], rows: List[Dict[str, Any]], total: int) -> str:
    """
    Build a fixed-width ASCII table suitable for a Slack code block.

    Args:
        columns: Column names.
        rows:    Preview rows (dicts).
        total:   Total row count from the DB.

    Returns:
        Formatted string.
    """
    if not rows:
        return "_No rows returned._"

    # Calculate column widths
    col_widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            col_widths[col] = max(col_widths[col], len(str(row.get(col, ""))))

    def fmt_row(values: List[str]) -> str:
        return "| " + " | ".join(
            str(v).ljust(col_widths[col]) for col, v in zip(columns, values)
        ) + " |"

    separator = "+-" + "-+-".join("-" * col_widths[col] for col in columns) + "-+"
    header    = fmt_row(columns)
    data_rows = [fmt_row([str(row.get(col, "")) for col in columns]) for row in rows]

    table_lines = [separator, header, separator] + data_rows + [separator]
    table = "\n".join(table_lines)

    footer = ""
    if total > len(rows):
        footer = f"\n_Showing {len(rows)} of {total} rows._"

    return table + footer