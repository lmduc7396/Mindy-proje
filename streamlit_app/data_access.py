"""Data access utilities for the Streamlit earnings dashboard."""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

try:  # Streamlit may not be installed in non-app contexts
    import streamlit as st  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    st = None  # type: ignore

from urllib.parse import quote, quote_plus


class MissingDatabaseURL(RuntimeError):
    """Raised when the required DATABASE_URL environment variable is absent."""


def _standardise_sqlalchemy_url(raw_value: str) -> str:
    """Convert raw connection strings into a SQLAlchemy-compatible URL."""

    if raw_value.startswith("mssql+"):
        return raw_value

    # Assume the value is an ODBC connection string
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(raw_value)}"


def _enumerate_secret_values() -> List[str]:
    candidates: List[str] = []

    env_candidates = [
        os.getenv("DATABASE_URL"),
        os.getenv("SOURCE_DB_CONNECTION_STRING"),
    ]
    candidates.extend([value for value in env_candidates if value])

    if st is not None:
        for key in ("DATABASE_URL", "SOURCE_DB_CONNECTION_STRING"):
            try:
                value = st.secrets[key]
            except Exception:  # pragma: no cover - secrets missing
                continue
            if value and value not in candidates:
                candidates.insert(0, value)

    return candidates


def _augment_with_driver_fallbacks(raw_value: str) -> List[str]:
    options: List[str] = []

    if "{ODBC Driver 18 for SQL Server}" in raw_value:
        fallback = raw_value.replace("{ODBC Driver 18 for SQL Server}", "{ODBC Driver 17 for SQL Server}")
        if fallback != raw_value:
            options.append(fallback)

    options.append(raw_value)

    return options


def _parse_odbc_connection_string(raw_value: str) -> Dict[str, str]:
    parts = [segment for segment in raw_value.strip().split(";") if segment]
    values: Dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip().upper()] = value.strip()
    return values


def _pymssql_url_from_odbc(raw_value: str) -> Optional[str]:
    values = _parse_odbc_connection_string(raw_value)
    user = values.get("UID")
    password = values.get("PWD")
    database = values.get("DATABASE")
    server = values.get("SERVER")

    if not all([user, password, database, server]):
        return None

    server = server.strip()
    if server.lower().startswith("tcp:"):
        server = server[4:]

    host = server
    port = "1433"
    if "," in server:
        host, port = server.split(",", 1)
        host = host.strip()
        port = port.strip()

    query_params = []
    encrypt = values.get("ENCRYPT")
    if encrypt:
        query_params.append(f"encrypt={encrypt.lower()}")

    trust_cert = values.get("TRUSTSERVERCERTIFICATE")
    if trust_cert:
        query_params.append(f"trustservercertificate={trust_cert.lower()}")

    timeout = values.get("CONNECTION TIMEOUT")
    if timeout:
        query_params.append(f"timeout={timeout}")

    query_string = f"?{'&'.join(query_params)}" if query_params else ""

    return (
        f"mssql+pymssql://{quote(user)}:{quote_plus(password)}@{host}:{port}/{database}{query_string}"
    )


def _get_candidate_database_urls() -> List[str]:
    raw_candidates = _enumerate_secret_values()
    if not raw_candidates:
        raise MissingDatabaseURL(
            "No database connection string configured. Set DATABASE_URL (SQLAlchemy format) or "
            "SOURCE_DB_CONNECTION_STRING (ODBC format) via environment variables or Streamlit secrets."
        )

    urls: List[str] = []
    for raw in raw_candidates:
        raw = raw.strip()
        if not raw:
            continue

        pymssql_url = _pymssql_url_from_odbc(raw)
        if pymssql_url and pymssql_url not in urls:
            urls.append(pymssql_url)

        for option in _augment_with_driver_fallbacks(raw):
            url = _standardise_sqlalchemy_url(option)
            if url not in urls:
                urls.append(url)
    return urls

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (or return cached) SQLAlchemy engine for the configured database.

    Attempts multiple connection strings (including driver fallbacks) until a
    connection succeeds. Raises the last encountered exception if all attempts
    fail.
    """

    candidate_urls = _get_candidate_database_urls()
    last_error: Optional[Exception] = None

    for url in candidate_urls:
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("Connected to database using %s", url)
            return engine
        except Exception as err:  # pragma: no cover - relies on external DB
            last_error = err
            engine.dispose()
            logger.warning("Connection attempt failed for %s: %s", url, err)
            continue

    if last_error:
        raise last_error

    # Should not reach here because MissingDatabaseURL already raised when no candidates
    raise MissingDatabaseURL("Unable to establish database connection with provided configuration.")


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
