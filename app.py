"""Streamlit app for sector-level earnings monitoring."""

from __future__ import annotations

from typing import Iterable, List

import pandas as pd
import streamlit as st

from streamlit_app.aggregation import (
    FREQUENCY_CONFIG,
    ComparisonPeriods,
    determine_comparison_periods,
    metric_labels,
    metric_keycodes,
    sort_periods,
    summarise_by_sector,
)
from streamlit_app.data_access import (
    MissingDatabaseURL,
    fetch_available_periods,
    fetch_financials,
    fetch_sector_map,
    get_engine,
)


st.set_page_config(page_title="Sector Earnings Monitor", layout="wide")


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


def _format_display(df: pd.DataFrame, sector_column: str) -> pd.DataFrame:
    formatted = df.copy()

    earnings_metrics = metric_labels()
    for metric in earnings_metrics:
        if metric in formatted.columns:
            metric_values = pd.to_numeric(formatted[metric], errors="coerce")
            formatted[metric] = metric_values / 1e9

        qoq_col = f"{metric}_QoQ"
        yoy_col = f"{metric}_YoY"
        if qoq_col in formatted.columns:
            formatted[qoq_col] = pd.to_numeric(formatted[qoq_col], errors="coerce") * 100
        if yoy_col in formatted.columns:
            formatted[yoy_col] = pd.to_numeric(formatted[yoy_col], errors="coerce") * 100

    if "coverage_pct" in formatted.columns:
        formatted["coverage_pct"] = pd.to_numeric(formatted["coverage_pct"], errors="coerce") * 100

    column_order: List[str] = [sector_column, "released_companies", "total_companies", "coverage_pct"]
    for metric in earnings_metrics:
        column_order.extend([metric, f"{metric}_QoQ", f"{metric}_YoY"])

    existing_columns = [col for col in column_order if col in formatted.columns]
    remaining_columns = [col for col in formatted.columns if col not in existing_columns]
    return formatted[existing_columns + remaining_columns]


def _build_column_config(sector_column: str) -> dict:
    column_config: dict = {
        sector_column: st.column_config.TextColumn(sector_column, help=f"Sector classification ({sector_column})."),
        "released_companies": st.column_config.NumberColumn("Released", format="%d"),
        "total_companies": st.column_config.NumberColumn("Universe", format="%d"),
        "coverage_pct": st.column_config.ProgressColumn(
            "Coverage",
            format="%.0f%%",
            min_value=0,
            max_value=100,
        ),
    }

    for metric in metric_labels():
        column_config[metric] = st.column_config.NumberColumn(
            metric,
            help="Sector sum (VND bn).",
            format="%.1f",
        )
        column_config[f"{metric}_QoQ"] = st.column_config.NumberColumn(
            f"{metric} QoQ",
            help="Quarter-over-quarter growth (same ticker set).",
            format="%.1f%%",
        )
        column_config[f"{metric}_YoY"] = st.column_config.NumberColumn(
            f"{metric} YoY",
            help="Year-over-year growth (same ticker set).",
            format="%.1f%%",
        )
    return column_config


def main() -> None:
    st.title("Sector Earnings Monitor")
    st.caption(
        "Sum of key income statement lines by sector. Growth rates are calculated using only the companies that "
        "have reported in the selected period."
    )

    try:
        load_engine()
    except MissingDatabaseURL as err:
        st.error(str(err))
        st.stop()

    sector_map = load_sector_map()

    frequency = st.radio("Data frequency", list(FREQUENCY_CONFIG.keys()), horizontal=True)
    level = st.radio("Sector granularity", ["L1", "L2"], index=0, horizontal=True)

    available_periods = load_period_options(frequency)
    if not available_periods:
        st.warning("No reporting periods available for the selected frequency.")
        st.stop()

    selected_period = st.selectbox("Reporting period", available_periods, index=0)

    comparison_periods: ComparisonPeriods = determine_comparison_periods(frequency, selected_period)
    periods_to_fetch = [selected_period]
    if comparison_periods.previous:
        periods_to_fetch.append(comparison_periods.previous)
    if comparison_periods.yoy:
        periods_to_fetch.append(comparison_periods.yoy)

    raw_financials = load_financial_snapshot(frequency, periods_to_fetch)

    if raw_financials.empty:
        st.warning("No financial data found for the selected period.")
        st.stop()

    summary = summarise_by_sector(
        raw_financials=raw_financials,
        sector_map=sector_map,
        frequency=frequency,
        period=selected_period,
        level=level,
    )

    released_count = summary.get("released_count", 0)
    total_count = summary.get("total_count", 0)
    coverage_pct = (released_count / total_count * 100) if total_count else 0.0

    meta_col1, meta_col2, meta_col3 = st.columns(3)
    meta_col1.metric("Companies reported", f"{released_count:,}")
    meta_col2.metric("Total coverage", f"{total_count:,}")
    meta_col3.metric("Release coverage", f"{coverage_pct:.0f}%")

    result_df = summary.get("data", pd.DataFrame())
    if result_df.empty:
        st.info("No companies have reported for the selected configuration yet.")
        st.stop()

    sector_column = level
    formatted_df = _format_display(result_df, sector_column)
    st.dataframe(
        formatted_df,
        use_container_width=True,
        hide_index=True,
        column_config=_build_column_config(sector_column),
    )

    st.caption(
        "Values shown in billions of VND. QoQ compares with the previous quarter (annual view uses previous year). "
        "YoY compares with the same quarter or year one year earlier."
    )


if __name__ == "__main__":
    main()
