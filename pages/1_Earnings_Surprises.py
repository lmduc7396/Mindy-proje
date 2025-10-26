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

st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1400px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
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

    current["qoq_rank"] = current["qoq_growth"].rank(ascending=True, method="average", pct=True)
    current["yoy_rank"] = current["yoy_growth"].rank(ascending=True, method="average", pct=True)
    current["metric_score"] = np.nanmean(current[["qoq_rank", "yoy_rank"]].to_numpy(), axis=1)

    return current


def _prepare_rank_table(df: pd.DataFrame, top_n: int, ascending: bool, min_base: float) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    table = df.copy()
    table = table[table["base_value"].notna()]
    table = table[table["base_value"] >= min_base]
    table = table[table["combined_score"].notna()]
    if table.empty:
        return pd.DataFrame()

    sort_columns = ["combined_score", "base_value", "Revenue_current", "NPATMI_current"]
    ascending_flags = [ascending, False, False, False]
    existing_columns = [col for col in sort_columns if col in table.columns]
    existing_flags = ascending_flags[: len(existing_columns)]

    table = table.sort_values(
        by=existing_columns,
        ascending=existing_flags,
        kind="mergesort",
    ).head(top_n)

    if "Revenue_current" in table.columns:
        table["Revenue (bn VND)"] = table["Revenue_current"] / 1e9
        table["Revenue QoQ %"] = table["Revenue_qoq"] * 100
        table["Revenue YoY %"] = table["Revenue_yoy"] * 100
    else:
        table["Revenue (bn VND)"] = np.nan
        table["Revenue QoQ %"] = np.nan
        table["Revenue YoY %"] = np.nan

    if "NPATMI_current" in table.columns:
        table["NPATMI (bn VND)"] = table["NPATMI_current"] / 1e9
        table["NPATMI QoQ %"] = table["NPATMI_qoq"] * 100
        table["NPATMI YoY %"] = table["NPATMI_yoy"] * 100
    else:
        table["NPATMI (bn VND)"] = np.nan
        table["NPATMI QoQ %"] = np.nan
        table["NPATMI YoY %"] = np.nan

    display_columns = [
        "Ticker",
        "Sector",
        "L2",
        "Revenue (bn VND)",
        "Revenue QoQ %",
        "Revenue YoY %",
        "NPATMI (bn VND)",
        "NPATMI QoQ %",
        "NPATMI YoY %",
    ]

    return table[display_columns]


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

    def _display_table(title: str, df: pd.DataFrame) -> None:
        st.subheader(title)
        if df.empty:
            st.write("No tickers meet the filters.")
            return
        column_config = {
            "Revenue (bn VND)": st.column_config.NumberColumn("Revenue (bn VND)", format="%.1f"),
            "Revenue QoQ %": st.column_config.NumberColumn("Revenue QoQ", format="%.1f%%"),
            "Revenue YoY %": st.column_config.NumberColumn("Revenue YoY", format="%.1f%%"),
            "NPATMI (bn VND)": st.column_config.NumberColumn("NPATMI (bn VND)", format="%.1f"),
            "NPATMI QoQ %": st.column_config.NumberColumn("NPATMI QoQ", format="%.1f%%"),
            "NPATMI YoY %": st.column_config.NumberColumn("NPATMI YoY", format="%.1f%%"),
        }
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={k: v for k, v in column_config.items() if k in df.columns},
        )

    metrics = metric_labels()
    metric_frames: list[pd.DataFrame] = []

    for metric in metrics:
        growth_df = _compute_ticker_growth(
            pivoted,
            metric=metric,
            period=selected_period,
            previous=comparison_periods.previous,
            yoy=comparison_periods.yoy,
        )

        if growth_df.empty:
            continue

        prefix = metric.upper().replace(" ", "_")
        renamed = growth_df.rename(
            columns={
                "current_value": f"{prefix}_current",
                "qoq_growth": f"{prefix}_qoq",
                "yoy_growth": f"{prefix}_yoy",
                "metric_score": f"{prefix}_score",
            }
        )
        renamed = renamed[
            ["Ticker", f"{prefix}_current", f"{prefix}_qoq", f"{prefix}_yoy", f"{prefix}_score"]
        ]
        renamed = renamed.set_index("Ticker")
        metric_frames.append(renamed)

    if not metric_frames:
        st.info("No tickers with available growth data for the selected configuration.")
        return

    combined_growth = pd.concat(metric_frames, axis=1, join="outer")
    combined_growth = combined_growth.reset_index()

    sector_info = sector_map[["Ticker", "Sector", "L2"]].drop_duplicates()
    combined_growth = combined_growth.merge(sector_info, on="Ticker", how="left")

    score_columns = [col for col in combined_growth.columns if col.endswith("_score")]
    if score_columns:
        combined_growth["combined_score"] = combined_growth[score_columns].mean(axis=1, skipna=True)
    else:
        combined_growth["combined_score"] = np.nan

    value_columns = [col for col in combined_growth.columns if col.endswith("_current")]
    if value_columns:
        combined_growth["base_value"] = combined_growth[value_columns].abs().max(axis=1, skipna=True)
    else:
        combined_growth["base_value"] = np.nan

    combined_growth = combined_growth.dropna(subset=value_columns, how="all")

    # Normalize column names for downstream display
    rename_map = {
        "REVENUE_current": "Revenue_current",
        "REVENUE_qoq": "Revenue_qoq",
        "REVENUE_yoy": "Revenue_yoy",
        "REVENUE_score": "Revenue_score",
        "NPATMI_current": "NPATMI_current",
        "NPATMI_qoq": "NPATMI_qoq",
        "NPATMI_yoy": "NPATMI_yoy",
        "NPATMI_score": "NPATMI_score",
    }
    combined_growth = combined_growth.rename(columns=rename_map)

    best = _prepare_rank_table(combined_growth, top_n, ascending=False, min_base=min_base_value)
    worst = _prepare_rank_table(combined_growth, top_n, ascending=True, min_base=min_base_value)

    _display_table("Positive Surprises", best)
    _display_table("Negative Surprises", worst)

    st.caption(
        "Combined ranking averages percentile ranks for QoQ and YoY growth, then orders tickers by score and earnings base."
    )


if __name__ == "__main__":
    main()
