"""PostgreSQL access layer for the SINAM database (Aurola)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterable

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()


def _conn_kwargs() -> dict:
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "Aurola"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
    }


@contextmanager
def get_conn():
    cfg = _conn_kwargs()
    conn = psycopg.connect(**cfg)
    try:
        yield conn
    finally:
        conn.close()


def ping() -> str:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT version();")
        return cur.fetchone()[0]


def list_tables(schema: str = "public") -> list[str]:
    sql = """
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = %s
         ORDER BY table_name;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (schema,))
        return [r[0] for r in cur.fetchall()]


def describe_table(table: str, schema: str = "public") -> pd.DataFrame:
    sql = """
        SELECT column_name, data_type, is_nullable
          FROM information_schema.columns
         WHERE table_schema = %s AND table_name = %s
         ORDER BY ordinal_position;
    """
    return run_query(sql, params=(schema, table))


def run_query(sql: str, params: Iterable | None = None) -> pd.DataFrame:
    """Run a SQL query and return a pandas DataFrame (no SQLAlchemy needed)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description] if cur.description else []
        rows = cur.fetchall() if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def time_series(
    sql: str,
    date_col: str = "data",
    value_col: str = "valor",
    freq: str | None = None,
    fillna: float | None = 0.0,
    params: Iterable | None = None,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Run an SQL query that returns (date_col, value_col) and turn it into a
    numpy time series suitable for ChatTime.

    The SQL is expected to already aggregate (e.g. SELECT date_trunc('day', ...),
    COUNT(*) ...). If `freq` is supplied, an extra pandas resample is applied.
    """
    df = run_query(sql, params=params)
    if date_col not in df.columns or value_col not in df.columns:
        raise ValueError(
            f"Query must return columns '{date_col}' and '{value_col}'. Got {list(df.columns)}"
        )
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).set_index(date_col)
    if freq:
        # pandas 3.0 renamed legacy offset aliases: M -> ME, Q -> QE, Y -> YE
        freq = {"M": "ME", "Q": "QE", "Y": "YE", "A": "YE"}.get(freq, freq)
        df = df[[value_col]].resample(freq).sum()
    series = df[value_col].astype(float)
    if fillna is not None:
        series = series.fillna(fillna)
    return series.index, series.to_numpy(dtype=float)


# ---------- SINAM (VIOLBR) helpers ----------------------------------------

VIOLBR_TABLES_BY_YEAR = {
    2020: "VIOLBR20",
    2021: "VIOLBR21",
    2022: "VIOLBR22",
    2023: "VIOLBR23",
    2024: "VIOLBR24",
}


def violbr_daily_counts(
    year: int,
    where: str | None = None,
    date_col: str = "DT_NOTIFIC",
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Daily notification counts from the VIOLBR<YY> table for a given year.

    Args:
        year: 2020..2024 (selects the matching VIOLBR<YY> table)
        where: optional extra SQL filter, e.g. "\"CS_SEXO\" = 'F'"
        date_col: text date column (default DT_NOTIFIC). Dates stored as 'YYYY-MM-DD'.
    """
    table = VIOLBR_TABLES_BY_YEAR.get(year)
    if table is None:
        raise ValueError(f"Unknown VIOLBR year {year!r}. Known: {list(VIOLBR_TABLES_BY_YEAR)}")
    where_sql = f"AND ({where})" if where else ""
    sql = f"""
        SELECT "{date_col}"::date AS data, COUNT(*)::int AS valor
          FROM "{table}"
         WHERE "{date_col}" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
         {where_sql}
         GROUP BY 1
         ORDER BY 1;
    """
    return time_series(sql, date_col="data", value_col="valor", freq="D")
