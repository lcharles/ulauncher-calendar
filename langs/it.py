# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""Italiano."""

# Months only count next to a day number ("14 maggio").
MONTHS = {
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
    'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
}
WEEKDAYS = {'lunedì': 0, 'lunedi': 0, 'martedì': 1, 'martedi': 1, 'mercoledì': 2, 'mercoledi': 2,
            'giovedì': 3, 'giovedi': 3, 'venerdì': 4, 'venerdi': 4, 'sabato': 5, 'domenica': 6}
NUMBERS = {'un': 1, 'uno': 1, 'una': 1, 'due': 2, 'tre': 3, 'quattro': 4, 'cinque': 5,
           'sei': 6, 'sette': 7, 'otto': 8, 'nove': 9, 'dieci': 10}
RELATIVE_DAYS = {
    r'oggi|stasera|stanotte': 0,
    r'domani': 1,
    r'ieri': -1,
    r'dopodomani': 2,
}
UNITS = {'day': r'giorni|giorno', 'week': r'settimane?|settimana', 'month': r'mes[ei]',
         'hour': r'ore|ora', 'minute': r'minuti|minuto'}

ORDINAL = r'º|°'
ON = r'il'
DAY_FROM = r'dal'
DAY_TO = r'al'
RANGE_TO = r'al|fino\s+al'
IN = r'tra|fra'
THIS = r'questo|questa'
NEXT = r'prossim[oa]'                   # il prossimo lunedì
NEXT_AFTER = r'prossim[oa]'             # lunedì prossimo
ARTICLE = r'il|la|lo'
WEEK = r'settimana'
WEEKEND = r'fine\s+settimana|week[\s-]?end'
FOR = r'per'
AND = r'e'
HALF_HOUR = r"mezz['’]ora|mezza\s+ora"
ALL_DAY = r'tutto\s+il\s+giorno|tutta\s+la\s+giornata'
AT = r"alle|all['’]"                    # alle 15, all'una
TIME_FROM = r'dalle|da'
TIME_BETWEEN = r'tra|fra'
TIME_TO = r'alle|a'
TIME_ARTICLE = r'le'                    # tra le 9 e le 11
NOON = r'mezzogiorno'
MIDNIGHT = r'mezzanotte'
FILLERS = r'il|a|alle|dalle|dal|per|tra|fra|da'
