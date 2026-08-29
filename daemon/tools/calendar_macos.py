"""macOS-Kalender über Calendar.app / icalBuddy."""

from __future__ import annotations

import subprocess
from datetime import datetime


def read_schedule(date_from: str, date_to: str) -> str:
    start = _parse_day(date_from)
    end = _parse_day(date_to)
    if shutil_which("icalBuddy"):
        try:
            result = subprocess.run(
                [
                    "icalBuddy",
                    "-n",
                    "-nc",
                    "-b",
                    "• ",
                    f"eventsFrom:{start.strftime('%Y-%m-%d')}",
                    f"to:{end.strftime('%Y-%m-%d')}",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    return _osascript_calendar(start, end)


def shutil_which(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _parse_day(value: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except ValueError:
            continue
    return datetime.now()


def _osascript_calendar(start: datetime, end: datetime) -> str:
    script = f"""
    set startDate to current date
    set year of startDate to {start.year}
    set month of startDate to {start.month}
    set day of startDate to {start.day}
    set time of startDate to 0
    set endDate to current date
    set year of endDate to {end.year}
    set month of endDate to {end.month}
    set day of endDate to {end.day}
    set time of endDate to 86399
    set output to {{}}
    tell application "Calendar"
        repeat with c in calendars
            set evs to (every event of c whose start date ≥ startDate and start date ≤ endDate)
            repeat with e in evs
                set end of output to ((start date of e as string) & " — " & summary of e)
            end repeat
        end repeat
    end tell
    return output as text
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return f"Kalender nicht lesbar: {exc}"
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        return f"Kalender nicht lesbar. {err or 'Calendar.app benötigt Zugriff.'}"
    text = result.stdout.strip()
    if not text:
        return f"Keine Termine von {start.date().isoformat()} bis {end.date().isoformat()}."
    return text
