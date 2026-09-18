import pytest

from argenerator.period import (
    PeriodError,
    parse_period,
    period_at_index,
    period_in_range,
    period_index,
    total_quarters,
)


def test_parse_period():
    assert parse_period("FY28.Q3") == (28, 3)


def test_parse_period_invalid():
    with pytest.raises(PeriodError):
        parse_period("2028-Q3")


def test_parse_period_zero_quarter():
    with pytest.raises(PeriodError):
        parse_period("FY28.Q0")


def test_period_index_same_year():
    assert period_index("FY27.Q3", "FY27.Q1") == 2


def test_period_index_across_year_boundary():
    assert period_index("FY28.Q1", "FY27.Q4") == 1
    assert period_index("FY28.Q1", "FY27.Q1") == 4


def test_period_at_index_is_inverse_of_period_index():
    start = "FY27.Q2"
    for idx in range(10):
        year, quarter = period_at_index(start, idx)
        period = f"FY{year}.Q{quarter}"
        assert period_index(period, start) == idx


def test_total_quarters():
    assert total_quarters("FY27.Q1", "FY27.Q4") == 4
    assert total_quarters("FY27.Q1", "FY30.Q4") == 16


def test_total_quarters_end_before_start_raises():
    with pytest.raises(PeriodError):
        total_quarters("FY28.Q1", "FY27.Q1")


def test_period_in_range():
    assert period_in_range("FY27.Q1", "FY27.Q1", "FY27.Q4")
    assert period_in_range("FY27.Q4", "FY27.Q1", "FY27.Q4")
    assert not period_in_range("FY28.Q1", "FY27.Q1", "FY27.Q4")
    assert not period_in_range("FY26.Q4", "FY27.Q1", "FY27.Q4")
