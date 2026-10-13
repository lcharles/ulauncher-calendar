"""Language packs: German, Spanish, Italian, and how languages combine.

Run with: /usr/bin/python3 -m unittest test_langs   (from this folder)
English and French are covered by test_parser.py.
"""

import datetime as dt
import itertools
import unittest
import warnings

import langs
from parser import Parser

NOW = dt.datetime(2026, 10, 13, 10, 0)    # a Tuesday
D = dt.date
T = dt.time


class LangTest(unittest.TestCase):
    languages = ('en',)

    def setUp(self):
        warnings.simplefilter('ignore', DeprecationWarning)     # dateparser on Python 3.14
        self.p = Parser('DMY', self.languages)

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


class GermanTest(LangTest):
    languages = ('de',)

    def test_dates(self):
        self.check('Termin am Freitag', 'Termin', D(2026, 10, 16))
        self.check('Treffen nächsten Mittwoch', 'Treffen', D(2026, 10, 21))
        self.check('Reise kommenden Montag', 'Reise', D(2026, 10, 19))
        self.check('Meeting übermorgen', 'Meeting', D(2026, 10, 15))
        self.check('Geburtstag am 14. Oktober', 'Geburtstag', D(2026, 10, 14))
        self.check('Konzert am 3.11.', 'Konzert', D(2026, 11, 3))
        self.check('Sport in 3 Tagen', 'Sport', D(2026, 10, 16))
        self.check('Urlaub vom 20. bis 23. Oktober', 'Urlaub', D(2026, 10, 20), end_date=D(2026, 10, 23))
        self.check('Ausflug nächste Woche', 'Ausflug', D(2026, 10, 19), span_days=7)
        self.check('diese Woche', '', D(2026, 10, 13), span_days=6)
        self.check('Wandern am Wochenende', 'Wandern', D(2026, 10, 17), span_days=2)
        self.check('nächstes Wochenende', '', D(2026, 10, 24), span_days=2)

    def test_times(self):
        self.check('Zahnarzt morgen um 15 Uhr', 'Zahnarzt', D(2026, 10, 14), T(15))
        self.check('Kino heute Abend um 20 Uhr', 'Kino', D(2026, 10, 13), T(20))
        self.check('Mittagessen um 12:30', 'Mittagessen', None, T(12, 30))
        self.check('Frühstück um 8:15 Uhr', 'Frühstück', None, T(8, 15))
        self.check('Anruf um 3 Uhr', 'Anruf', None, T(3))
        self.check('Besprechung von 9 bis 11 Uhr', 'Besprechung', None, T(9), T(11))
        self.check('Call zwischen 14 und 15 Uhr', 'Call', None, T(14), T(15))
        self.check('Lauf in 2 Stunden', 'Lauf', D(2026, 10, 13), T(12))
        self.check('Essen mittags', 'Essen', None, T(12))
        self.check('Workshop für 2 Stunden', 'Workshop', duration=dt.timedelta(hours=2))
        self.check('Pause für eine halbe Stunde', 'Pause', duration=dt.timedelta(minutes=30))
        self.check('Feier ganztägig', 'Feier', all_day=True)

    def test_titles_survive(self):
        self.check('Termin am Bahnhof', 'Termin am Bahnhof')
        self.check('acht Punkte', 'acht Punkte')
        self.check('Mai Liste', 'Mai Liste')
        self.check('Woche der Gesundheit', 'Woche der Gesundheit')


class SpanishTest(LangTest):
    languages = ('es',)

    def test_dates(self):
        self.check('cena el viernes', 'cena', D(2026, 10, 16))
        self.check('cita el próximo miércoles', 'cita', D(2026, 10, 21))
        self.check('cita el miércoles que viene', 'cita', D(2026, 10, 21))
        self.check('reunión pasado mañana', 'reunión', D(2026, 10, 15))
        self.check('cumpleaños el 14 de octubre', 'cumpleaños', D(2026, 10, 14))
        self.check('boda 14 de octubre de 2027', 'boda', D(2027, 10, 14))
        self.check('deporte en 3 días', 'deporte', D(2026, 10, 16))
        self.check('vacaciones del 20 al 23 de octubre', 'vacaciones', D(2026, 10, 20), end_date=D(2026, 10, 23))
        self.check('viaje la semana que viene', 'viaje', D(2026, 10, 19), span_days=7)
        self.check('la próxima semana', '', D(2026, 10, 19), span_days=7)
        self.check('esta semana', '', D(2026, 10, 13), span_days=6)
        self.check('excursión este fin de semana', 'excursión', D(2026, 10, 17), span_days=2)
        self.check('el próximo fin de semana', '', D(2026, 10, 24), span_days=2)
        self.check('cena con la familia el sábado', 'cena con la familia', D(2026, 10, 17))

    def test_times(self):
        self.check('dentista mañana a las 15:00', 'dentista', D(2026, 10, 14), T(15))
        self.check('reunión a las 9', 'reunión', None, T(9))
        self.check('clase de 9 a 11', 'clase', None, T(9), T(11))
        self.check('llamada entre las 14 y las 15', 'llamada', None, T(14), T(15))
        self.check('correr en 2 horas', 'correr', D(2026, 10, 13), T(12))
        self.check('comida al mediodía', 'comida', None, T(12))
        self.check('taller durante 2 horas', 'taller', duration=dt.timedelta(hours=2))
        self.check('pausa durante media hora', 'pausa', duration=dt.timedelta(minutes=30))
        self.check('fiesta todo el día', 'fiesta', all_day=True)

    def test_titles_survive(self):
        self.check('mar y montaña', 'mar y montaña')
        self.check('dos tortillas', 'dos tortillas')
        self.check('semana santa', 'semana santa')


class ItalianTest(LangTest):
    languages = ('it',)

    def test_dates(self):
        self.check('cena venerdì', 'cena', D(2026, 10, 16))
        self.check('appuntamento mercoledì prossimo', 'appuntamento', D(2026, 10, 21))
        self.check('appuntamento il prossimo mercoledì', 'appuntamento', D(2026, 10, 21))
        self.check('riunione dopodomani', 'riunione', D(2026, 10, 15))
        self.check('compleanno il 14 ottobre', 'compleanno', D(2026, 10, 14))
        self.check('sport tra 3 giorni', 'sport', D(2026, 10, 16))
        self.check('vacanze dal 20 al 23 ottobre', 'vacanze', D(2026, 10, 20), end_date=D(2026, 10, 23))
        self.check('viaggio la prossima settimana', 'viaggio', D(2026, 10, 19), span_days=7)
        self.check('la settimana prossima', '', D(2026, 10, 19), span_days=7)
        self.check('questa settimana', '', D(2026, 10, 13), span_days=6)
        self.check('gita questo fine settimana', 'gita', D(2026, 10, 17), span_days=2)
        self.check('stasera cinema', 'cinema', D(2026, 10, 13))

    def test_times(self):
        self.check('dentista domani alle 15', 'dentista', D(2026, 10, 14), T(15))
        self.check('riunione alle 9:30', 'riunione', None, T(9, 30))
        self.check('lezione dalle 9 alle 11', 'lezione', None, T(9), T(11))
        self.check('chiamata tra le 14 e le 15', 'chiamata', None, T(14), T(15))
        self.check('corsa tra 2 ore', 'corsa', D(2026, 10, 13), T(12))
        self.check('pranzo a mezzogiorno', 'pranzo', None, T(12))
        self.check('workshop per 2 ore', 'workshop', duration=dt.timedelta(hours=2))
        self.check("pausa per mezz'ora", 'pausa', duration=dt.timedelta(minutes=30))
        self.check('festa tutto il giorno', 'festa', all_day=True)

    def test_titles_survive(self):
        self.check('sei personaggi', 'sei personaggi')
        self.check('tre uomini in barca', 'tre uomini in barca')


class CombinationTest(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', DeprecationWarning)

    def parse(self, languages, text):
        return Parser('DMY', languages).parse(text, now=NOW)

    def test_only_selected_languages_are_read(self):
        q = self.parse(('de',), 'call tomorrow')
        self.assertEqual((q.title, q.when.date), ('call tomorrow', None))
        q = self.parse(('en',), 'Termin morgen')
        self.assertEqual((q.title, q.when.date), ('Termin morgen', None))

    def test_neutral_formats_work_in_every_language(self):
        for code in langs.AVAILABLE:
            q = self.parse((code,), 'x 2026-10-20 14:30')
            self.assertEqual((q.title, q.when.date, q.when.start), ('x', D(2026, 10, 20), T(14, 30)), code)

    def test_both_languages_of_a_pair(self):
        q = self.parse(('fr', 'de'), 'réunion demain à 14h')
        self.assertEqual((q.title, q.when.date, q.when.start), ('réunion', D(2026, 10, 14), T(14)))
        q = self.parse(('fr', 'de'), 'Termin morgen um 9 Uhr')
        self.assertEqual((q.title, q.when.date, q.when.start), ('Termin', D(2026, 10, 14), T(9)))

    def test_german_am_does_not_take_english_am(self):
        q = self.parse(('en', 'de'), 'call 9 am friday')
        self.assertEqual((q.title, q.when.date, q.when.start), ('call', D(2026, 10, 16), T(9)))
        q = self.parse(('de', 'en'), 'Termin am Freitag')
        self.assertEqual((q.title, q.when.date), ('Termin', D(2026, 10, 16)))

    def test_every_pair_builds_and_keeps_plain_titles(self):
        for pair in itertools.permutations(langs.AVAILABLE, 2):
            p = Parser('DMY', pair)
            for title in ('buy 2 tickets', 'room 3.14', 'score 9-10', 'call 0797526709'):
                self.assertEqual(p.parse(title, now=NOW).title, title, f'{pair}: {title!r}')

    def test_explicit_when_falls_back_to_any_language(self):
        q = self.parse(('en', 'de'), 'review @ demain')
        self.assertEqual((q.title, q.when.date, q.unparsed), ('review', D(2026, 10, 14), None))

    def test_loading(self):
        self.assertEqual(langs.load(['xx']).codes, ('en',))
        self.assertEqual(langs.load(['de', 'de']).codes, ('de',))
        self.assertEqual(langs.load(['it', 'es']).codes, ('it', 'es'))

    def test_packs_only_define_known_slots(self):
        known = set(langs.TABLES) | set(langs.PIECES) | {'UNITS'}
        for code in langs.AVAILABLE:
            pack = __import__(f'langs.{code}', fromlist=['x'])
            names = {n for n in vars(pack) if n.isupper()}
            self.assertEqual(names - known, set(), f'{code}: unknown slot names')
            self.assertEqual(set(getattr(pack, 'UNITS', {})) - set(langs.UNIT_KINDS), set(), code)


if __name__ == '__main__':
    unittest.main()
