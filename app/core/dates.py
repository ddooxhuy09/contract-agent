"""Date helpers shared by agents and retrieval."""

import re
from datetime import date, datetime

# «15/07/2026», «15-07-2026», «15.07.2026», «15 tháng 07 năm 2026»
_VN_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:/|-|\.|tháng)\s*(\d{1,2})\s*(?:/|-|\.|năm)\s*(\d{2,4})(?!\d)")


def parse_vn_date(value: str | date | None) -> date | None:
    """Parse a contract date as written (dd/mm/yyyy, «ngày … tháng … năm …», ISO); None if unreadable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    m = _VN_DATE.search(text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y + 2000 if y < 100 else y, mo, d)
        except ValueError:
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_as_of(as_of: str | date | None) -> date:
    """Analysis date: the given one, or today when missing / unreadable."""
    if as_of is None:
        return date.today()
    return parse_vn_date(as_of) or date.today()
