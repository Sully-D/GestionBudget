import calendar
from datetime import date, timedelta


def _clamped_day(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


def _add_month(year: int, month: int) -> tuple[int, int]:
    return (year, month + 1) if month < 12 else (year + 1, 1)


def _sub_month(year: int, month: int) -> tuple[int, int]:
    return (year, month - 1) if month > 1 else (year - 1, 12)


def period_for(start_day: int, reference_date: date) -> tuple[date, date]:
    year, month = reference_date.year, reference_date.month
    day_this_month = _clamped_day(year, month, start_day)

    if reference_date.day >= day_this_month:
        period_start = date(year, month, day_this_month)
    else:
        prev_year, prev_month = _sub_month(year, month)
        prev_day = _clamped_day(prev_year, prev_month, start_day)
        period_start = date(prev_year, prev_month, prev_day)

    next_year, next_month = _add_month(period_start.year, period_start.month)
    next_day = _clamped_day(next_year, next_month, start_day)
    next_period_start = date(next_year, next_month, next_day)
    period_end = next_period_start - timedelta(days=1)

    return period_start, period_end
