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

    return current


def _prepare_rank_table(df: pd.DataFrame, growth_column: str, top_n: int, ascending: bool, min_base: float) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    filtered = df.copy()
    filtered["abs_base"] = filtered["current_value"].abs()
    filtered = filtered[filtered["abs_base"] >= min_base]
    filtered = filtered[filtered[growth_column].notna()]
    if filtered.empty:
        return pd.DataFrame()

    filtered = filtered.sort_values(
        by=[growth_column, "abs_base", "current_value"],
        ascending=[ascending, False, False],
    ).head(top_n)

    filtered["Metric (bn VND)"] = filtered["current_value"] / 1e9
    filtered[f"{growth_column}_pct"] = filtered[growth_column] * 100

    display_columns = [
        "Ticker",
        "Sector",
        "L1",
        "Metric (bn VND)",
        f"{growth_column}_pct",
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
    metric_options = metric_labels()
    selected_metric = st.selectbox("Metric", metric_options, index=0)

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

    growth_df = _compute_ticker_growth(
        pivoted,
        metric=selected_metric,
        period=selected_period,
        previous=comparison_periods.previous,
        yoy=comparison_periods.yoy,
    )

    if growth_df.empty:
        st.info("No tickers with available data for the selected metric and period.")
        return

    min_base_value = min_base_bn * 1e9

    top_qoq = _prepare_rank_table(growth_df, "qoq_growth", top_n, ascending=False, min_base=min_base_value)
    worst_qoq = _prepare_rank_table(growth_df, "qoq_growth", top_n, ascending=True, min_base=min_base_value)
    top_yoy = _prepare_rank_table(growth_df, "yoy_growth", top_n, ascending=False, min_base=min_base_value)
    worst_yoy = _prepare_rank_table(growth_df, "yoy_growth", top_n, ascending=True, min_base=min_base_value)

    def _display_table(title: str, df: pd.DataFrame) -> None:
        st.subheader(title)
        if df.empty:
            st.write("No tickers meet the filters.")
            return
        column_config = {
            "Metric (bn VND)": st.column_config.NumberColumn("Metric (bn VND)", format="%.1f"),
            "qoq_growth_pct": st.column_config.NumberColumn("QoQ Growth", format="%.1f%%"),
            "yoy_growth_pct": st.column_config.NumberColumn("YoY Growth", format="%.1f%%"),
        }
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={k: v for k, v in column_config.items() if k in df.columns},
        )

    st.markdown("### Quarter-on-Quarter Surprises")
    qo_cols = st.columns(2)
    with qo_cols[0]:
        _display_table(f"Top QoQ by {selected_metric}", top_qoq)
    with qo_cols[1]:
        _display_table(f"Worst QoQ by {selected_metric}", worst_qoq)

    st.markdown("### Year-on-Year Surprises")
    yo_cols = st.columns(2)
    with yo_cols[0]:
        _display_table(f"Top YoY by {selected_metric}", top_yoy)
    with yo_cols[1]:
        _display_table(f"Worst YoY by {selected_metric}", worst_yoy)

    st.caption(
        "Ranking ties are broken by the absolute earnings base in the current period. "
        "Tickers without valid comparison values are excluded from each list."
    )


if __name__ == "__main__":
    main()
