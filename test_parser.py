# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""Run with: /usr/bin/python3 -m unittest test_parser   (from this folder)"""

import datetime as dt
import unittest

from parser import Parser

NOW = dt.datetime(2026, 10, 13, 10, 0)    # a Tuesday
D = dt.date
T = dt.time


class ParserTest(unittest.TestCase):

    def setUp(self):
        self.p = Parser('DMY')

    def check(self, text, title, date=None, start=None, end=None, **extra):
        q = self.p.parse(text, now=NOW)
        self.assertEqual(q.title, title, f'title for {text!r}')
        self.assertEqual(q.when.date, date, f'date for {text!r}')
        self.assertEqual(q.when.start, start, f'start for {text!r}')
        self.assertEqual(q.when.end, end, f'end for {text!r}')
        for key, value in extra.items():
            actual = getattr(q, key) if hasattr(q, key) else getattr(q.when, key)
            self.assertEqual(actual, value, f'{key} for {text!r}')
        return q

    # --- plain titles stay intact
    def test_plain_titles(self):
        self.check('buy 2 tickets', 'buy 2 tickets')
        self.check('call 0797526709', 'call 0797526709')
        self.check('fun in the sun', 'fun in the sun')
        self.check('fix bug #123', 'fix bug #123')
        self.check('email bob@example.com', 'email bob@example.com')
        self.check('score 9-10', 'score 9-10')
        self.check('room 3.14', 'room 3.14')
        self.check('workout 2h', 'workout 2h')
        self.check('dinner at Joe\'s', 'dinner at Joe\'s')

    # --- relative dates
    def test_relative_days(self):
        self.check('dentist tomorrow', 'dentist', D(2026, 10, 14))
        self.check('tmrw dentist', 'dentist', D(2026, 10, 14))
        self.check('party day after tomorrow', 'party', D(2026, 10, 15))
        self.check('review today', 'review', D(2026, 10, 13))
        self.check('trip in 3 days', 'trip', D(2026, 10, 16))
        self.check('trip in two weeks', 'trip', D(2026, 10, 27))
        self.check('renew in 4 months', 'renew', D(2027, 2, 13))

    def test_weekdays(self):
        self.check('drinks friday', 'drinks', D(2026, 10, 16))
        self.check('drinks on fri', 'drinks', D(2026, 10, 16))
        self.check('standup tuesday', 'standup', D(2026, 10, 13))        # today is Tuesday
        self.check('standup mon', 'standup', D(2026, 10, 19))
        self.check('sync next monday', 'sync', D(2026, 10, 19))
        self.check('sync next wednesday', 'sync', D(2026, 10, 21))       # next week's, not tomorrow
        self.check('sync this wednesday', 'sync', D(2026, 10, 14))
        self.check('hike sunday', 'hike', D(2026, 10, 18))

    def test_weeks(self):
        self.check('next week', '', D(2026, 10, 19), span_days=7)
        self.check('this week', '', D(2026, 10, 13), span_days=6)
        self.check('weekend', '', D(2026, 10, 17), span_days=2)

    # --- absolute dates
    def test_absolute_dates(self):
        self.check('meeting 14/10', 'meeting', D(2026, 10, 14))
        self.check('meeting on 14.10.', 'meeting', D(2026, 10, 14))
        self.check('meeting 14.10.2027', 'meeting', D(2027, 10, 14))
        self.check('meeting 1/10', 'meeting', D(2027, 10, 1))            # already passed: next year
        self.check('meeting 2026-12-24', 'meeting', D(2026, 12, 24))
        self.check('meeting 24 dec', 'meeting', D(2026, 12, 24))
        self.check('meeting december 24th', 'meeting', D(2026, 12, 24))
        self.check('meeting on the 3rd of march 2027', 'meeting', D(2027, 3, 3))
        self.check('may the force', 'may the force')

    def test_date_ranges(self):
        self.check('trip 14/10-18/10', 'trip', D(2026, 10, 14), end_date=D(2026, 10, 18))
        self.check('trip 14-18 oct', 'trip', D(2026, 10, 14), end_date=D(2026, 10, 18))
        self.check('trip oct 14-18', 'trip', D(2026, 10, 14), end_date=D(2026, 10, 18))
        self.check('trip oct 30 - 2', 'trip', D(2026, 10, 30), end_date=D(2026, 11, 2))
        self.check('standup monday-friday', 'standup', D(2026, 10, 19), end_date=D(2026, 10, 23))
        self.check('holiday from 24 dec to 2 jan', 'holiday', D(2026, 12, 24), end_date=D(2027, 1, 2))
        self.check('conference fri to next tuesday', 'conference', D(2026, 10, 16), end_date=D(2026, 10, 20))
        q = self.p.parse('trip 14/10-18/10', now=NOW)
        self.assertEqual(q.span(NOW.date()), (D(2026, 10, 14), D(2026, 10, 19), True))
        self.assertEqual(q.when.span_days, 5)
        # a date followed by a time range is not a date range
        self.check('call 14/10 9-10am', 'call', D(2026, 10, 14), T(9), T(10))

    def test_mdy(self):
        q = Parser('MDY').parse('meeting 10/14', now=NOW)
        self.assertEqual(q.when.date, D(2026, 10, 14))

    # --- times
    def test_times(self):
        self.check('lunch 12:30', 'lunch', None, T(12, 30))
        self.check('lunch at 12:30', 'lunch', None, T(12, 30))
        self.check('call 3pm', 'call', None, T(15, 0))
        self.check('call at 3:30 pm', 'call', None, T(15, 30))
        self.check('call 12am', 'call', None, T(0, 0))
        self.check('call 15h', 'call', None, T(15, 0))
        self.check('call 15h30', 'call', None, T(15, 30))
        self.check('lunch at noon', 'lunch', None, T(12, 0))
        self.check('call at 3', 'call', None, T(15, 0))
        self.check('call at 9', 'call', None, T(9, 0))
        self.check('call in 2 hours', 'call', D(2026, 10, 13), T(12, 0))
        self.check('call in 90 min', 'call', D(2026, 10, 13), T(11, 30))

    def test_ranges(self):
        self.check('standup 9-10am', 'standup', None, T(9), T(10))
        self.check('lunch 11-1pm', 'lunch', None, T(11), T(13))
        self.check('workshop 14:00-15:30', 'workshop', None, T(14), T(15, 30))
        self.check('workshop 14h-16h', 'workshop', None, T(14), T(16))
        self.check('workshop 2pm to 4pm', 'workshop', None, T(14), T(16))
        self.check('class from 9 to 11', 'class', None, T(9), T(11))
        self.check('class between 9 and 11am', 'class', None, T(9), T(11))
        self.check('party 22:00-02:00', 'party', None, T(22), T(2))
        self.check('doctor 9.30-10.30', 'doctor', None, T(9, 30), T(10, 30))

    def test_durations(self):
        self.check('gym 6pm for 1h30', 'gym', None, T(18), duration=dt.timedelta(minutes=90))
        self.check('gym 6pm for 45 min', 'gym', None, T(18), duration=dt.timedelta(minutes=45))
        self.check('gym 6pm for 1.5h', 'gym', None, T(18), duration=dt.timedelta(minutes=90))
        self.check('gym 6pm for an hour', 'gym', None, T(18), duration=dt.timedelta(hours=1))
        self.check('offsite tomorrow all day', 'offsite', D(2026, 10, 14), all_day=True)

    # --- combinations
    def test_combined(self):
        self.check('lunch with Bob tomorrow at 12:30', 'lunch with Bob', D(2026, 10, 14), T(12, 30))
        self.check('friday 6pm drinks', 'drinks', D(2026, 10, 16), T(18))
        self.check('standup mon 9-9:15am', 'standup', D(2026, 10, 19), T(9), T(9, 15))
        self.check('dentist on 20/10 at 8:45', 'dentist', D(2026, 10, 20), T(8, 45))
        self.check('meeting wed 14 oct 9am', 'meeting', D(2026, 10, 14), T(9))     # weekday restating the date

    # --- markers
    def test_quotes_protect_title(self):
        self.check('"Friday release" party fri 6pm', 'Friday release party', D(2026, 10, 16), T(18))
        self.check('meet at "Joe\'s" 7pm', 'meet at Joe\'s', None, T(19))

    def test_explicit_when(self):
        self.check('call mom @ tomorrow 9am', 'call mom', D(2026, 10, 14), T(9))
        self.check('review friday notes @ mon', 'review friday notes', D(2026, 10, 19))
        q = self.check('x @ tomorrow banana', 'x', D(2026, 10, 14))
        self.assertEqual(q.unparsed, 'banana')
        q = self.check('x @ 25/13', 'x')
        self.assertEqual(q.unparsed, '25/13')

    def test_explicit_when_fallback(self):
        q = self.p.parse('review @ demain', now=NOW)
        self.assertEqual(q.when.date, D(2026, 10, 14))
        self.assertIsNone(q.unparsed)

    # --- French, with or without "@"
    def test_french_dates(self):
        self.check('réunion demain', 'réunion', D(2026, 10, 14))
        self.check("bilan aujourd'hui", 'bilan', D(2026, 10, 13))
        self.check('bilan aujourd’hui', 'bilan', D(2026, 10, 13))
        self.check('apéro ce soir', 'apéro', D(2026, 10, 13))
        self.check('fête après-demain', 'fête', D(2026, 10, 15))
        self.check('fête apres demain', 'fête', D(2026, 10, 15))
        self.check('réunion mercredi', 'réunion', D(2026, 10, 14))
        self.check('réunion ce mercredi', 'réunion', D(2026, 10, 14))
        self.check('réunion mercredi prochain', 'réunion', D(2026, 10, 21))   # like "next wednesday"
        self.check('réunion lundi', 'réunion', D(2026, 10, 19))
        self.check('rando dimanche', 'rando', D(2026, 10, 18))
        self.check('voyage dans 3 jours', 'voyage', D(2026, 10, 16))
        self.check('voyage dans deux semaines', 'voyage', D(2026, 10, 27))
        self.check('réunion le 14 octobre', 'réunion', D(2026, 10, 14))
        self.check('réunion le 1er novembre', 'réunion', D(2026, 11, 1))
        self.check('réunion 3 février 2027', 'réunion', D(2027, 2, 3))
        self.check('réunion 15 aout', 'réunion', D(2027, 8, 15))
        self.check('semaine prochaine', '', D(2026, 10, 19), span_days=7)
        self.check('la semaine prochaine', '', D(2026, 10, 19), span_days=7)
        self.check('cette semaine', '', D(2026, 10, 13), span_days=6)
        self.check('ce week-end', '', D(2026, 10, 17), span_days=2)
        self.check('le week-end prochain', '', D(2026, 10, 24), span_days=2)
        self.check('vacances du 20 au 23 octobre', 'vacances', D(2026, 10, 20), end_date=D(2026, 10, 23))
        self.check('stage lundi au vendredi', 'stage', D(2026, 10, 19), end_date=D(2026, 10, 23))
        self.check('mars attacks', 'mars attacks')
        self.check('mer du nord', 'mer du nord')

    def test_french_times(self):
        self.check('réunion à 14h', 'réunion', None, T(14))
        self.check('réunion 14 h', 'réunion', None, T(14))
        self.check('réunion 14h00', 'réunion', None, T(14))
        self.check('réunion 14 h 30', 'réunion', None, T(14, 30))
        self.check('réunion à 14 heures', 'réunion', None, T(14))
        self.check('déjeuner à midi', 'déjeuner', None, T(12))
        self.check('feu d’artifice à minuit', 'feu d’artifice', None, T(0))
        self.check('appel dans 2 heures', 'appel', D(2026, 10, 13), T(12))
        self.check('appel dans 30 min', 'appel', D(2026, 10, 13), T(10, 30))
        self.check('cours de 9h à 11h', 'cours', None, T(9), T(11))
        self.check('cours entre 9h et 11h', 'cours', None, T(9), T(11))
        self.check('cours 9h-11h', 'cours', None, T(9), T(11))
        self.check('sport 18h pendant 1h30', 'sport', None, T(18), duration=dt.timedelta(minutes=90))
        self.check('sport 18h pour 45 min', 'sport', None, T(18), duration=dt.timedelta(minutes=45))
        self.check('séminaire demain toute la journée', 'séminaire', D(2026, 10, 14), all_day=True)
        self.check('pause café', 'pause café')
        self.check('salle à manger', 'salle à manger')

    def test_french_combined(self):
        self.check('réunion mercredi 14h', 'réunion', D(2026, 10, 14), T(14))
        self.check('réunion @ mercredi 14h', 'réunion', D(2026, 10, 14), T(14))
        self.check('réunion @ mercredi à 14h', 'réunion', D(2026, 10, 14), T(14))
        self.check('réunion @ mercredi prochain 14h', 'réunion', D(2026, 10, 21), T(14))
        self.check('réunion @ jeudi prochain', 'réunion', D(2026, 10, 22))
        self.check('réunion @ lundi de 14h à 16h', 'réunion', D(2026, 10, 19), T(14), T(16))
        self.check('dentiste le 20/10 à 8h45', 'dentiste', D(2026, 10, 20), T(8, 45))
        self.check('rdv mercredi 14 octobre à 9h30', 'rdv', D(2026, 10, 14), T(9, 30))

    def test_description_and_calendar(self):
        q = self.check('review 3pm :: bring slides #work', 'review', None, T(15))
        self.assertEqual(q.description, 'bring slides')
        self.assertEqual(q.calendar, 'work')
        q = self.check('#pers tomorrow', '', D(2026, 10, 14))
        self.assertEqual(q.calendar, 'pers')
        q = self.check('standup #work mon 9am', 'standup', D(2026, 10, 19), T(9))
        self.assertEqual(q.calendar, 'work')
        self.assertEqual(self.p.parse('#', now=NOW).calendar, '')

    # --- spans
    def test_span(self):
        today = NOW.date()
        q = self.p.parse('x tomorrow 3pm', now=NOW)
        self.assertEqual(q.span(today), (dt.datetime(2026, 10, 14, 15), dt.datetime(2026, 10, 14, 16), False))
        q = self.p.parse('x 22:00-01:00', now=NOW)
        self.assertEqual(q.span(today)[1], dt.datetime(2026, 10, 14, 1))
        q = self.p.parse('x friday', now=NOW)
        self.assertEqual(q.span(today), (D(2026, 10, 16), D(2026, 10, 17), True))


    def test_spans_are_created_whole(self):
        today = NOW.date()
        self.assertEqual(self.p.parse('trip next week', now=NOW).span(today),
                         (D(2026, 10, 19), D(2026, 10, 26), True))
        self.assertEqual(self.p.parse('ski weekend', now=NOW).span(today),
                         (D(2026, 10, 17), D(2026, 10, 19), True))
        # with a time it is one timed event, on the first day
        self.assertEqual(self.p.parse('standup next week 9am', now=NOW).span(today)[:2],
                         (dt.datetime(2026, 10, 19, 9), dt.datetime(2026, 10, 19, 10)))

    def test_leap_day(self):
        self.check('party 29/02', 'party', D(2028, 2, 29))
        self.check('party 29 feb', 'party', D(2028, 2, 29))

    def test_calendar_selector(self):
        self.check('milk #2026-Goals', 'milk', calendar='2026-Goals')
        self.check('#Q4 report', 'report', calendar='Q4')
        self.check('fix bug #12', 'fix bug #12', calendar=None)

if __name__ == '__main__':
    unittest.main()
