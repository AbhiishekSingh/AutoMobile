from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Indian Standard Time (UTC+5:30). We store business timestamps as IST wall-clock
# so the values in the database read directly as Indian time.
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current time in IST, as a naive datetime (no tzinfo) for `timestamp` columns."""
    return datetime.now(IST).replace(tzinfo=None)


def period_range(period: str) -> tuple[datetime, datetime]:
    """Calendar-based [start, end) datetime range for a dashboard `period` filter.

    - "today": from today 00:00 (IST) up to (but not including) tomorrow 00:00.
    - "week":  from this week's Monday 00:00 up to next Monday 00:00.
    - "month": from the 1st of this month 00:00 up to the 1st of next month.
    - "year":  from Jan 1 this year 00:00 up to Jan 1 next year.

    Falls back to "today" for any unrecognised value so callers never get an
    unbounded/None range by mistake.
    """
    now = now_ist()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "week":
        start = start_of_today - timedelta(days=start_of_today.weekday())  # Monday
        end = start + timedelta(days=7)
    elif period == "month":
        start = start_of_today.replace(day=1)
        end = (start.replace(year=start.year + 1, month=1, day=1)
               if start.month == 12
               else start.replace(month=start.month + 1, day=1))
    elif period == "year":
        start = start_of_today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
    else:  # "today" (and any unrecognised value)
        start = start_of_today
        end = start + timedelta(days=1)

    return start, end


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()