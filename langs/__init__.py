# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""
Language packs for the date/time parser.

Each pack (en.py, fr.py, ...) is plain data: word tables and small regex pieces
for the slots below. The parser joins the packs the user selected (one or two)
into a Vocabulary and builds its rules from it. Words a language doesn't have
are left empty ('').

Word tables (lower case; months only count next to a day number):
    MONTHS, WEEKDAYS        word -> 1..12 / 0 (Monday)..6
    NUMBERS                 number word -> int ("in two days", "for three hours")
    RELATIVE_DAYS           regex -> day offset (today, tomorrow, the day after tomorrow, ...)
    UNITS                   'day' / 'week' / 'month' / 'hour' / 'minute' -> regex

Regex pieces (alternatives joined with "|", matched case-insensitively):
    ORDINAL       after a day number                 st|nd|rd|th, er, \\.
    ON            before a date                       on, le, am, el, il
    THE           between ON and the day number       the
    OF            between day and month               of, de
    YEAR_OF       between month and year              de
    DAY_FROM      before a day range                  from, du, vom, del, dal
    DAY_TO        inside a day range ("14 to 18 oct") to, au, bis, al
    RANGE_TO      between two dates                   to|until|through, au, bis, al|hasta
    IN            before an amount of time to wait    in, dans, en|dentro de, tra|fra
    THIS / NEXT   before a weekday, week or weekend   this|coming / next
    NEXT_AFTER    after them ("vendredi prochain")    prochain, prossimo, que viene
    ARTICLE       optional, before THIS/NEXT/WEEK     the, la, die, el, il
    WEEK, WEEKEND
    FOR           before a duration                   for, pendant, für, durante, per
    AND           "1 hour and 30", "between 9 and 11" and, et, und, y, e
    HALF_HOUR, ALL_DAY
    AT            before a time                       at, à, um, a las, alle
    TIME_FROM, TIME_BETWEEN, TIME_TO                  from/between/to, de/entre/à, von/zwischen/bis
    TIME_ARTICLE  after those ("entre las 9 y las 11") las, le
    HOUR_MARK     after an hour ("15h", "15 Uhr")     heures, uhr
    NOON, MIDNIGHT
    FILLERS       words dropped from the title when they precede a recognised date or time
"""

import importlib
import re
from types import SimpleNamespace

AVAILABLE = ('en', 'fr', 'de', 'es', 'it')
NAMES = {'en': 'English', 'fr': 'Français', 'de': 'Deutsch', 'es': 'Español', 'it': 'Italiano'}

TABLES = ('MONTHS', 'WEEKDAYS', 'NUMBERS', 'RELATIVE_DAYS')
PIECES = ('ORDINAL', 'ON', 'THE', 'OF', 'YEAR_OF', 'DAY_FROM', 'DAY_TO', 'RANGE_TO', 'IN',
          'THIS', 'NEXT', 'NEXT_AFTER', 'ARTICLE', 'WEEK', 'WEEKEND', 'FOR', 'AND',
          'HALF_HOUR', 'ALL_DAY', 'AT', 'TIME_FROM', 'TIME_BETWEEN', 'TIME_TO', 'TIME_ARTICLE',
          'HOUR_MARK', 'NOON', 'MIDNIGHT', 'FILLERS')
UNIT_KINDS = ('day', 'week', 'month', 'hour', 'minute')

# Shared by every language
BASE = {
    'HOUR_MARK': r'h',                  # 15h, 15h30
    'UNITS': {'hour': r'h|hrs?', 'minute': r'm|min'},
}
NEVER = r'(?!)'                         # a regex that matches nothing, for empty slots


def load(codes):
    """Vocabulary for the given language codes, the first one winning when a word means
    different things in two of them. Unknown codes are ignored; none at all means English."""
    codes = [c for c in dict.fromkeys(codes) if c in AVAILABLE] or ['en']
    packs = [importlib.import_module(f'{__name__}.{c}') for c in codes]

    vocab = SimpleNamespace(codes=tuple(codes))
    for name in TABLES:
        merged = {}
        for pack in reversed(packs):    # primary last, so it wins
            merged.update(getattr(pack, name, {}))
        setattr(vocab, name.lower(), merged)
    for name in PIECES:
        parts = [BASE.get(name, '')] + [getattr(pack, name, '') for pack in packs]
        setattr(vocab, name, _alternatives(parts))
    vocab.units = {kind: _alternatives([BASE['UNITS'].get(kind, '')] +
                                       [getattr(pack, 'UNITS', {}).get(kind, '') for pack in packs])
                   for kind in UNIT_KINDS}
    return vocab


def _alternatives(parts):
    parts = [p for p in parts if p]
    return '|'.join(f'(?:{p})' for p in parts) if parts else NEVER


def words(table):
    """Regex alternation of a word table's keys, longest first."""
    return '|'.join(sorted(table, key=len, reverse=True)) if table else NEVER


def lookup(table, text):
    """Value of the table entry whose key (a word or a regex) matches `text` entirely."""
    text = text.lower()
    if text in table:
        return table[text]
    for key, value in table.items():
        if re.fullmatch(key, text, re.I):
            return value
    raise KeyError(text)
