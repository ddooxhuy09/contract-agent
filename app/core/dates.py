"""Date helpers shared by agents and retrieval."""

from datetime import date, datetime


def parse_as_of(as_of: str | date | None) -> date:
    if as_of is None:
        return date.today()
    if isinstance(as_of, date) and not isinstance(as_of, datetime):
        return as_of
    text = str(as_of).strip()[:10]
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100:
                    y += 2000
                return date(y, m, d)
            except ValueError:
                pass
    try:
        return date.fromisoformat(text)
    except ValueError:
        return date.today()
