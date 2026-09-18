"""Parsing and comparison helpers for fiscal-year.quarter period strings, e.g. "FY28.Q3"."""

from __future__ import annotations

import re


class PeriodError(ValueError):
    pass


def _pattern(fiscal_year_prefix: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(fiscal_year_prefix)}(\d+)\.Q(\d+)$")


def parse_period(period: str, fiscal_year_prefix: str = "FY") -> tuple[int, int]:
    """Parse "FY28.Q3" -> (28, 3). Raises PeriodError on malformed input."""
    match = _pattern(fiscal_year_prefix).match(period.strip())
    if not match:
        raise PeriodError(
            f"Invalid period '{period}': expected format '{fiscal_year_prefix}<year>.Q<quarter>', "
            f"e.g. '{fiscal_year_prefix}28.Q3'"
        )
    year, quarter = int(match.group(1)), int(match.group(2))
    if quarter < 1:
        raise PeriodError(f"Invalid period '{period}': quarter must be >= 1")
    return year, quarter


def period_sort_key(period: str, fiscal_year_prefix: str = "FY") -> tuple[int, int]:
    return parse_period(period, fiscal_year_prefix)


def period_index(
    period: str,
    start: str,
    fiscal_year_prefix: str = "FY",
    quarters_per_year: int = 4,
) -> int:
    """0-based column index of `period` relative to `start`, in units of quarters."""
    year, quarter = parse_period(period, fiscal_year_prefix)
    start_year, start_quarter = parse_period(start, fiscal_year_prefix)
    return (year - start_year) * quarters_per_year + (quarter - start_quarter)


def total_quarters(
    start: str,
    end: str,
    fiscal_year_prefix: str = "FY",
    quarters_per_year: int = 4,
) -> int:
    """Number of quarter columns spanned by [start, end], inclusive."""
    end_index = period_index(end, start, fiscal_year_prefix, quarters_per_year)
    if end_index < 0:
        raise PeriodError(f"Timeline end '{end}' is before start '{start}'")
    return end_index + 1


def period_at_index(
    start: str,
    index: int,
    fiscal_year_prefix: str = "FY",
    quarters_per_year: int = 4,
) -> tuple[int, int]:
    """Inverse of period_index: the (year, quarter) at 0-based column `index` from `start`."""
    start_year, start_quarter = parse_period(start, fiscal_year_prefix)
    total = start_quarter - 1 + index
    year = start_year + total // quarters_per_year
    quarter = total % quarters_per_year + 1
    return year, quarter


def period_in_range(
    period: str,
    start: str,
    end: str,
    fiscal_year_prefix: str = "FY",
    quarters_per_year: int = 4,
) -> bool:
    index = period_index(period, start, fiscal_year_prefix, quarters_per_year)
    span = total_quarters(start, end, fiscal_year_prefix, quarters_per_year)
    return 0 <= index < span
