"""
Query parser for the calendar extension.

    <title, with the date/time anywhere in it> [@ <date/time>] [:: <description>] [#calendar]

Date/time phrases are recognised anywhere in the text and removed from the
title; whatever is left is the title. An empty title means "list events".

    lunch with Bob tomorrow 12:30          -> "lunch with Bob", tomorrow 12:30-13:30
    standup mon 9-9:15am #work             -> "standup", next Monday, in calendars matching "work"
    "Friday release" party fri 6pm for 3h  -> quotes keep "Friday release" in the title
    review @ demain 14h :: bring slides    -> after "@" everything is date/time (falls back to dateparser)
    tomorrow                               -> no title: list tomorrow's events

Recognised dates:  today, tomorrow, day after tomorrow, yesterday, mon..sunday,
                   this/next <weekday>, this/next week, (next) weekend, in 3 days/weeks/months,
                   14/10, 14.10.2026, 2026-10-14, 14 oct, oct 14th 2026
Recognised times:  3pm, 3:30pm, 15:00, 15h, 15h30, noon, midnight, at 3, in 2 hours,
                   ranges (9-10am, 14:00-15:30, 2pm to 4pm, from 9 to 11, 14h-16h),
                   durations (for 2h, for 45 min, for 1h30), all day

Semantics worth knowing:
  - "friday" is the coming Friday (today if it is Friday);
    "next friday" is the Friday of next week (weeks start on Monday).
  - A date without a year is the next occurrence of it (today included).
  - "at 1".."at 7" without am/pm is read as afternoon.
"""

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Optional

MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
}
# "sun" and "sat" are deliberately left out: too common as plain words.
WEEKDAYS = {
    'mon': 0, 'monday': 0, 'tue': 1, 'tues': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2, 'thu': 3, 'thur': 3, 'thurs': 3, 'thursday': 3,
    'fri': 4, 'friday': 4, 'saturday': 5, 'sunday': 6,
}
NUMBER_WORDS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}

_MONTH_RE = '|'.join(sorted(MONTHS, key=len, reverse=True))
_WEEKDAY_RE = '|'.join(sorted(WEEKDAYS, key=len, reverse=True))
_NUM_RE = r'\d+|' + '|'.join(NUMBER_WORDS)
_AMPM = r'[ap]\.?m\.?'

HOLE = '\x00'          # replaces recognised text so neighbours don't merge
QUOTE = '\x01'         # wraps placeholders for quoted text


@dataclass
class When:
    date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None     # last day (inclusive) of a multi-day range
    span_days: int = 1                     # days covered, used when listing ("next week" = 7)
    start: Optional[dt.time] = None
    end: Optional[dt.time] = None
    duration: Optional[dt.timedelta] = None
    all_day: bool = False
    matched: list = field(default_factory=list)

    @property
    def empty(self):
        return not self.matched


@dataclass
class ParsedQuery:
    title: str
    when: When
    description: Optional[str] = None
    calendar: Optional[str] = None         # word after "#"; "" for a bare "#", None if absent
    unparsed: Optional[str] = None         # part of an explicit "@ ..." that wasn't understood

    @property
    def is_create(self):
        return bool(self.title)

    def span(self, today, default_duration=dt.timedelta(hours=1)):
        """Concrete (start, end, all_day). All-day ends are exclusive dates."""
        w = self.when
        day = w.date or today
        last = w.end_date or day
        if w.start is None or w.all_day:
            return day, last + dt.timedelta(days=1), True
        start = dt.datetime.combine(day, w.start)
        if w.end is not None:
            end = dt.datetime.combine(last, w.end)
            if end <= start:
                end += dt.timedelta(days=1)
        else:
            end = dt.datetime.combine(last, w.start) + (w.duration or default_duration)
        return start, end, False


def _to24(hour, minute, ampm):
    if hour > 24 or minute > 59:
        return None
    ampm = (ampm or '').replace('.', '').lower()
    if ampm in ('am', 'pm'):
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm == 'pm' else 0)
    if hour == 24:
        hour = 0 if minute == 0 else None
    if hour is None or hour > 23:
        return None
    return dt.time(hour, minute)


def _number(text):
    text = text.lower()
    return NUMBER_WORDS[text] if text in NUMBER_WORDS else int(text)


def _add_months(day, months):
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    for d in (day.day, 30, 29, 28):
        try:
            return dt.date(year, month, d)
        except ValueError:
            continue


def _next_occurrence(today, month, day):
    """Date for day/month without a year: the next one, today included."""
    for year in (today.year, today.year + 1):
        try:
            candidate = dt.date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None


def _make_date(year, month, day, today):
    try:
        month, day = int(month), int(day)
        if year is None:
            return _next_occurrence(today, month, day)
        year = int(year)
        if year < 100:
            year += 2000
        return dt.date(year, month, day)
    except (ValueError, TypeError):
        return None


class Parser:

    def __init__(self, date_order='DMY'):
        self.date_order = date_order
        self._rules = self._build_rules()

    # --- public API -------------------------------------------------------

    def parse(self, text, now=None):
        now = now or dt.datetime.now()
        text = (text or '').strip()

        quoted = []

        def protect(m):
            quoted.append(m.group(1))
            # private-use code point: not a digit or word char, so no rule can match it
            return f'{QUOTE}{chr(0xE000 + len(quoted) - 1)}{QUOTE}'

        text = re.sub(r'"([^"]*)"', protect, text)

        segments = self._split_markers(text)
        title_part = segments.get('title', '')
        unparsed = None

        if 'when' in segments:
            when, leftover = self._extract(segments['when'], now)
            leftover = self._clean(leftover)
            if leftover:
                if not self._fallback(leftover, when, now):
                    unparsed = leftover
            title = title_part
        else:
            when, title = self._extract(title_part, now)

        def restore(s):
            return re.sub(f'{QUOTE}(.){QUOTE}', lambda m: quoted[ord(m.group(1)) - 0xE000], s or '')

        description = restore(segments.get('description', '')).strip() or None
        calendar = segments.get('calendar')
        if calendar is not None:
            calendar = restore(calendar).strip()
        return ParsedQuery(
            title=restore(self._clean(title)),
            when=when,
            description=description,
            calendar=calendar,
            unparsed=restore(unparsed) if unparsed else None,
        )

    # --- markers ----------------------------------------------------------

    _CALENDAR_RE = re.compile(r'(?:(?<=\s)|^)#(?P<name>[^\s\d#]\S*)?(?=\s|$)')
    _MARKER_RE = re.compile(r'::|(?:(?<=\s)|^)@')

    def _split_markers(self, text):
        """Split into title / when ("@") / description ("::") / calendar ("#word")."""
        segments = {}
        m = self._CALENDAR_RE.search(text)
        if m:
            segments['calendar'] = m['name'] or ''
            text = text[:m.start()] + text[m.end():]

        markers, seen = [], set()
        for m in self._MARKER_RE.finditer(text):
            kind = 'description' if m.group() == '::' else 'when'
            if kind not in seen:
                seen.add(kind)
                markers.append((m.start(), m.end(), kind))
        segments['title'] = text[:markers[0][0]] if markers else text
        for i, (_, end, kind) in enumerate(markers):
            stop = markers[i + 1][0] if i + 1 < len(markers) else len(text)
            segments[kind] = text[end:stop].strip()
        return segments

    # --- extraction -------------------------------------------------------

    def _extract(self, text, now):
        when = When()
        today = now.date()
        for regex, slots, handler in self._rules:
            pos = 0
            while True:
                m = regex.search(text, pos)
                if not m:
                    break
                if any(self._slot_filled(when, s) for s in slots) or not handler(m, when, today, now):
                    pos = m.end()
                    continue
                stop = m.end()
                if slots == ['date'] and when.end_date is None:
                    stop = self._extend_date_range(text, stop, when, now)
                when.matched.append(text[m.start():stop].strip())
                text = text[:m.start()] + f' {HOLE} ' + text[stop:]
                pos = m.start() + 3
        return when, text

    _RANGE_SEP = re.compile(r'\s*(?:-|–|—|\bto\b|\buntil\b|\btill\b|\bthrough\b|\bthru\b)\s*', re.I)
    _BARE_DAY = re.compile(r'(?P<d>\d{1,2})(?:st|nd|rd|th)?(?![\w:./])', re.I)

    def _extend_date_range(self, text, pos, when, now):
        """After a date, swallow "- <date>" / "to <date>" as the end of a multi-day range."""
        sep = self._RANGE_SEP.match(text, pos)
        if not sep:
            return pos
        start = when.date
        end, stop = None, pos
        for regex, slots, handler in self._rules:
            if slots != ['date']:
                continue
            m = regex.match(text, sep.end())
            tmp = When()
            # relative words in the end part are read from the start date ("mon - fri")
            if m and handler(m, tmp, start, now) and tmp.date:
                end, stop = tmp.date, m.end()
                break
        if end is None:
            m = self._BARE_DAY.match(text, sep.end())     # "oct 14-18"
            if m:
                day = int(m['d'])
                end = _make_date(start.year, start.month, day, start) if day >= start.day else None
                end = end or _make_date(None, _add_months(start.replace(day=1), 1).month, day, start)
                stop = m.end()
        if end is None or end <= start:
            return pos
        when.end_date = end
        when.span_days = (end - start).days + 1
        return stop

    @staticmethod
    def _slot_filled(when, slot):
        return {
            'date': when.date is not None,
            'time': when.start is not None,
            'duration': when.duration is not None or when.end is not None,
            'all_day': when.all_day,
        }[slot]

    @staticmethod
    def _clean(text):
        text = re.sub(rf'\b(?:on|at|from|for|by|between)\s*(?={HOLE})', ' ', text, flags=re.I)
        text = text.replace(HOLE, ' ')
        text = ' '.join(text.split())
        return text.strip(' ,;:-–—')

    def _fallback(self, text, when, now):
        """Last resort for an explicit "@ ..." part (handles other languages)."""
        try:
            import dateparser
        except ImportError:
            return False
        settings = {
            'PREFER_DATES_FROM': 'future',
            'DATE_ORDER': self.date_order,
            'RELATIVE_BASE': now.replace(second=0, microsecond=0),
            'RETURN_TIME_AS_PERIOD': True,
        }
        try:
            data = dateparser.DateDataParser(settings=settings).get_date_data(text)
        except Exception:
            return False
        if not data or not data.date_obj:
            return False
        if abs((data.date_obj.date() - now.date()).days) > 3 * 366:
            return False
        if when.date is None:
            when.date = data.date_obj.date()
        if data.period == 'time' and when.start is None:
            when.start = data.date_obj.time().replace(second=0, microsecond=0)
        when.matched.append(text)
        return True

    # --- rules ------------------------------------------------------------

    def _build_rules(self):
        I = re.I
        rules = []

        def rule(pattern, slots):
            def wrap(fn):
                rules.append((re.compile(pattern, I), slots, fn))
                return fn
            return wrap

        # Durations go first so "1.5h" or "1h30" are never mistaken for dates/times.
        @rule(rf'\bfor\s+(?P<h>{_NUM_RE})\s*(?:h|hrs?|hours?)\s*(?:and\s+)?(?P<m>\d{{1,2}})\s*(?:m|mins?|minutes?)?(?!\w)', ['duration'])
        def _(m, w, today, now):
            w.duration = dt.timedelta(hours=_number(m['h']), minutes=int(m['m']))
            return True

        @rule(r'\bfor\s+(?P<n>\d+(?:[.,]\d+)?|an?|one|two|three|four|five|six)\s*(?P<u>h|hrs?|hours?|m|mins?|minutes?)(?!\w)', ['duration'])
        def _(m, w, today, now):
            n = m['n'].replace(',', '.')
            n = float(n) if n[0].isdigit() else _number(n)
            unit = 'minutes' if m['u'].lower().startswith('m') else 'hours'
            w.duration = dt.timedelta(**{unit: n})
            return w.duration > dt.timedelta(0)

        @rule(r'\bfor\s+half\s+an?\s+hour\b', ['duration'])
        def _(m, w, today, now):
            w.duration = dt.timedelta(minutes=30)
            return True

        @rule(r'\ball[\s-]?day\b', ['all_day'])
        def _(m, w, today, now):
            w.all_day = True
            return True

        # --- dates ---

        @rule(r'(?:\bon\s+)?\b(?P<y>\d{4})-(?P<mo>\d{1,2})-(?P<d>\d{1,2})\b', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], m['mo'], m['d'], today)
            return w.date is not None

        @rule(r'(?:\bon\s+)?\b(?P<a>\d{1,2})[./](?P<b>\d{1,2})(?:[./](?P<y>\d{4}|\d{2}))?\.?(?![\w./:])', ['date'])
        def _(m, w, today, now):
            day, month = (m['a'], m['b']) if self.date_order == 'DMY' else (m['b'], m['a'])
            w.date = _make_date(m['y'], month, day, today)
            return w.date is not None

        @rule(rf'(?:\b(?:on|from)\s+)?\b(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:-|–|to)\s*(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mo>{_MONTH_RE})\b\.?(?:,?\s+(?P<y>\d{{4}})\b)?', ['date'])
        def _(m, w, today, now):
            month = MONTHS[m['mo'].lower()]
            start = _make_date(m['y'], month, m['d1'], today)
            end = start and _make_date(start.year, month, m['d2'], today)
            if not start or not end or end <= start:
                return False
            w.date, w.end_date, w.span_days = start, end, (end - start).days + 1
            return True

        @rule(rf'(?:\bon\s+)?(?:the\s+)?\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mo>{_MONTH_RE})\b\.?(?:,?\s+(?P<y>\d{{4}})\b)?', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], MONTHS[m['mo'].lower()], m['d'], today)
            return w.date is not None

        @rule(rf'(?:\bon\s+)?\b(?P<mo>{_MONTH_RE})\.?\s+(?:the\s+)?(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b(?!:)(?:,?\s+(?P<y>\d{{4}})\b)?', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], MONTHS[m['mo'].lower()], m['d'], today)
            return w.date is not None

        @rule(rf'\bin\s+(?P<n>{_NUM_RE})\s+(?P<u>days?|weeks?|months?)\b', ['date'])
        def _(m, w, today, now):
            n, unit = _number(m['n']), m['u'].lower()
            if unit.startswith('month'):
                w.date = _add_months(today, n)
            else:
                w.date = today + dt.timedelta(days=n * (7 if unit.startswith('week') else 1))
            return True

        @rule(r'\b(?:the\s+)?day\s+after\s+tomorrow\b', ['date'])
        def _(m, w, today, now):
            w.date = today + dt.timedelta(days=2)
            return True

        @rule(r'\b(?P<word>today|tonight|tomorrow|tmrw|tmr|yesterday)\b', ['date'])
        def _(m, w, today, now):
            offset = {'yesterday': -1, 'today': 0, 'tonight': 0}.get(m['word'].lower(), 1)
            w.date = today + dt.timedelta(days=offset)
            return True

        @rule(r'\b(?P<which>this|next)\s+week\b', ['date'])
        def _(m, w, today, now):
            monday = today - dt.timedelta(days=today.weekday())
            if m['which'].lower() == 'next':
                w.date, w.span_days = monday + dt.timedelta(days=7), 7
            else:
                w.date, w.span_days = today, 7 - today.weekday()
            return True

        @rule(r'(?:\bon\s+)?\b(?:(?P<which>this|next)\s+)?(?:the\s+)?weekend\b', ['date'])
        def _(m, w, today, now):
            if today.weekday() == 6:
                saturday = today - dt.timedelta(days=1)
            else:
                saturday = today + dt.timedelta(days=5 - today.weekday())
            if (m['which'] or '').lower() == 'next':
                saturday += dt.timedelta(days=7)
            w.date, w.span_days = max(saturday, today), (saturday + dt.timedelta(days=2) - max(saturday, today)).days
            return True

        @rule(rf'(?:\bon\s+)?\b(?:(?P<which>this|next|coming)\s+)?(?P<day>{_WEEKDAY_RE})\b\.?', ['date'])
        def _(m, w, today, now):
            target = WEEKDAYS[m['day'].lower()]
            if (m['which'] or '').lower() == 'next':
                monday_next = today + dt.timedelta(days=7 - today.weekday())
                w.date = monday_next + dt.timedelta(days=target)
            else:
                w.date = today + dt.timedelta(days=(target - today.weekday()) % 7)
            return True

        # --- times ---

        @rule(rf'\bin\s+(?P<n>{_NUM_RE})\s*(?P<u>h|hrs?|hours?|m|mins?|minutes?)(?!\w)', ['time', 'date'])
        def _(m, w, today, now):
            unit = 'minutes' if m['u'].lower().startswith('m') else 'hours'
            at = (now + dt.timedelta(**{unit: _number(m['n'])})).replace(second=0, microsecond=0)
            w.date, w.start = at.date(), at.time()
            return True

        @rule(rf'(?:\b(?P<from>from|between)\s+)?\b(?P<h1>\d{{1,2}})(?:(?P<s1>[:h.])(?P<m1>\d{{2}}))?\s*(?P<a1>{_AMPM}|h)?'
              rf'\s*(?:-|–|—|\bto\b|\buntil\b|\btill\b|\band\b)\s*'
              rf'(?P<h2>\d{{1,2}})(?:(?P<s2>[:h.])(?P<m2>\d{{2}}))?\s*(?P<a2>{_AMPM}|h)?(?![\w:/])', ['time', 'duration'])
        def _(m, w, today, now):
            explicit = m['from'] or m['a1'] or m['a2'] or (m['s1'] and m['s1'] != '.') or (m['s2'] and m['s2'] != '.')
            dotted = '.' in (m['s1'] or '') + (m['s2'] or '')
            if dotted and not (m['a1'] or m['a2']) and not (m['s1'] == m['s2'] == '.'):
                return False
            if not explicit and not dotted:
                return False
            sep = m.group().lower()
            if re.search(r'\band\b', sep) and (m['from'] or '').lower() != 'between':
                return False
            a1 = m['a1'] if m['a1'] and m['a1'].lower() != 'h' else None
            a2 = m['a2'] if m['a2'] and m['a2'].lower() != 'h' else None
            m1, m2 = int(m['m1'] or 0), int(m['m2'] or 0)
            end = _to24(int(m['h2']), m2, a2)
            start = _to24(int(m['h1']), m1, a1 or a2)
            if a2 and not a1 and start and end and start > end:
                flipped = 'am' if a2.lower().startswith('p') else 'pm'
                start = _to24(int(m['h1']), m1, flipped)
            if start is None or end is None:
                return False
            w.start, w.end = start, end
            return True

        @rule(rf'(?:\bat\s+)?\b(?P<h>\d{{1,2}})(?:[:h.](?P<m>\d{{2}}))?\s*(?P<a>{_AMPM})(?!\w)', ['time'])
        def _(m, w, today, now):
            w.start = _to24(int(m['h']), int(m['m'] or 0), m['a'])
            return w.start is not None

        @rule(r'(?:\bat\s+)?\b(?P<h>\d{1,2})(?:[:h](?P<m>\d{2})|h)(?![\w:])', ['time'])
        def _(m, w, today, now):
            # a bare "2h" is more likely a duration than 2 in the morning
            if m['m'] is None and int(m['h']) < 6:
                return False
            w.start = _to24(int(m['h']), int(m['m'] or 0), None)
            return w.start is not None

        @rule(r'(?:\bat\s+)?\b(?P<word>noon|midday|midnight)\b', ['time'])
        def _(m, w, today, now):
            w.start = dt.time(0, 0) if m['word'].lower() == 'midnight' else dt.time(12, 0)
            return True

        @rule(r'\bat\s+(?P<h>\d{1,2})(?![\w:./%])', ['time'])
        def _(m, w, today, now):
            hour = int(m['h'])
            if not 0 <= hour <= 23:
                return False
            w.start = dt.time(hour + 12 if 1 <= hour <= 7 else hour, 0)
            return True

        return rules
