# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""Run with: /usr/bin/python3 -m unittest test_calendarstore   (from this folder)

CalendarStore against fake calendars (no Evolution Data Server needed): one whose
server doesn't answer mustn't hold up queries."""

import datetime as dt
import threading
import time
import unittest

from calendars import Calendar, CalendarStore, ICalGLib, _local_tz, _to_ical, _to_python


class FakeClient:
    """Just enough of ECal.Client. With `hung`, calls block until `release` is set."""

    def __init__(self, *events, hung=False, fail_create=False):
        self.events = list(events)          # (summary, start datetime)
        self.release = threading.Event()
        if not hung:
            self.release.set()
        self.fail_create = fail_create

    def generate_instances_sync(self, start, end, cancellable, callback):
        self.release.wait(10)
        for summary, when in self.events:
            comp = ICalGLib.Component.new_vevent()
            comp.set_uid(summary)
            comp.set_summary(summary)
            istart = _to_ical(when, _local_tz())
            iend = _to_ical(when + dt.timedelta(hours=1), _local_tz())
            callback(comp, istart, iend)

    def add_timezone_sync(self, zone, cancellable):
        self.release.wait(10)

    def create_object_sync(self, comp, flags, cancellable):
        self.release.wait(10)
        if self.fail_create:
            raise RuntimeError('server said no')
        self.events.append((comp.get_summary(), _to_python(comp.get_dtstart(), _local_tz())))
        return True, comp.get_uid()


def calendar(uid, client):
    return Calendar(uid=uid, name=uid.title(), account='', color='#000000', readonly=False, client=client)


class SlowCalendarTest(unittest.TestCase):

    def setUp(self):
        self.today = dt.datetime.combine(dt.date.today(), dt.time.min)
        self.hung = FakeClient(('Standup', self.today + dt.timedelta(hours=9)), hung=True)
        self.addCleanup(self.hung.release.set)
        self.local = FakeClient(('Lunch', self.today + dt.timedelta(hours=12)))
        self.cals = [calendar('work', self.hung), calendar('home', self.local)]
        self.store = CalendarStore(wait=0.3)

    def summaries(self):
        self.store.errors = []
        events = self.store.events(self.cals, self.today, self.today + dt.timedelta(days=1))
        return [e.summary for e in events]

    def test_hung_calendar(self):
        start = time.monotonic()
        self.assertEqual(self.summaries(), ['Lunch'])
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(self.store.errors, ['Work: not answering yet'])
        start = time.monotonic()
        self.assertEqual(self.summaries(), ['Lunch'])
        self.assertLess(time.monotonic() - start, 0.2)        # the read under way isn't waited for again
        self.hung.release.set()
        time.sleep(0.2)
        self.assertEqual(self.summaries(), ['Standup', 'Lunch'])
        self.assertEqual(self.store.errors, [])

    def test_create_in_hung_calendar(self):
        work = self.cals[0]
        self.hung.fail_create = True
        start = time.monotonic()
        uid = self.store.create_event(work, 'Review', self.today + dt.timedelta(hours=15),
                                      self.today + dt.timedelta(hours=16), False, wait=0.3)
        self.assertIsNone(uid)                                # saving carries on in the background
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(self.store.pop_failures(), [])
        self.hung.release.set()
        time.sleep(0.2)
        self.assertEqual(self.store.pop_failures(), ['Could not add “Review” to Work: server said no'])
        self.assertEqual(self.store.pop_failures(), [])

    def test_create(self):
        home = self.cals[1]
        self.assertEqual(self.summaries(), ['Lunch'])
        uid = self.store.create_event(home, 'Dinner', self.today + dt.timedelta(hours=19),
                                      self.today + dt.timedelta(hours=20), False)
        self.assertIsNotNone(uid)
        self.assertEqual(self.summaries(), ['Lunch', 'Dinner'])   # the cached day was dropped


if __name__ == '__main__':
    unittest.main()
