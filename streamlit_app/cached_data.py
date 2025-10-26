"""Shared cached data loaders for Streamlit pages."""

from __future__ import annotations

from typing import Iterable, List

import pandas as pd
import streamlit as st

from streamlit_app.aggregation import FREQUENCY_CONFIG, metric_keycodes, sort_periods
from streamlit_app.data_access import (
    fetch_available_periods,
    fetch_financials,
    fetch_sector_map,
    get_engine,
)


@st.cache_resource(show_spinner=False)
def load_engine():
    return get_engine()


@st.cache_data(ttl=600, show_spinner=False)
def load_sector_map() -> pd.DataFrame:
    engine = load_engine()
    return fetch_sector_map(engine)


@st.cache_data(ttl=600, show_spinner=False)
def load_period_options(frequency: str) -> List[str]:
    config = FREQUENCY_CONFIG[frequency]
    engine = load_engine()
    periods_df = fetch_available_periods(
        table_name=config["table"],
        date_column=config["date_column"],
        metric_keycodes=metric_keycodes(),
        engine=engine,
    )

    if periods_df.empty:
        return []

    periods = periods_df["period"].dropna().astype(str).unique().tolist()
    return sort_periods(periods, frequency)


@st.cache_data(ttl=600, show_spinner=False)
def load_financial_snapshot(frequency: str, periods: Iterable[str]) -> pd.DataFrame:
    config = FREQUENCY_CONFIG[frequency]
    engine = load_engine()
    period_tuple = tuple(sorted(set(periods)))
    if not period_tuple:
        return pd.DataFrame()
    return fetch_financials(
        table_name=config["table"],
        date_column=config["date_column"],
        metric_keycodes=metric_keycodes(),
        periods=period_tuple,
        engine=engine,
    )
