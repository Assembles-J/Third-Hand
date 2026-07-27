"""Time conventions for user-facing API fields."""
from datetime import datetime
from zoneinfo import ZoneInfo

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """Return an offset-aware Beijing timestamp for user-visible events."""
    return datetime.now(BEIJING_TIMEZONE)
