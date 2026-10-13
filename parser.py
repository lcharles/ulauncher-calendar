"""
Query parser for the calendar extension.

    <title, with the date/time anywhere in it> [@ <date/time>] [:: <description>] [#calendar]

Date/time phrases are recognised anywhere in the text and removed from the
title; whatever is left is the title. An empty title means "list events".

    lunch with Bob tomorrow 12:30          -> "lunch with Bob", tomorrow 12:30-13:30
    standup mon 9-9:15am #work             -> "standup", next Monday, in calendars matching "work"
    "Friday release" party fri 6pm for 3h  -> quotes keep "Friday release" in the title
    réunion mercredi prochain de 14h à 16h -> French works the same way, with or without "@"
    review @ morgen 14:00 :: bring slides  -> after "@" everything is date/time (other languages
                                              fall back to dateparser)
    tomorrow                               -> no title: list tomorrow's events

Languages: the words come from language packs (langs/en.py, fr.py, de.py, es.py, it.py);
a Parser uses the one or two it is given. The examples below are the English and French ones.
Recognised dates:  today, tomorrow, day after tomorrow, yesterday, mon..sunday,
                   this/next <weekday>, this/next week, (next) weekend, in 3 days/weeks/months,
                   14/10, 14.10.2026, 2026-10-14, 14 oct, oct 14th 2026, wed 14 oct
                   aujourd'hui, ce soir, demain, après-demain, hier, lundi..dimanche,
                   ce/<jour> prochain, cette semaine, semaine prochaine, ce week-end,
                   week-end prochain, dans 3 jours/semaines/mois, le 1er novembre,
                   du 20 au 23 octobre, lundi au vendredi
Recognised times:  3pm, 3:30pm, 15:00, 15h, 15h30, noon, midnight, at 3, in 2 hours,
                   ranges (9-10am, 14:00-15:30, 2pm to 4pm, from 9 to 11, 14h-16h),
                   durations (for 2h, for 45 min, for 1h30), all day
                   à 14h, 14 h 30, 14 heures, midi, minuit, dans 2 heures,
                   de 9h à 11h, entre 9h et 11h, pendant 1h30, pour 45 min, toute la journée

Semantics worth knowing:
  - "friday" is the coming Friday (today if it is Friday);
    "next friday" / "vendredi prochain" is the Friday of next week (weeks start on Monday).
  - A date without a year is the next occurrence of it (today included).
  - "at 1".."at 7" without am/pm is read as afternoon.
"""

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Optional

import langs
from langs import lookup, words

_AMPM = r'[ap]\.?m\.?'                          # understood whatever the languages

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

    def __init__(self, date_order='DMY', languages=('en', 'fr')):
        """`languages`: one or two codes from langs.AVAILABLE, the first winning on conflicts."""
        self.date_order = date_order
        self.v = langs.load(languages)
        self.languages = self.v.codes
        self._ord = rf'(?:{self.v.ORDINAL})?'
        self._range_sep = re.compile(rf'\s*(?:-|–|—|\b(?:{self.v.RANGE_TO})\b)\s*', re.I)
        self._bare_day = re.compile(rf'(?P<d>\d{{1,2}}){self._ord}(?![\w:./])', re.I)
        self._fillers = re.compile(rf'(?<!\d)(?<!\d\s)\b(?:{self.v.FILLERS}|{self.v.ON}|{self.v.AT})\s*(?={HOLE})', re.I)
        self._rules = self._build_rules()

    def _number(self, text):
        return self.v.numbers[text.lower()] if text.lower() in self.v.numbers else int(text)

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

    def _extend_date_range(self, text, pos, when, now):
        """After a date, swallow "- <date>" / "to <date>" as the end of a multi-day range."""
        sep = self._range_sep.match(text, pos)
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
            m = self._bare_day.match(text, sep.end())     # "oct 14-18"
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

    def _clean(self, text):
        text = self._fillers.sub(' ', text)
        text = text.replace(HOLE, ' ')
        text = ' '.join(text.split())
        return text.strip(' ,;:-–—')

    def _fallback(self, text, when, now):
        """Last resort for an explicit "@ ..." part: dateparser, in the selected languages first,
        then in any language it knows."""
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
        data = None
        for languages in (list(self.languages), None):
            try:
                data = dateparser.DateDataParser(languages=languages, settings=settings).get_date_data(text)
            except Exception:
                data = None
            if data and data.date_obj:
                break
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
        V = self.v
        rules = []

        def rule(pattern, slots):
            def wrap(fn):
                rules.append((re.compile(pattern, I), slots, fn))
                return fn
            return wrap

        def opt(piece):
            """`piece` followed by spaces, optional."""
            return rf'(?:\b(?:{piece})\s+)?'

        def on(piece=V.ON):
            """Optional "on"-like word before a date, but never right after a number: in
            "9 am friday" with German selected, "am" belongs to the time."""
            return rf'(?:{NOT_AFTER_NUMBER}\b(?:{piece})\s+)?'

        def word_in(piece, text):
            return bool(text) and re.fullmatch(piece, text, I) is not None

        ORD = self._ord
        NOT_AFTER_NUMBER = r'(?<!\d)(?<!\d\s)'
        MONTH = words(V.months)
        WEEKDAY = words(V.weekdays)
        NUM = r'\d+|' + words(V.numbers)
        HOURS, MINUTES = V.units['hour'], V.units['minute']
        AT = rf'(?:\b(?P<at>{V.AT})\s+)?'
        # "wed 14 oct" / "mercredi 14 octobre": the weekday just restates the date
        WD_PREFIX = rf'(?:\b(?:{WEEKDAY})\b\.?,?\s+)?'
        YEAR = rf'(?:,?\s+(?:(?:{V.YEAR_OF})\s+)?(?P<y>\d{{4}})\b)?'
        NEXT_PREFIX = rf'(?:(?P<this>{V.THIS})\s+|(?P<next>{V.NEXT})\s+)?'
        NEXT_SUFFIX = rf'(?:\s+(?P<next2>{V.NEXT_AFTER})\b)?'

        def is_next(m):
            return bool(m['next'] or m['next2'])

        # Durations go first so "1.5h" or "1h30" are never mistaken for dates/times.
        FOR = rf'\b(?:{V.FOR})\s+'

        @rule(rf'{FOR}(?P<h>{NUM})\s*(?:{HOURS})\s*(?:(?:{V.AND})\s+)?(?P<m>\d{{1,2}})\s*(?:{MINUTES})?(?!\w)', ['duration'])
        def _(m, w, today, now):
            w.duration = dt.timedelta(hours=self._number(m['h']), minutes=int(m['m']))
            return True

        @rule(rf'{FOR}(?P<n>\d+(?:[.,]\d+)?|{words(V.numbers)})\s*(?P<u>{HOURS}|{MINUTES})(?!\w)', ['duration'])
        def _(m, w, today, now):
            n = m['n'].replace(',', '.')
            n = float(n) if n[0].isdigit() else self._number(n)
            unit = 'minutes' if word_in(MINUTES, m['u']) else 'hours'
            w.duration = dt.timedelta(**{unit: n})
            return w.duration > dt.timedelta(0)

        @rule(rf'{FOR}(?:{V.HALF_HOUR})\b', ['duration'])
        def _(m, w, today, now):
            w.duration = dt.timedelta(minutes=30)
            return True

        @rule(rf'\b(?:{V.ALL_DAY})\b', ['all_day'])
        def _(m, w, today, now):
            w.all_day = True
            return True

        # --- dates ---

        @rule(rf'{on()}\b(?P<y>\d{{4}})-(?P<mo>\d{{1,2}})-(?P<d>\d{{1,2}})\b', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], m['mo'], m['d'], today)
            return w.date is not None

        @rule(rf'{on()}{WD_PREFIX}\b(?P<a>\d{{1,2}})[./](?P<b>\d{{1,2}})(?:[./](?P<y>\d{{4}}|\d{{2}}))?\.?(?![\w./:])', ['date'])
        def _(m, w, today, now):
            day, month = (m['a'], m['b']) if self.date_order == 'DMY' else (m['b'], m['a'])
            w.date = _make_date(m['y'], month, day, today)
            return w.date is not None

        @rule(rf'{on(f"{V.ON}|{V.DAY_FROM}")}\b(?P<d1>\d{{1,2}}){ORD}\s*(?:-|–|\b(?:{V.DAY_TO})\b)\s*'
              rf'(?P<d2>\d{{1,2}}){ORD}\s+{opt(V.OF)}(?P<mo>{MONTH})\b\.?{YEAR}', ['date'])
        def _(m, w, today, now):
            month = lookup(V.months, m['mo'])
            start = _make_date(m['y'], month, m['d1'], today)
            end = start and _make_date(start.year, month, m['d2'], today)
            if not start or not end or end <= start:
                return False
            w.date, w.end_date, w.span_days = start, end, (end - start).days + 1
            return True

        @rule(rf'{on()}{WD_PREFIX}{opt(V.THE)}\b(?P<d>\d{{1,2}}){ORD}\s+{opt(V.OF)}(?P<mo>{MONTH})\b\.?{YEAR}', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], lookup(V.months, m['mo']), m['d'], today)
            return w.date is not None

        @rule(rf'{on()}{WD_PREFIX}\b(?P<mo>{MONTH})\.?\s+{opt(V.THE)}(?P<d>\d{{1,2}}){ORD}\b(?!:){YEAR}', ['date'])
        def _(m, w, today, now):
            w.date = _make_date(m['y'], lookup(V.months, m['mo']), m['d'], today)
            return w.date is not None

        @rule(rf'\b(?:{V.IN})\s+(?P<n>{NUM})\s+(?P<u>{V.units["day"]}|{V.units["week"]}|{V.units["month"]})\b', ['date'])
        def _(m, w, today, now):
            n = self._number(m['n'])
            if word_in(V.units['month'], m['u']):
                w.date = _add_months(today, n)
            else:
                w.date = today + dt.timedelta(days=n * (7 if word_in(V.units['week'], m['u']) else 1))
            return True

        @rule(rf'\b(?P<word>{words(V.relative_days)})\b', ['date'])
        def _(m, w, today, now):
            w.date = today + dt.timedelta(days=lookup(V.relative_days, m['word']))
            return True

        # weekend before week, so "this weekend" is not "this week" + "end"
        @rule(rf'{on()}\b{opt(V.ARTICLE)}{NEXT_PREFIX}(?:(?:{V.THE})\s+)?(?:{V.WEEKEND})\b{NEXT_SUFFIX}', ['date'])
        def _(m, w, today, now):
            if today.weekday() == 6:
                saturday = today - dt.timedelta(days=1)
            else:
                saturday = today + dt.timedelta(days=5 - today.weekday())
            if is_next(m):
                saturday += dt.timedelta(days=7)
            w.date, w.span_days = max(saturday, today), (saturday + dt.timedelta(days=2) - max(saturday, today)).days
            return True

        @rule(rf'\b{opt(V.ARTICLE)}(?:{NEXT_PREFIX}(?:{V.WEEK}){NEXT_SUFFIX})\b', ['date'])
        def _(m, w, today, now):
            if not (m['this'] or is_next(m)):
                return False                # a bare "week" is just a word
            monday = today - dt.timedelta(days=today.weekday())
            if is_next(m):
                w.date, w.span_days = monday + dt.timedelta(days=7), 7
            else:
                w.date, w.span_days = today, 7 - today.weekday()
            return True

        # "next wednesday" / "mercredi prochain" is the one of next week
        @rule(rf'{on()}\b{opt(V.ARTICLE)}{NEXT_PREFIX}(?P<day>{WEEKDAY})\b\.?{NEXT_SUFFIX}', ['date'])
        def _(m, w, today, now):
            target = lookup(V.weekdays, m['day'])
            if is_next(m):
                monday_next = today + dt.timedelta(days=7 - today.weekday())
                w.date = monday_next + dt.timedelta(days=target)
            else:
                w.date = today + dt.timedelta(days=(target - today.weekday()) % 7)
            return True

        # --- times ---

        @rule(rf'\b(?:{V.IN})\s+(?P<n>{NUM})\s*(?P<u>{HOURS}|{MINUTES})(?!\w)', ['time', 'date'])
        def _(m, w, today, now):
            unit = 'minutes' if word_in(MINUTES, m['u']) else 'hours'
            at = (now + dt.timedelta(**{unit: self._number(m['n'])})).replace(second=0, microsecond=0)
            w.date, w.start = at.date(), at.time()
            return True

        T_ART = rf'(?:(?:{V.TIME_ARTICLE})\s+)?'
        MARK = rf'{_AMPM}|{V.HOUR_MARK}'

        @rule(rf'(?:\b(?P<from>{V.TIME_FROM}|{V.TIME_BETWEEN})\s+{T_ART})?\b(?P<h1>\d{{1,2}})(?:(?P<s1>[:h.])(?P<m1>\d{{2}}))?\s*(?P<a1>{MARK})?'
              rf'\s*(?P<sep>-|–|—|\b(?:{V.TIME_TO})\b|\b(?:{V.AND})\b)\s*{T_ART}'
              rf'(?P<h2>\d{{1,2}})(?:(?P<s2>[:h.])(?P<m2>\d{{2}}))?\s*(?P<a2>{MARK})?(?![\w:/])', ['time', 'duration'])
        def _(m, w, today, now):
            explicit = m['from'] or m['a1'] or m['a2'] or (m['s1'] and m['s1'] != '.') or (m['s2'] and m['s2'] != '.')
            dotted = '.' in (m['s1'] or '') + (m['s2'] or '')
            if dotted and not (m['a1'] or m['a2']) and not (m['s1'] == m['s2'] == '.'):
                return False
            if not explicit and not dotted:
                return False
            # "and" only joins a range after "between"
            if word_in(V.AND, m['sep']) and not word_in(V.TIME_BETWEEN, m['from']):
                return False
            a1 = m['a1'] if word_in(_AMPM, m['a1']) else None
            a2 = m['a2'] if word_in(_AMPM, m['a2']) else None
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

        @rule(rf'{AT}\b(?P<h>\d{{1,2}})(?:[:h.](?P<m>\d{{2}}))?\s*(?P<a>{_AMPM})(?!\w)', ['time'])
        def _(m, w, today, now):
            w.start = _to24(int(m['h']), int(m['m'] or 0), m['a'])
            return w.start is not None

        # 15:30, 15h, 15h30, 15 h 30, 15 heures, 15 Uhr, 15:30 Uhr
        @rule(rf'{AT}\b(?P<h>\d{{1,2}})(?::(?P<m>\d{{2}})(?:\s*(?:{V.HOUR_MARK})\b)?|\s*(?P<mark>{V.HOUR_MARK})(?:\s*(?P<m2>\d{{2}}))?)(?![\w:])', ['time'])
        def _(m, w, today, now):
            minute = m['m'] or m['m2']
            # a bare "2h" is more likely a duration than 2 in the morning
            if minute is None and int(m['h']) < 6 and not m['at'] and word_in('h', m['mark']):
                return False
            w.start = _to24(int(m['h']), int(minute or 0), None)
            return w.start is not None

        @rule(rf'{AT}\b(?P<word>{V.NOON}|{V.MIDNIGHT})\b', ['time'])
        def _(m, w, today, now):
            w.start = dt.time(0, 0) if word_in(V.MIDNIGHT, m['word']) else dt.time(12, 0)
            return True

        @rule(rf'\b(?:{V.AT})\s+(?P<h>\d{{1,2}})(?![\w:./%])', ['time'])
        def _(m, w, today, now):
            hour = int(m['h'])
            if not 0 <= hour <= 23:
                return False
            w.start = dt.time(hour + 12 if 1 <= hour <= 7 else hour, 0)
            return True

        return rules
