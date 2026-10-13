# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""Deutsch."""

# Months only count next to a day number ("14. Mai"), so "Mai" alone stays a word.
MONTHS = {
    'januar': 1, 'jänner': 1, 'jan': 1, 'februar': 2, 'feb': 2, 'märz': 3, 'maerz': 3,
    'april': 4, 'apr': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8, 'aug': 8,
    'september': 9, 'sept': 9, 'oktober': 10, 'okt': 10, 'november': 11, 'nov': 11,
    'dezember': 12, 'dez': 12,
}
# Two-letter abbreviations ("Mo", "Di", "So", ...) are left out: too ambiguous.
WEEKDAYS = {'montag': 0, 'dienstag': 1, 'mittwoch': 2, 'donnerstag': 3, 'freitag': 4,
            'samstag': 5, 'sonnabend': 5, 'sonntag': 6}
NUMBERS = {'ein': 1, 'eine': 1, 'einen': 1, 'einem': 1, 'einer': 1, 'zwei': 2, 'drei': 3,
           'vier': 4, 'fünf': 5, 'fuenf': 5, 'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10}
RELATIVE_DAYS = {
    r'heute(?:\s+abend)?': 0,
    r'morgen': 1,
    r'gestern': -1,
    r'(?:ü|ue)bermorgen': 2,
}
UNITS = {'day': r'tagen?|tage?', 'week': r'wochen?', 'month': r'monaten?|monate?',
         'hour': r'std|stunden?', 'minute': r'minuten?'}

ORDINAL = r'\.'                         # 14. Oktober
ON = r'am'
DAY_FROM = r'vom'
DAY_TO = r'bis(?:\s+zum)?'
RANGE_TO = r'bis(?:\s+zum)?'
IN = r'in'
THIS = r'diese[nrs]?'
NEXT = r'n(?:ä|ae)chste[nrs]?|kommende[nrs]?'
ARTICLE = r'die|der|das|den|dem'
WEEK = r'woche'
WEEKEND = r'wochenende'
FOR = r'für|fuer'
AND = r'und'
HALF_HOUR = r'eine\s+halbe\s+stunde'
ALL_DAY = r'ganzt(?:ä|ae)gig|den\s+ganzen\s+tag'
AT = r'um'
TIME_FROM = r'von|ab'
TIME_BETWEEN = r'zwischen'
TIME_TO = r'bis'
HOUR_MARK = r'uhr'                      # 15 Uhr, 15:30 Uhr
NOON = r'mittags?'
MIDNIGHT = r'mitternacht'
FILLERS = r'am|um|von|vom|für|zwischen|ab|bis'
