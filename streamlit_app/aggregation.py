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
    comparison = comparison_df.set_index(sector_column) if not comparison_df.empty else None

    if comparison is None:
        growth = pd.DataFrame(index=current.index, columns=metric_cols, dtype=float)
    else:
        comparison = comparison.reindex(current.index)
        growth = (current - comparison) / comparison

    growth = growth.replace([np.inf, -np.inf], np.nan)
    growth = growth.rename(columns={col: f"{col}_{suffix}" for col in metric_cols})
    return growth.reset_index()


def summarise_by_sector(
    raw_financials: pd.DataFrame,
    sector_map: pd.DataFrame,
    frequency: str,
    period: str,
    level: str,
) -> Dict[str, pd.DataFrame | int | float]:
    sector_column = level
    metric_cols = metric_labels()

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

    yoy_summary = _aggregate_period(
        pivoted,
        comparison_periods.yoy,
        sector_column,
        metric_cols,
        released_tickers,
    )

    qoq_growth = _compute_growth(current_summary, previous_summary, sector_column, metric_cols, "QoQ")
    yoy_growth = _compute_growth(current_summary, yoy_summary, sector_column, metric_cols, "YoY")

    output = current_summary.merge(counts, on=sector_column, how="left")
    output = output.merge(total_counts, on=sector_column, how="left")
    output = output.merge(qoq_growth, on=sector_column, how="left")
    output = output.merge(yoy_growth, on=sector_column, how="left")

    coverage = output[["released_companies", "total_companies"]].copy()
    output["coverage_pct"] = coverage["released_companies"].astype(float) / coverage["total_companies"].replace({0: np.nan})

    released_count = int(len(released_tickers))
    total_count = int(sector_map["Ticker"].nunique()) if not sector_map.empty else 0

    return {
        "data": output,
        "released_count": released_count,
        "total_count": total_count,
    }
