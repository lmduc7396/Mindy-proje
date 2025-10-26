from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from streamlit_app.aggregation import (
    FREQUENCY_CONFIG,
    determine_comparison_periods,
    metric_labels,
    _pivot_financials,
)
from streamlit_app.cached_data import (
    load_financial_snapshot,
    load_period_options,
    load_sector_map,
)
from streamlit_app.data_access import MissingDatabaseURL


st.title("Earnings Surprises")
st.caption(
    "Identify tickers delivering standout earnings momentum or disappointments. "
    "Growth calculations use only the companies with data in the selected period and comparison." 
)


def _compute_ticker_growth(
    pivoted: pd.DataFrame,
    metric: str,
    period: str,
    previous: str | None,
    yoy: str | None,
) -> pd.DataFrame:
    metric_cols = ["Ticker", "Sector", "L1", "L2", metric]

    current = pivoted[pivoted["PERIOD"] == period]
    current = current[metric_cols].dropna(subset=[metric]).copy()
    if current.empty:
        return pd.DataFrame(columns=metric_cols + ["prev_value", "yoy_value", "qoq_growth", "yoy_growth"])

    current = current.rename(columns={metric: "current_value"})

    if previous:
        prev_df = pivoted[pivoted["PERIOD"] == previous][["Ticker", metric]].rename(columns={metric: "prev_value"})
        current = current.merge(prev_df, on="Ticker", how="left")
    else:
        current["prev_value"] = np.nan

    if yoy:
        yoy_df = pivoted[pivoted["PERIOD"] == yoy][["Ticker", metric]].rename(columns={metric: "yoy_value"})
        current = current.merge(yoy_df, on="Ticker", how="left")
    else:
        current["yoy_value"] = np.nan

    def _growth(curr: pd.Series, base: pd.Series) -> pd.Series:
        with np.errstate(divide="ignore", invalid="ignore"):
            growth = (curr - base) / base
        growth[(base.isna()) | (base == 0)] = np.nan
        return growth

    current["qoq_growth"] = _growth(current["current_value"], current["prev_value"])
    current["yoy_growth"] = _growth(current["current_value"], current["yoy_value"])

    current["qoq_rank"] = current["qoq_growth"].rank(ascending=False, method="average", pct=True)
    current["yoy_rank"] = current["yoy_growth"].rank(ascending=False, method="average", pct=True)
    current["combined_score"] = np.nanmean(current[["qoq_rank", "yoy_rank"]].to_numpy(), axis=1)

    return current


def _prepare_rank_table(df: pd.DataFrame, top_n: int, ascending: bool, min_base: float) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    filtered = df.copy()
    filtered["abs_base"] = filtered["current_value"].abs()
    filtered = filtered[filtered["abs_base"] >= min_base]
    filtered = filtered[filtered["combined_score"].notna()]
    if filtered.empty:
        return pd.DataFrame()

    filtered = filtered.sort_values(
        by=["combined_score", "abs_base", "current_value"],
        ascending=[ascending, False, False],
    ).head(top_n)

    filtered["Metric (bn VND)"] = filtered["current_value"] / 1e9
    filtered["QoQ Growth %"] = filtered["qoq_growth"] * 100
    filtered["YoY Growth %"] = filtered["yoy_growth"] * 100

    display_columns = [
        "Ticker",
        "Sector",
        "L2",
        "Metric (bn VND)",
        "QoQ Growth %",
        "YoY Growth %",
    ]
    return filtered[display_columns]


def main() -> None:
    try:
        sector_map = load_sector_map()
    except MissingDatabaseURL as err:
        st.error(str(err))
        return

    frequency = st.radio("Data frequency", list(FREQUENCY_CONFIG.keys()), horizontal=True)
    available_periods = load_period_options(frequency)
    if not available_periods:
        st.warning("No reporting periods available for the selected frequency.")
        return

    selected_period = st.selectbox("Reporting period", available_periods, index=0)
    col_controls = st.columns(2)
    with col_controls[0]:
        min_base_bn = st.number_input(
            "Minimum earnings base (bn VND)",
            min_value=0.0,
            value=200.0,
            step=50.0,
            help="Only tickers with current-period earnings above this threshold are ranked."
        )
    with col_controls[1]:
        top_n = st.slider(
            "Results per list",
            min_value=5,
            max_value=25,
            value=10,
            step=1,
        )

    comparison_periods = determine_comparison_periods(frequency, selected_period)
    periods_to_fetch = [selected_period]
    if comparison_periods.previous:
        periods_to_fetch.append(comparison_periods.previous)
    if comparison_periods.yoy:
        periods_to_fetch.append(comparison_periods.yoy)

    raw_financials = load_financial_snapshot(frequency, periods_to_fetch)
    if raw_financials.empty:
        st.info("No financial data found for the selected configuration.")
        return

    pivoted = _pivot_financials(raw_financials)

    min_base_value = min_base_bn * 1e9

    metrics = metric_labels()

    def _display_table(title: str, df: pd.DataFrame) -> None:
        st.subheader(title)
        if df.empty:
            st.write("No tickers meet the filters.")
            return
        column_config = {
            "Metric (bn VND)": st.column_config.NumberColumn("Metric (bn VND)", format="%.1f"),
            "QoQ Growth %": st.column_config.NumberColumn("QoQ Growth", format="%.1f%%"),
            "YoY Growth %": st.column_config.NumberColumn("YoY Growth", format="%.1f%%"),
        }
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={k: v for k, v in column_config.items() if k in df.columns},
        )

    for metric in metrics:
        st.markdown(f"### {metric} Surprises")

        growth_df = _compute_ticker_growth(
            pivoted,
            metric=metric,
            period=selected_period,
            previous=comparison_periods.previous,
            yoy=comparison_periods.yoy,
        )

        if growth_df.empty:
            st.write("No tickers with available data for this metric.")
            continue

        best = _prepare_rank_table(growth_df, top_n, ascending=False, min_base=min_base_value)
        worst = _prepare_rank_table(growth_df, top_n, ascending=True, min_base=min_base_value)

        cols = st.columns(2)
        with cols[0]:
            _display_table("Top Combined Growth", best)
        with cols[1]:
            _display_table("Worst Combined Growth", worst)

    st.caption(
        "Combined ranking averages percentile ranks for QoQ and YoY growth, then orders tickers by score and earnings base."
    )


if __name__ == "__main__":
    main()
