"""Deterministic local-date boundaries for calendar queries.

A local calendar date D is the half-open interval [start(D), start(D+1)) in the
user's timezone, converted to UTC. Nothing here asks a language model what
"today" means: callers pass the current time (or rely on the system clock) and
the user's tzinfo.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Optional, Tuple

Range = Tuple[datetime, datetime]  # [start, end) in UTC

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ORD = r"(?:st|nd|rd|th)?"


def local_day_bounds(day: date, tz: tzinfo) -> Range:
    """[00:00 of `day`, 00:00 of next day) in the user's timezone, as UTC."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def local_range_bounds(first: date, last: date, tz: tzinfo) -> Range:
    """Inclusive local dates first..last as one half-open UTC interval."""
    if last < first:
        first, last = last, first
    return local_day_bounds(first, tz)[0], local_day_bounds(last, tz)[1]


def _week_start(day: date) -> date:  # Monday
    return day - timedelta(days=day.weekday())


def _explicit_dates(text: str, today: date) -> list[date]:
    found: list[tuple[int, date]] = []
    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text):
        try:
            found.append((m.start(), date(int(m[1]), int(m[2]), int(m[3]))))
        except ValueError:
            pass
    pat_dm = rf"\b(\d{{1,2}}){_ORD}\s+(?:of\s+)?({_MONTH_RE})\b\.?,?(?:\s+(\d{{4}}))?"
    pat_md = rf"\b({_MONTH_RE})\b\.?\s+(\d{{1,2}}){_ORD}\b(?:,?\s+(\d{{4}}))?"
    for m in re.finditer(pat_dm, text):
        found.append((m.start(), _mk(int(m[1]), _MONTHS[m[2]], m[3], today)))
    for m in re.finditer(pat_md, text):
        found.append((m.start(), _mk(int(m[2]), _MONTHS[m[1]], m[3], today)))
    return [d for _, d in sorted(found, key=lambda x: x[0]) if d]


def _mk(day: int, month: int, year: Optional[str], today: date) -> Optional[date]:
    try:
        return date(int(year) if year else today.year, month, day)
    except ValueError:
        return None


def resolve_date_range(text: str, tz: tzinfo, now: Optional[datetime] = None) -> Optional[Range]:
    """Return a [start, end) UTC interval for the date expression in `text`,
    or None when the text contains no recognisable date expression."""
    t = (text or "").lower()
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    today = now_local.date()

    dates = _explicit_dates(t, today)
    if len(dates) >= 2 and re.search(r"\b(?:to|until|till|through|between|-|and)\b", t):
        return local_range_bounds(dates[0], dates[1], tz)
    if dates:
        return local_day_bounds(dates[0], tz)

    if re.search(r"\bday after tomorrow\b", t):
        return local_day_bounds(today + timedelta(days=2), tz)
    if re.search(r"\bday before yesterday\b", t):
        return local_day_bounds(today - timedelta(days=2), tz)
    if re.search(r"\btomorrow\b", t):
        return local_day_bounds(today + timedelta(days=1), tz)
    if re.search(r"\byesterday\b", t):
        return local_day_bounds(today - timedelta(days=1), tz)
    if re.search(r"\b(?:today|tonight|this (?:morning|afternoon|evening))\b", t):
        return local_day_bounds(today, tz)
    if re.search(r"\bnext week\b", t):
        s = _week_start(today) + timedelta(days=7)
        return local_range_bounds(s, s + timedelta(days=6), tz)
    if re.search(r"\blast week\b", t):
        s = _week_start(today) - timedelta(days=7)
        return local_range_bounds(s, s + timedelta(days=6), tz)
    if re.search(r"\bthis week\b", t):
        s = _week_start(today)
        return local_range_bounds(s, s + timedelta(days=6), tz)
    return None


def to_query(rng: Range) -> dict:
    """Mongo filter for a half-open interval."""
    return {"$gte": rng[0], "$lt": rng[1]}


def exclusive_end(hi: datetime, tz: tzinfo) -> datetime:
    """Models send an inclusive end like 23:59:59; turn it into the next local
    midnight so the query interval stays half-open without losing the last
    second of the day."""
    local = hi.astimezone(tz)
    if (local.hour, local.minute) == (23, 59):
        nxt = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=tz)
        return nxt.astimezone(timezone.utc)
    return hi
