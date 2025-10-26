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
    summarise_by_sector,
)
from streamlit_app.cached_data import (
    load_engine,
    load_financial_snapshot,
    load_period_options,
    load_sector_map,
)
from streamlit_app.data_access import MissingDatabaseURL


st.set_page_config(page_title="Sector Earnings Monitor", layout="wide")


def _format_display(df: pd.DataFrame, sector_column: str) -> pd.DataFrame:
    formatted = df.copy()

    earnings_metrics = metric_labels()
    for metric in earnings_metrics:
        if metric in formatted.columns:
            metric_series = formatted[metric]
            if metric_series.dtype == object:
                metric_series = metric_series.astype(str).str.replace(",", "", regex=False)
            metric_values = pd.to_numeric(metric_series, errors="coerce")
            formatted[metric] = metric_values / 1e9

        qoq_col = f"{metric}_QoQ"
        yoy_col = f"{metric}_YoY"
        if qoq_col in formatted.columns:
            qoq_series = formatted[qoq_col]
            if qoq_series.dtype == object:
                qoq_series = qoq_series.astype(str).str.replace("%", "", regex=False)
            formatted[qoq_col] = pd.to_numeric(qoq_series, errors="coerce") * 100
        if yoy_col in formatted.columns:
            yoy_series = formatted[yoy_col]
            if yoy_series.dtype == object:
                yoy_series = yoy_series.astype(str).str.replace("%", "", regex=False)
            formatted[yoy_col] = pd.to_numeric(yoy_series, errors="coerce") * 100

    if "coverage_pct" in formatted.columns:
        coverage_series = formatted["coverage_pct"]
        if coverage_series.dtype == object:
            coverage_series = coverage_series.astype(str).str.replace("%", "", regex=False)
        formatted["coverage_pct"] = pd.to_numeric(coverage_series, errors="coerce") * 100

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
