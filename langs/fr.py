# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Lucas Charles
"""Français."""

# Months only count next to a day number, so "mars" or "mai" alone stay words.
MONTHS = {
    'janvier': 1, 'janv': 1, 'février': 2, 'fevrier': 2, 'févr': 2, 'fevr': 2, 'mars': 3,
    'avril': 4, 'avr': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'juil': 7, 'août': 8, 'aout': 8,
    'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12, 'déc': 12,
}
# Abbreviations ("mer", "jeu", "sam", ...) are left out: too common as plain words.
WEEKDAYS = {'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3, 'vendredi': 4, 'samedi': 5, 'dimanche': 6}
NUMBERS = {'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
           'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10}
RELATIVE_DAYS = {
    r"aujourd['’]hui|ce\s+soir": 0,
    r'demain': 1,
    r'hier': -1,
    r'apr[eè]s[\s-]demain': 2,
}
UNITS = {'day': r'jours?', 'week': r'semaines?', 'month': r'mois',
         'hour': r'heures?', 'minute': r'minutes?'}

ORDINAL = r'er'                         # 1er
ON = r'le'
DAY_FROM = r'du'
DAY_TO = r'au'
RANGE_TO = r'au'
IN = r'dans'
THIS = r'ce|cette'
NEXT_AFTER = r'prochaine?'              # "mercredi prochain" = next week's Wednesday
ARTICLE = r'la|le'
WEEK = r'semaine'
WEEKEND = r'week[\s-]?end'
FOR = r'pendant|pour|durant'
AND = r'et'
HALF_HOUR = r'une\s+demi[\s-]heure'
ALL_DAY = r'toute\s+la\s+journ[ée]e|journ[ée]e\s+enti[èe]re'
AT = r'à'
TIME_FROM = r'de'
TIME_BETWEEN = r'entre'
TIME_TO = r"à|jusqu['’]à"
HOUR_MARK = r'heures?'                  # 15 heures ("15h" is shared)
NOON = r'midi'
MIDNIGHT = r'minuit'
FILLERS = r'le|à|de|du|pour|pendant|entre'
