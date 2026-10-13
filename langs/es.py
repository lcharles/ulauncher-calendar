"""Español."""

# Months only count next to a day number ("14 de mayo"). Abbreviations like "mar" (also
# "sea") or "ago" are left out.
MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
    'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
WEEKDAYS = {'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2, 'jueves': 3, 'viernes': 4,
            'sábado': 5, 'sabado': 5, 'domingo': 6}
NUMBERS = {'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
           'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10}
RELATIVE_DAYS = {
    r'hoy|esta\s+noche': 0,
    r'mañana|manana': 1,
    r'ayer': -1,
    r'pasado\s+(?:mañana|manana)': 2,
}
UNITS = {'day': r'd[ií]as?', 'week': r'semanas?', 'month': r'mes(?:es)?',
         'hour': r'horas?', 'minute': r'minutos?'}

ORDINAL = r'º|ª'
ON = r'el'
OF = r'de'                              # 14 de octubre
YEAR_OF = r'de'                         # 14 de octubre de 2026
DAY_FROM = r'del'
DAY_TO = r'al'
RANGE_TO = r'al|hasta(?:\s+el)?'
IN = r'en|dentro\s+de'
THIS = r'este|esta'
NEXT = r'pr[oó]xim[oa]'                 # el próximo lunes
NEXT_AFTER = r'pr[oó]xim[oa]|que\s+viene'   # el lunes que viene
ARTICLE = r'el|la'
WEEK = r'semana'
WEEKEND = r'fin\s+de\s+semana'
FOR = r'durante'
AND = r'y'
HALF_HOUR = r'media\s+hora'
ALL_DAY = r'todo\s+el\s+d[ií]a'
AT = r'a\s+las?|a\s+la'                 # a las 3, a la 1
TIME_FROM = r'de|desde'
TIME_BETWEEN = r'entre'
TIME_TO = r'a|hasta'
TIME_ARTICLE = r'las?'                  # entre las 9 y las 11
NOON = r'mediod[ií]a'
MIDNIGHT = r'medianoche'
FILLERS = r'el|al|a|las|la|de|del|desde|para|durante|entre'
