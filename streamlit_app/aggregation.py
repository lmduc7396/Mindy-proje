"""Business logic for sector-level earnings aggregation and growth calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


METRIC_CONFIG = (
    ("Revenue", "Net_Revenue"),
    ("Gross Profit", "Gross_Profit"),
    ("EBITDA", "EBITDA"),
    ("EBIT", "EBIT"),
    ("NPATMI", "NPATMI"),
)

FREQUENCY_CONFIG = {
    "Quarterly": {
        "table": "FA_Quarterly",
        "date_column": "DATE",
        "previous_offset": 1,
        "yoy_offset": 4,
        "parser": "quarter",
    },
    "Annual": {
        "table": "FA_Annual",
        "date_column": "DATE",
        "previous_offset": 1,
        "yoy_offset": 1,
        "parser": "year",
    },
}


@dataclass(frozen=True)
class ComparisonPeriods:
    current: str
    previous: Optional[str]
    yoy: Optional[str]


def metric_labels() -> List[str]:
    return [label for label, _ in METRIC_CONFIG]


def metric_keycodes() -> List[str]:
    return [key for _, key in METRIC_CONFIG]


def _parse_quarter(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})Q([1-4])", period)
    if not match:
        raise ValueError(f"Invalid quarter format: {period}")
    year, quarter = int(match.group(1)), int(match.group(2))
    return year, quarter


def _format_quarter(year: int, quarter: int) -> str:
    return f"{year}Q{quarter}"


def _shift_quarter(period: str, offset: int) -> Optional[str]:
    year, quarter = _parse_quarter(period)
    quarter -= offset
    while quarter <= 0:
        quarter += 4
        year -= 1
        if year < 1900:
            return None
    while quarter > 4:
        quarter -= 4
        year += 1
    return _format_quarter(year, quarter)


def _parse_year(period: str) -> int:
    if not period or not period.isdigit():
        raise ValueError(f"Invalid year format: {period}")
    return int(period)


def _format_year(year: int) -> str:
    return str(year)


def _shift_year(period: str, offset: int) -> Optional[str]:
    year = _parse_year(period) - offset
    if year < 1900:
        return None
    return _format_year(year)


def determine_comparison_periods(frequency: str, current_period: str) -> ComparisonPeriods:
    config = FREQUENCY_CONFIG[frequency]
    parser = config["parser"]

    if parser == "quarter":
        previous = _shift_quarter(current_period, config["previous_offset"])
        yoy = _shift_quarter(current_period, config["yoy_offset"])
    else:
        previous = _shift_year(current_period, config["previous_offset"])
        yoy = _shift_year(current_period, config["yoy_offset"])

    return ComparisonPeriods(current=current_period, previous=previous, yoy=yoy)


def _period_sort_key(frequency: str, period: str) -> tuple[int, int]:
    if FREQUENCY_CONFIG[frequency]["parser"] == "quarter":
        year, quarter = _parse_quarter(period)
        return year, quarter
    return _parse_year(period), 0


def sort_periods(periods: Iterable[str], frequency: str, descending: bool = True) -> List[str]:
    return sorted(
        periods,
        key=lambda value: _period_sort_key(frequency, value),
        reverse=descending,
    )


def _pivot_financials(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        columns = [
            "Ticker",
            "PERIOD",
            "Sector",
            "L1",
            "L2",
        ] + metric_labels()
        return pd.DataFrame(columns=columns)

    pivoted = (
        raw_df
        .pivot_table(
            index=["Ticker", "PERIOD", "Sector", "L1", "L2"],
            columns="KEYCODE",
            values="VALUE",
            aggfunc="first",
        )
        .reset_index()
    )

    rename_map = {key: label for label, key in METRIC_CONFIG}
    pivoted = pivoted.rename(columns=rename_map)

    for label in metric_labels():
        if label not in pivoted.columns:
            pivoted[label] = np.nan

    pivoted[metric_labels()] = pivoted[metric_labels()].apply(pd.to_numeric, errors="coerce")

    return pivoted


def _aggregate_period(
    pivoted_df: pd.DataFrame,
    period: Optional[str],
    sector_column: str,
    metric_cols: List[str],
    tickers: Iterable[str],
) -> pd.DataFrame:
    if not period:
        empty = pd.DataFrame({sector_column: []})
        for column in metric_cols:
            empty[column] = []
        return empty

    tickers = set(tickers)
    period_df = pivoted_df[(pivoted_df["PERIOD"] == period) & (pivoted_df["Ticker"].isin(tickers))]
    if period_df.empty:
        empty = pd.DataFrame({sector_column: []})
        for column in metric_cols:
            empty[column] = []
        return empty

    aggregated = (
        period_df
        .groupby(sector_column, dropna=False)[metric_cols]
        .sum(min_count=1)
        .reset_index()
    )
    aggregated[metric_cols] = aggregated[metric_cols].apply(pd.to_numeric, errors="coerce")
    return aggregated


def _compute_growth(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    sector_column: str,
    metric_cols: List[str],
    suffix: str,
) -> pd.DataFrame:
    if current_df.empty:
        return pd.DataFrame(columns=[sector_column] + [f"{col}_{suffix}" for col in metric_cols])

    current = current_df.set_index(sector_column)
    current_numeric = current.apply(pd.to_numeric, errors="coerce")

    if comparison_df.empty:
        comparison_numeric = pd.DataFrame(index=current_numeric.index, columns=metric_cols)
    else:
        comparison = comparison_df.set_index(sector_column)
        comparison = comparison.reindex(current.index)
        comparison_numeric = comparison.apply(pd.to_numeric, errors="coerce")
        comparison_numeric = comparison_numeric.reindex(current_numeric.index)

    records: List[Dict[str, float | str]] = []
    for sector_label, current_row in current_numeric.iterrows():
        record: Dict[str, float | str] = {sector_column: sector_label}
        comparison_row = comparison_numeric.loc[sector_label] if sector_label in comparison_numeric.index else pd.Series(dtype=float)

        for metric in metric_cols:
            current_value = current_row.get(metric)
            comparison_value = comparison_row.get(metric) if not comparison_row.empty else np.nan

            if isinstance(current_value, pd.Series):
                current_value = current_value.iloc[0]
            if isinstance(comparison_value, pd.Series):
                comparison_value = comparison_value.iloc[0]

            if comparison_value is None or pd.isna(comparison_value) or comparison_value == 0:
                record[f"{metric}_{suffix}"] = np.nan
            else:
                record[f"{metric}_{suffix}"] = (current_value - comparison_value) / comparison_value

        records.append(record)

    return pd.DataFrame(records)


def summarise_by_sector(
    raw_financials: pd.DataFrame,
    sector_map: pd.DataFrame,
    frequency: str,
    period: str,
    level: str,
) -> Dict[str, pd.DataFrame | int | float]:
    sector_column = level
    metric_cols = metric_labels()

    def _sum_metrics(frame: pd.DataFrame) -> pd.Series:
        if frame.empty:
            return pd.Series({metric: np.nan for metric in metric_cols})
        summed = frame[metric_cols].sum(axis=0, min_count=1)
        return summed.reindex(metric_cols)

    pivoted = _pivot_financials(raw_financials)
    current_period_df = pivoted[pivoted["PERIOD"] == period]
    if current_period_df.empty:
        return {
            "data": pd.DataFrame(),
            "released_count": 0,
            "total_count": int(sector_map["Ticker"].nunique()) if not sector_map.empty else 0,
        }

    released_mask = current_period_df[metric_cols].notna().any(axis=1)
    released_df = current_period_df[released_mask]
    released_tickers = released_df["Ticker"].unique()

    current_summary = (
        released_df
        .groupby(sector_column, dropna=False)[metric_cols]
        .sum(min_count=1)
        .reset_index()
    )
    current_summary[metric_cols] = current_summary[metric_cols].apply(pd.to_numeric, errors="coerce")

    counts = (
        released_df
        .groupby(sector_column, dropna=False)["Ticker"]
        .nunique()
        .reset_index(name="released_companies")
    )

    total_counts = (
        sector_map.groupby(sector_column, dropna=False)["Ticker"].nunique().reset_index(name="total_companies")
    )

    comparison_periods = determine_comparison_periods(frequency, period)

    previous_summary = _aggregate_period(
        pivoted,
        comparison_periods.previous,
        sector_column,
        metric_cols,
        released_tickers,
    )
    if not previous_summary.empty:
        previous_summary[metric_cols] = previous_summary[metric_cols].apply(pd.to_numeric, errors="coerce")

    yoy_summary = _aggregate_period(
        pivoted,
        comparison_periods.yoy,
        sector_column,
        metric_cols,
        released_tickers,
    )
    if not yoy_summary.empty:
        yoy_summary[metric_cols] = yoy_summary[metric_cols].apply(pd.to_numeric, errors="coerce")

    qoq_growth = _compute_growth(current_summary, previous_summary, sector_column, metric_cols, "QoQ")
    yoy_growth = _compute_growth(current_summary, yoy_summary, sector_column, metric_cols, "YoY")

    output = current_summary.merge(counts, on=sector_column, how="left")
    output = output.merge(total_counts, on=sector_column, how="left")
    output = output.merge(qoq_growth, on=sector_column, how="left")
    output = output.merge(yoy_growth, on=sector_column, how="left")

    coverage = output[["released_companies", "total_companies"]].copy()
    output["coverage_pct"] = coverage["released_companies"].astype(float) / coverage["total_companies"].replace({0: np.nan})

    totals_metrics = _sum_metrics(current_summary)
    totals_previous = _sum_metrics(previous_summary)
    totals_yoy = _sum_metrics(yoy_summary)

    total_released = int(len(released_tickers))
    total_universe = int(sector_map["Ticker"].nunique()) if not sector_map.empty else 0

    total_row: Dict[str, float | str] = {sector_column: "Total"}
    for metric in metric_cols:
        current_value = totals_metrics.get(metric)
        total_row[metric] = current_value

        prev_value = totals_previous.get(metric)
        if pd.notna(current_value) and pd.notna(prev_value) and prev_value != 0:
            total_row[f"{metric}_QoQ"] = (current_value - prev_value) / prev_value
        else:
            total_row[f"{metric}_QoQ"] = np.nan

        yoy_value = totals_yoy.get(metric)
        if pd.notna(current_value) and pd.notna(yoy_value) and yoy_value != 0:
            total_row[f"{metric}_YoY"] = (current_value - yoy_value) / yoy_value
        else:
            total_row[f"{metric}_YoY"] = np.nan

    total_row["released_companies"] = total_released
    total_row["total_companies"] = total_universe
    total_row["coverage_pct"] = (total_released / total_universe) if total_universe else np.nan

    total_df = pd.DataFrame([total_row])
    total_df = total_df.reindex(columns=output.columns)
    output = pd.concat([total_df, output], ignore_index=True)

    released_count = int(len(released_tickers))
    total_count = int(sector_map["Ticker"].nunique()) if not sector_map.empty else 0

    return {
        "data": output,
        "released_count": released_count,
        "total_count": total_count,
    }
