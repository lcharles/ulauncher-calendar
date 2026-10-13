# Calendar for Ulauncher

List upcoming events across all your calendars and create new ones by typing them in plain
English or French, e.g. `cal lunch with Bob tomorrow 12:30`.

Calendars come from Evolution Data Server: GNOME Calendar's local calendars, and Google or
CalDAV accounts added in *Settings → Online Accounts*.

## Requirements

- Ulauncher 5 (extension API 2)
- Evolution Data Server and its GObject bindings. On Debian/Ubuntu:

  ```
  sudo apt install evolution-data-server gir1.2-edataserver-1.2 gir1.2-ecal-2.0 gir1.2-ical-3.0
  ```

- Optional: GNOME Calendar, to open events (otherwise Enter copies them), and `python3-dateparser`,
  for dates in other languages after `@`.

## Usage

| Type | To |
|---|---|
| `cal` | upcoming events (the next 7 days) |
| `cal tomorrow`, `cal fri`, `cal next week`, `cal weekend`, `cal 14/10-18/10` | events then |
| `cal lunch with Bob tomorrow 12:30` | add an event, choosing the calendar from the results (last used first); what's already planned that day is listed below |
| `cal review 3pm :: bring slides` | add with a description |
| `cal standup mon 9-9:15am #work` | only calendars matching “work” |
| `cal "Friday release" party fri 6pm for 3h` | quotes keep words in the title |
| `cal #` | list calendars, including excluded ones (Alt+Enter copies a name) |

Enter on an event opens it in GNOME Calendar, and Alt+Enter copies it.

What the date parser understands, with examples:

- **Dates:** `today`, `tomorrow`, `fri`, `next friday` (the Friday of next week), `next week`,
  `weekend`, `in 3 days`, `14/10`, `14 oct`, `2026-10-14`, `14-18 oct`
- **Times:** `3pm`, `15:00`, `15h30`, `noon`, `at 3` (1 to 7 without am/pm means afternoon),
  `in 2 hours`, ranges like `9-10am` and `from 9 to 11`, durations like `for 1h30`, `all day`
- **French:** `demain`, `vendredi prochain`, `semaine prochaine`, `dans 3 jours`, `le 1er novembre`,
  `du 20 au 23 octobre`, `à 14h`, `midi`, `de 9h à 11h`, `pendant 1h30`, `toute la journée`
- **Anything else** can go after `@`, e.g. `review @ morgen 14:00`. That part is read by dateparser
  if it is installed.

A date without a year means its next occurrence. New events use your system time zone.

## Preferences

- **Calendar**: the keyword (`cal`).
- **Excluded calendars**: comma-separated names of calendars to ignore (`cal #` shows the names).
- **Days ahead**: how far `cal` alone looks (7 days).
- **Default duration (minutes)**: the length of events given only a start time (60).
- **Date order**: how to read `04/10`: day first (DMY) or month first (MDY).

## Troubleshooting

- **A calendar is missing:** check that GNOME Calendar shows it, and that it isn't excluded in
  the preferences. `/usr/bin/python3 calendars.py`, run from the extension's folder, lists what
  the extension sees.
- **Events changed on your phone or the web don't show yet:** Evolution Data Server syncs online
  calendars on its own, about every 30 minutes. GNOME Calendar's *Synchronize Calendars* syncs now.
- After installing or updating the extension, restart Ulauncher.
