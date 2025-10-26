"""Data access utilities for the Streamlit earnings dashboard."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable, Optional, Sequence

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

try:  # Streamlit may not be installed in non-app contexts
    import streamlit as st  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    st = None  # type: ignore

from urllib.parse import quote_plus

try:
    import pyodbc  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pyodbc = None  # type: ignore


class MissingDatabaseURL(RuntimeError):
    """Raised when the required DATABASE_URL environment variable is absent."""


def _maybe_replace_driver(connection_string: str) -> str:
    """Replace ODBC driver name if the requested one is unavailable."""

    if pyodbc is None:
        return connection_string

    try:
        available_drivers = {driver.lower() for driver in pyodbc.drivers()}
    except Exception:  # pragma: no cover - defensive
        return connection_string

    # Normalize spacing to match driver list formatting
    requested_driver = None
    if "{ODBC Driver 18 for SQL Server}" in connection_string:
        requested_driver = "odbc driver 18 for sql server"
    elif "{ODBC Driver 17 for SQL Server}" in connection_string:
        requested_driver = "odbc driver 17 for sql server"

    if requested_driver and requested_driver not in available_drivers:
        fallback = "{ODBC Driver 17 for SQL Server}" if "odbc driver 17 for sql server" in available_drivers else None
        if fallback:
            return connection_string.replace("{ODBC Driver 18 for SQL Server}", fallback)

    return connection_string


def _standardise_sqlalchemy_url(raw_value: str) -> str:
    """Convert raw connection strings into a SQLAlchemy-compatible URL."""

    if raw_value.startswith("mssql+"):
        return raw_value

    # Assume the value is an ODBC connection string
    adjusted = _maybe_replace_driver(raw_value)
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(adjusted)}"


def _get_database_url() -> str:
    """Return the database URL from environment variables or Streamlit secrets."""

    candidates = [
        os.getenv("DATABASE_URL"),
        os.getenv("SOURCE_DB_CONNECTION_STRING"),
    ]

    if st is not None:
        secret_value: Optional[str] = st.secrets.get("DATABASE_URL") if "DATABASE_URL" in st.secrets else None
        if secret_value:
            candidates.insert(0, secret_value)
        secret_odbc: Optional[str] = (
            st.secrets.get("SOURCE_DB_CONNECTION_STRING")
            if "SOURCE_DB_CONNECTION_STRING" in st.secrets
            else None
        )
        if secret_odbc:
            candidates.append(secret_odbc)

    for candidate in candidates:
        if candidate:
            return _standardise_sqlalchemy_url(candidate)

    raise MissingDatabaseURL(
        "No database connection string configured. Set DATABASE_URL (SQLAlchemy style) or "
        "SOURCE_DB_CONNECTION_STRING (ODBC style) via environment variables or Streamlit secrets."
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (or return cached) SQLAlchemy engine for the configured database."""

    return create_engine(_get_database_url())


def fetch_sector_map(engine: Engine | None = None) -> pd.DataFrame:
    """Load ticker-to-sector classifications from the Sector_Map table."""

    engine = engine or get_engine()
    query = text(
        """
        SELECT
            Ticker,
            Sector,
            L1,
            L2
        FROM Sector_Map
        """
    )
    return pd.read_sql(query, engine)


def fetch_available_periods(
    table_name: str,
    date_column: str,
    metric_keycodes: Sequence[str],
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Retrieve distinct reporting periods for a given financial statements table."""

    engine = engine or get_engine()
    if not metric_keycodes:
        return pd.DataFrame(columns=["period"])

    stmt = (
        text(
            f"""
            SELECT DISTINCT {date_column} AS period
            FROM {table_name}
            WHERE KEYCODE IN :metric_codes
            """
        )
        .bindparams(bindparam("metric_codes", expanding=True))
    )

    return pd.read_sql(stmt, engine, params={"metric_codes": list(metric_keycodes)})


def fetch_financials(
    table_name: str,
    date_column: str,
    metric_keycodes: Sequence[str],
    periods: Iterable[str],
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Load raw financial values for the requested periods and metrics."""

    engine = engine or get_engine()
    period_list = list(periods)
    if not period_list:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "PERIOD",
                "KEYCODE",
                "VALUE",
                "Sector",
                "L1",
                "L2",
            ]
        )

    stmt = (
        text(
            f"""
            SELECT
                fa.TICKER AS Ticker,
                fa.{date_column} AS PERIOD,
                fa.KEYCODE,
                fa.VALUE,
                sm.Sector,
                sm.L1,
                sm.L2
            FROM {table_name} AS fa
            INNER JOIN Sector_Map AS sm
                ON sm.Ticker = fa.TICKER
            WHERE fa.KEYCODE IN :metric_codes
              AND fa.{date_column} IN :periods
            """
        )
        .bindparams(
            bindparam("metric_codes", expanding=True),
            bindparam("periods", expanding=True),
        )
    )

    params = {
        "metric_codes": list(metric_keycodes),
        "periods": period_list,
    }

    return pd.read_sql(stmt, engine, params=params)
