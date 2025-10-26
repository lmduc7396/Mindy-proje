"""Data access utilities for the Streamlit earnings dashboard."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable, Sequence

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine


class MissingDatabaseURL(RuntimeError):
    """Raised when the required DATABASE_URL environment variable is absent."""


def _get_database_url() -> str:
    """Return the database URL from environment variables.

    Raises
    ------
    MissingDatabaseURL
        If the DATABASE_URL variable has not been configured.
    """

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise MissingDatabaseURL(
            "DATABASE_URL environment variable is not set. "
            "Configure it with your database connection string (e.g. "
            "mssql+pyodbc://user:pass@server/database?driver=ODBC+Driver+17+for+SQL+Server)."
        )
    return db_url


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
