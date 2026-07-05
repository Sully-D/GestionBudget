from datetime import date

from app.core.period import period_for


def test_period_for_nominal_case():
    assert period_for(15, date(2026, 7, 20)) == (date(2026, 7, 15), date(2026, 8, 14))


def test_period_for_reference_date_before_start_day_straddles_previous_month():
    assert period_for(15, date(2026, 7, 10)) == (date(2026, 6, 15), date(2026, 7, 14))


def test_period_for_start_day_clamped_to_last_day_of_shorter_month():
    # start_day=30 clamped to 28 in February 2026 (non-leap year)
    assert period_for(30, date(2026, 2, 15)) == (date(2026, 1, 30), date(2026, 2, 27))


def test_period_for_reference_date_on_clamped_boundary():
    assert period_for(30, date(2026, 2, 28)) == (date(2026, 2, 28), date(2026, 3, 29))


def test_period_for_start_day_31_clamped_in_30_day_month():
    assert period_for(31, date(2026, 4, 15)) == (date(2026, 3, 31), date(2026, 4, 29))


def test_period_for_start_day_clamped_to_29_in_leap_year_february():
    # 2028 is a leap year: start_day=30 clamps to 29 in February 2028
    assert period_for(30, date(2028, 2, 15)) == (date(2028, 1, 30), date(2028, 2, 28))
