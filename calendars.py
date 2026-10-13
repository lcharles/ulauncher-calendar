# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""
Calendar access through Evolution Data Server.

Has no Ulauncher dependency so it can be exercised from a plain script:
    /usr/bin/python3 calendars.py            # list calendars and the next 7 days
"""

import datetime as dt
import json
import logging
import os
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

import gi
gi.require_version('EDataServer', '1.2')
gi.require_version('ECal', '2.0')
gi.require_version('ICalGLib', '3.0')
from gi.repository import EDataServer, ECal, ICalGLib

logger = logging.getLogger(__name__)

# wait_for_connected_seconds for connect_sync: 0 would wait forever for the backend to go
# online (e.g. a Google list after an EDS restart); -1 returns at once and reads use the
# local copy until the backend has synced.
NO_WAIT = 0xFFFFFFFF

CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'ulauncher-calendar'
STATE_FILE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state')) / 'ulauncher-calendar' / 'state.json'


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '')
    return ''.join(c for c in text if not unicodedata.combining(c)).lower().strip()


@dataclass
class Calendar:
    uid: str
    name: str
    account: str
    color: str
    readonly: bool
    client: object
    excluded: bool = False

    def matches(self, needle):
        """Loose match used by "#word": prefix of any word, or substring of the name."""
        needle = normalize(needle)
        name = normalize(self.name)
        return not needle or name.startswith(needle) or needle in name or \
            any(w.startswith(needle) for w in name.split()) or normalize(self.account).startswith(needle)


@dataclass
class Event:
    uid: str
    rid: str                 # recurrence id of this instance, '' for single events
    summary: str
    start: object            # datetime (local, naive) or date for all-day
    end: object
    all_day: bool
    location: str
    calendar: Calendar

    @property
    def gnome_calendar_id(self):
        """Event id in the form `gnome-calendar --uuid` expects."""
        parts = [self.calendar.uid, self.uid] + ([self.rid] if self.rid else [])
        return ':'.join(parts)

    def sort_key(self):
        start = self.start if isinstance(self.start, dt.datetime) else dt.datetime.combine(self.start, dt.time.min)
        return (start, not self.all_day, self.summary.lower())


def _local_tz():
    return ECal.util_get_system_timezone() or ICalGLib.Timezone.get_utc_timezone()


def _to_python(t, local_tz):
    """ICalGLib.Time -> local naive datetime, or date for DATE values."""
    if t is None or t.is_null_time():
        return None
    if t.is_date():
        return dt.date(t.get_year(), t.get_month(), t.get_day())
    zone = t.get_timezone()
    if zone is None and not t.is_utc():
        # floating time: already "local"
        return dt.datetime(t.get_year(), t.get_month(), t.get_day(), t.get_hour(), t.get_minute(), t.get_second())
    if zone is None:
        zone = ICalGLib.Timezone.get_utc_timezone()
    return dt.datetime.fromtimestamp(t.as_timet_with_zone(zone))


def _to_ical(value, local_tz):
    t = ICalGLib.Time.new_null_time()
    t.set_date(value.year, value.month, value.day)
    if isinstance(value, dt.datetime):
        t.set_time(value.hour, value.minute, 0)
        t.set_timezone(local_tz)
    else:
        t.set_is_date(True)
    return t


class CalendarStore:
    """Connected EDS calendars plus a short-lived cache of listed events."""

    def __init__(self, event_ttl=30):
        self.event_ttl = event_ttl
        self._registry = None
        self._clients = {}           # source uid -> ECal.Client
        self._events = {}            # (source uid, start ts, end ts) -> (loaded_at, [Event])
        self.errors = []

    # --- calendars ---

    def _get_registry(self):
        if self._registry is None:
            self._registry = EDataServer.SourceRegistry.new_sync(None)
        return self._registry

    def calendars(self, excluded=(), include_excluded=False):
        """Enabled calendars, sorted by account then name. `excluded` holds names/uids."""
        registry = self._get_registry()
        excluded = {normalize(e) for e in excluded if e.strip()}
        result = []
        self.errors = []
        for source in registry.list_enabled(EDataServer.SOURCE_EXTENSION_CALENDAR):
            uid, name = source.get_uid(), source.get_display_name()
            parent = registry.ref_source(source.get_parent()) if source.get_parent() else None
            account = parent.get_display_name() if parent else ''
            is_excluded = bool(excluded & {normalize(name), normalize(uid), normalize(f'{account}/{name}')})
            if is_excluded and not include_excluded:
                continue
            client = self._clients.get(uid)
            if client is None:
                try:
                    client = ECal.Client.connect_sync(source, ECal.ClientSourceType.EVENTS, NO_WAIT, None)
                except Exception as e:
                    logger.warning('Calendar %r unavailable: %s', name, e)
                    self.errors.append(f'{name}: {e}')
                    continue
                self._clients[uid] = client
            ext = source.get_extension(EDataServer.SOURCE_EXTENSION_CALENDAR)
            result.append(Calendar(uid=uid, name=name, account=account, color=ext.get_color() or '#888888',
                                   readonly=client.is_readonly(), client=client, excluded=is_excluded))
        result.sort(key=lambda c: (normalize(c.account), normalize(c.name)))
        return result

    # --- events ---

    def events(self, calendars, start, end):
        """Instances (recurrences expanded) overlapping [start, end), sorted by start."""
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
        local_tz = _local_tz()
        out = []
        for cal in calendars:
            key = (cal.uid, start_ts, end_ts)
            cached = self._events.get(key)
            if cached and time.monotonic() - cached[0] < self.event_ttl:
                out.extend(cached[1])
                continue
            found = []

            def collect(comp, istart, iend, *_):
                found.append(self._make_event(cal, comp, istart, iend, local_tz))
                return True

            try:
                cal.client.generate_instances_sync(start_ts, end_ts, None, collect)
            except Exception as e:
                logger.warning('Could not list events of %r: %s', cal.name, e)
                self.errors.append(f'{cal.name}: {e}')
                continue
            # EDS also returns events that merely touch the range (e.g. all-day ending at its start)
            found = [e for e in found if e is not None and _overlaps(e, start, end)]
            self._events[key] = (time.monotonic(), found)
            out.extend(found)
        out.sort(key=Event.sort_key)
        return out

    @staticmethod
    def _make_event(cal, comp, istart, iend, local_tz):
        try:
            start = _to_python(istart, local_tz)
            end = _to_python(iend, local_tz) or start
            rid = comp.get_recurrenceid()
            rid = rid.as_ical_string() if rid is not None and not rid.is_null_time() else ''
            return Event(uid=comp.get_uid(), rid=rid, summary=comp.get_summary() or '(no title)',
                         start=start, end=end, all_day=istart.is_date(),
                         location=comp.get_location() or '', calendar=cal)
        except Exception:
            logger.exception('Skipping unreadable event in %s', cal.name)
            return None

    def create_event(self, cal, title, start, end, all_day, description=None):
        """Create a VEVENT; start/end are dates (all-day, end exclusive) or local datetimes."""
        local_tz = _local_tz()
        comp = ICalGLib.Component.new_vevent()
        comp.set_uid(str(uuid.uuid4()))
        comp.set_summary(title)
        comp.set_dtstamp(ICalGLib.Time.new_current_with_zone(ICalGLib.Timezone.get_utc_timezone()))
        if all_day:
            start, end = _date(start), _date(end)
        comp.set_dtstart(_to_ical(start, local_tz))
        comp.set_dtend(_to_ical(end, local_tz))
        if description:
            comp.set_description(description)
        if not all_day:
            cal.client.add_timezone_sync(local_tz, None)
        ok, uid = cal.client.create_object_sync(comp, ECal.OperationFlags.NONE, None)
        if not ok:
            raise RuntimeError('EDS refused to create the event')
        self._events = {k: v for k, v in self._events.items() if k[0] != cal.uid}
        return uid


def _overlaps(event, start, end):
    as_dt = lambda v: v if isinstance(v, dt.datetime) else dt.datetime.combine(v, dt.time.min)
    ev_start, ev_end = as_dt(event.start), as_dt(event.end)
    if ev_end == ev_start:                      # zero-length events
        return start <= ev_start < end
    return ev_start < end and ev_end > start


def _date(value):
    return value.date() if isinstance(value, dt.datetime) else value


# --- formatting ---------------------------------------------------------------

def day_label(day, today):
    if day == today:
        return 'Today'
    if day == today + dt.timedelta(days=1):
        return 'Tomorrow'
    if day == today - dt.timedelta(days=1):
        return 'Yesterday'
    fmt = '%a %d %b' if day.year == today.year else '%a %d %b %Y'
    return day.strftime(fmt)


def format_span(start, end, all_day, today):
    """'Tomorrow, 15:00–16:00', 'Thu 15 Oct (all day)', 'Thu 15 – Sat 17 Oct (all day)'."""
    if all_day:
        last = _date(end) - dt.timedelta(days=1)
        first = _date(start)
        if last <= first:
            return f'{day_label(first, today)} (all day)'
        return f'{day_label(first, today)} – {day_label(last, today)} (all day)'
    if start.date() == end.date() or (end - start <= dt.timedelta(hours=12) and end.time() <= dt.time(6)):
        return f'{day_label(start.date(), today)}, {start:%H:%M}–{end:%H:%M}'
    return f'{day_label(start.date(), today)} {start:%H:%M} – {day_label(end.date(), today)} {end:%H:%M}'


def color_icon(color):
    """Path to a PNG dot in the calendar's colour (cached)."""
    color = (color or '#888888').strip()
    if not (color.startswith('#') and len(color) in (4, 7)):
        color = '#888888'
    if len(color) == 4:
        color = '#' + ''.join(c * 2 for c in color[1:])
    path = CACHE_DIR / 'colors' / f'{color[1:].lower()}.png'
    if not path.exists():
        import cairo
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 64
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)
        r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        ctx.arc(size / 2, size / 2, size * 0.36, 0, 6.2832)
        ctx.set_source_rgb(r, g, b)
        ctx.fill_preserve()
        ctx.set_source_rgba(0, 0, 0, 0.25)
        ctx.set_line_width(2)
        ctx.stroke()
        surface.write_to_png(str(path))
    return str(path)


# --- persistent state (last used calendar) --------------------------------------

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError:
        logger.exception('Could not save state')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    store = CalendarStore()
    today = dt.date.today()
    cals = store.calendars()
    for c in cals:
        print(f'{c.name!r:32} account={c.account!r} readonly={c.readonly} color={c.color} uid={c.uid}')
    start = dt.datetime.combine(today, dt.time.min)
    for e in store.events(cals, start, start + dt.timedelta(days=7)):
        print(f'  {format_span(e.start, e.end, e.all_day, today):40} {e.summary}  [{e.calendar.name}]  {e.gnome_calendar_id}')
    for err in store.errors:
        print('ERROR', err)
