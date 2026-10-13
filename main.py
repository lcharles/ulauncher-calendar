# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""
Calendar extension for Ulauncher, backed by Evolution Data Server.

Lists events across all your EDS calendars (GNOME Calendar, Google / CalDAV
accounts from GNOME Online Accounts, ...) and creates new ones.

    cal                          -> upcoming events
    cal tomorrow / cal fri       -> events on that day ("next week", "weekend", "14/10-18/10" work too)
    cal lunch with Bob tmrw 12:30
                                 -> one "Add" item per writable calendar (last used first),
                                    followed by what is already planned that day
    cal review 3pm :: notes      -> "::" adds a description
    cal standup mon 9am #work    -> "#word" restricts to calendars matching "word"
    cal réunion demain 14h       -> dates in the one or two languages chosen in the preferences
    cal #                        -> list calendars (Alt+Enter copies a name for the exclusion preference)

See parser.py for everything the date/time parser understands.
"""

import datetime as dt
import logging
import os
import shutil
import subprocess

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.SetUserQueryAction import SetUserQueryAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.DoNothingAction import DoNothingAction

from calendars import CalendarStore, color_icon, day_label, format_span, load_state, save_state
import langs
from parser import Parser

logger = logging.getLogger(__name__)

ICON = 'images/icon.png'
ERROR_ICON = 'images/error.png'
MAX_EVENTS = 25
CONTEXT_EVENTS = 5


class CalendarExtension(Extension):

    def __init__(self):
        super().__init__()
        self.store = CalendarStore()
        self.store.warm_up()
        self.state = load_state()
        self._parser = None
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

    # --- preferences ---

    def pref_int(self, key, default):
        try:
            return max(1, int(self.preferences.get(key) or default))
        except ValueError:
            return default

    @property
    def parser(self):
        order = self.preferences.get('date_order') or 'DMY'
        languages = self.languages()
        if self._parser is None or (self._parser.date_order, self._parser.languages) != (order, languages):
            self._parser = Parser(order, languages)
        return self._parser

    def languages(self):
        """The one or two selected language codes, "auto" being the desktop's language."""
        codes = []
        for key in ('language', 'language2'):
            code = (self.preferences.get(key) or '').strip().lower()
            if code == 'auto':
                code = desktop_language()
            if code in langs.AVAILABLE and code not in codes:
                codes.append(code)
        return tuple(codes) or ('en',)

    def excluded(self):
        return [e.strip() for e in (self.preferences.get('excluded_calendars') or '').split(',') if e.strip()]

    def calendars(self, include_excluded=False):
        return self.store.calendars(self.excluded(), include_excluded=include_excluded)

    # --- items ---

    def event_item(self, event, today, suffix=''):
        when = format_span(event.start, event.end, event.all_day, today)
        details = [when, event.calendar.name] + ([event.location] if event.location else [])
        return ExtensionResultItem(
            icon=color_icon(event.calendar.color),
            name=event.summary + suffix,
            description=' · '.join(details),
            highlightable=False,
            on_enter=open_action(event.gnome_calendar_id, event.summary, when),
            on_alt_enter=CopyToClipboardAction(f'{event.summary} — {when}'),
        )

    def last_used_first(self, calendars):
        last = self.state.get('last_calendar')
        return sorted(calendars, key=lambda c: c.uid != last)


def desktop_language():
    """Two-letter code of the session's language if there is a pack for it, else English."""
    for var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        for value in (os.environ.get(var) or '').split(':'):
            if value[:2].lower() in langs.AVAILABLE:
                return value[:2].lower()
    return 'en'


def open_action(event_id, summary, when):
    if shutil.which('gnome-calendar'):
        return ExtensionCustomAction({'action': 'open', 'id': event_id}, keep_app_open=False)
    return CopyToClipboardAction(f'{summary} — {when}')


def message(name, description='', icon=ICON, on_enter=None):
    return ExtensionResultItem(icon=icon, name=name, description=description, highlightable=False,
                               on_enter=on_enter or DoNothingAction())


def failure_items(extension):
    return [message(f, 'The event was not saved', ERROR_ICON) for f in extension.store.pop_failures()]


def read_errors(errors):
    """A warning row when some calendars couldn't be read, so missing events don't look like free time."""
    if not errors:
        return []
    return [message('Some calendars couldn’t be read: events may be missing', '; '.join(errors), ERROR_ICON)]


class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        try:
            items = self.results(event, extension)
        except Exception as e:
            logger.exception('Calendar query failed')
            items = [message('Calendar error', str(e), ERROR_ICON)]
        # failed saves and unreadable calendars show on every view, so missing events don't look like free time
        return RenderResultListAction(failure_items(extension) + read_errors(extension.store.errors) + items)

    def results(self, event, extension):
        text = (event.get_argument() or '').strip()
        now = dt.datetime.now()
        query = extension.parser.parse(text, now=now)
        if query.calendar == '' and not query.title and query.when.empty:
            return self.list_calendars(event, extension)

        calendars = extension.calendars()
        if query.calendar:
            calendars = [c for c in calendars if c.matches(query.calendar)]
            if not calendars:
                hidden = [c.name for c in extension.calendars(include_excluded=True)
                          if c.excluded and c.matches(query.calendar)]
                return [message(
                    f'No calendar matches “#{query.calendar}”',
                    f'“{hidden[0]}” is excluded in the preferences' if hidden
                    else 'Type “cal #” to list your calendars', ERROR_ICON)]
        if not calendars:
            return [message('No calendars found', 'Add one in GNOME Calendar or GNOME Online Accounts', ERROR_ICON)]

        if query.is_create:
            return self.create_items(query, calendars, extension, now)
        return self.list_items(query, calendars, extension, now)

    @staticmethod
    def list_items(query, calendars, extension, now):
        today = now.date()
        items = []
        if query.unparsed:
            items.append(message(f'Didn’t understand “{query.unparsed}”',
                                 'Try e.g. tomorrow, fri, 14/10, next week', ERROR_ICON))
        if query.when.date:
            first = query.when.date
            last = first + dt.timedelta(days=query.when.span_days - 1)
            start = dt.datetime.combine(first, dt.time.min)
            end = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min)
            label = day_label(first, today) if first == last else f'{day_label(first, today)} – {day_label(last, today)}'
            events = extension.store.events(calendars, start, end)
        else:
            days = extension.pref_int('days_ahead', 7)
            start = dt.datetime.combine(today, dt.time.min)
            end = start + dt.timedelta(days=days)
            label = f'in the next {days} days'
            events = [e for e in extension.store.events(calendars, start, end) if not _ended(e, now)]

        items += [extension.event_item(e, today) for e in events[:MAX_EVENTS]]
        if not events:
            items.append(message(f'No events {label}' if not query.when.date else f'Nothing on {label}',
                                 'Type a title to create one, e.g. “lunch with Bob tomorrow 12:30”'))
        return items

    @staticmethod
    def create_items(query, calendars, extension, now):
        today = now.date()
        writable = extension.last_used_first([c for c in calendars if not c.readonly])
        if not writable:
            return [message('No writable calendar', 'All matching calendars are read-only', ERROR_ICON)]

        duration = dt.timedelta(minutes=extension.pref_int('default_duration', 60))
        start, end, all_day = query.span(today, duration)
        when = format_span(start, end, all_day, today)
        details = [when]
        if query.description:
            details.append(query.description)
        if query.unparsed:
            details.append(f'⚠ ignored “{query.unparsed}”')

        items = []
        for cal in writable:
            data = {
                'action': 'create',
                'calendar': cal.uid,
                'title': query.title,
                'start': start.isoformat(),
                'end': end.isoformat(),
                'all_day': all_day,
                'description': query.description,
            }
            items.append(ExtensionResultItem(
                icon=color_icon(cal.color),
                name=f'Add “{query.title}” to {cal.name}',
                description=' · '.join(details),
                highlightable=False,
                on_enter=ExtensionCustomAction(data, keep_app_open=True),
            ))

        # What is already planned around then, across all (non-excluded) calendars
        day_start = dt.datetime.combine(start if all_day else start.date(), dt.time.min)
        day_end = dt.datetime.combine(end if all_day else end.date() + dt.timedelta(days=1), dt.time.min)
        planned = extension.store.events(extension.calendars(), day_start, day_end)
        items += [extension.event_item(e, today, suffix='  (planned)') for e in planned[:CONTEXT_EVENTS]]
        return items

    @staticmethod
    def list_calendars(event, extension):
        keyword = event.get_keyword()
        items = []
        for cal in extension.calendars(include_excluded=True):
            flags = [cal.account] if cal.account else []
            if cal.readonly:
                flags.append('read-only')
            if cal.excluded:
                flags.append('excluded in preferences')
            first_word = cal.name.split()[0] if cal.name.split() else cal.name
            items.append(ExtensionResultItem(
                icon=color_icon(cal.color),
                name=cal.name,
                description=' · '.join(flags) + ' — Enter: show its events · Alt+Enter: copy name',
                highlightable=False,
                on_enter=SetUserQueryAction(f'{keyword} #{first_word} '),
                on_alt_enter=CopyToClipboardAction(cal.name),
            ))
        return items or [message('No calendars found', icon=ERROR_ICON)]


def _ended(event, now):
    end = event.end
    if isinstance(end, dt.datetime):
        return end <= now
    return end <= now.date()


class ItemEnterEventListener(EventListener):

    def on_event(self, event, extension):
        data = event.get_data() or {}
        if data.get('action') == 'open':
            try:
                subprocess.Popen(['gnome-calendar', '--uuid', data['id']], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                logger.exception('Could not start gnome-calendar')
            return HideWindowAction()
        if data.get('action') == 'create':
            return RenderResultListAction([self.create(data, extension)])
        return HideWindowAction()

    @staticmethod
    def create(data, extension):
        cal = next((c for c in extension.calendars() if c.uid == data['calendar']), None)
        if cal is None or cal.readonly:
            return message('Calendar no longer available', icon=ERROR_ICON, on_enter=HideWindowAction())

        parse = dt.date.fromisoformat if data['all_day'] else dt.datetime.fromisoformat
        start, end = parse(data['start']), parse(data['end'])
        try:
            uid = extension.store.create_event(cal, data['title'], start, end, data['all_day'], data.get('description'))
        except Exception as e:
            logger.exception('Could not create event')
            return message('Could not create the event', str(e), ERROR_ICON, HideWindowAction())

        extension.state['last_calendar'] = cal.uid
        save_state(extension.state)
        when = format_span(start, end, data['all_day'], dt.date.today())
        if uid is None:
            return message(f'Adding “{data["title"]}” to {cal.name}…',
                           f'{when} — the calendar isn’t answering yet: the event is saved as soon as it does',
                           color_icon(cal.color), HideWindowAction())
        return ExtensionResultItem(
            icon=color_icon(cal.color),
            name=f'Added “{data["title"]}” to {cal.name}',
            description=f'{when} — Enter: open in GNOME Calendar',
            highlightable=False,
            on_enter=open_action(f'{cal.uid}:{uid}', data['title'], when),
        )


if __name__ == '__main__':
    CalendarExtension().run()
