# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""English."""

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
NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
           'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
RELATIVE_DAYS = {
    r'today|tonight': 0,
    r'tomorrow|tmrw|tmr': 1,
    r'yesterday': -1,
    r'(?:the\s+)?day\s+after\s+tomorrow': 2,
}
UNITS = {'day': r'days?', 'week': r'weeks?', 'month': r'months?',
         'hour': r'hours?', 'minute': r'mins?|minutes?'}

ORDINAL = r'st|nd|rd|th'
ON = r'on'
THE = r'the'
OF = r'of'
DAY_FROM = r'from'
DAY_TO = r'to'
RANGE_TO = r'to|until|till|through|thru'
IN = r'in'
THIS = r'this|coming'
NEXT = r'next'
ARTICLE = r'the'
WEEK = r'week'
WEEKEND = r'week[\s-]?end'
FOR = r'for'
AND = r'and'
HALF_HOUR = r'half\s+an?\s+hour'
ALL_DAY = r'all[\s-]?day'
AT = r'at'
TIME_FROM = r'from'
TIME_BETWEEN = r'between'
TIME_TO = r'to|until|till'
NOON = r'noon|midday'
MIDNIGHT = r'midnight'
FILLERS = r'on|at|from|for|by|between'
