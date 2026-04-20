#!/usr/bin/env python3
"""
Google Calendar service for Philip bot.
Reads token.json (saved by OAuth flow) and provides calendar operations.
"""
from __future__ import annotations

import json
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytz

TOKEN_FILE = Path(__file__).resolve().parent / "token.json"
CREDENTIALS_FILE = Path(__file__).resolve().parent / "credentials.json"
CALENDAR_ID = "primary"
TIMEZONE = "America/New_York"

def _get_service():
    """Build Google Calendar service from saved token."""
    import warnings
    warnings.filterwarnings('ignore')
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        raise FileNotFoundError("token.json не найден. Запусти setup_calendar_auth.py")

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service


def get_events_today() -> list[dict]:
    """Get events for today."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    service = _get_service()
    result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def get_events_week() -> list[dict]:
    """Get events for the next 7 days."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)

    service = _get_service()
    result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def create_event(title: str, date_str: str, time_str: str = "", duration_hours: int = 1) -> dict:
    """
    Create a calendar event.
    date_str: 'YYYY-MM-DD' or 'завтра' / 'сегодня' / 'послезавтра'
    time_str: 'HH:MM' or '' for all-day
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Parse natural language dates
    date_lower = date_str.lower().strip()
    if date_lower in ("сегодня", "today"):
        target_date = now.date()
    elif date_lower in ("завтра", "tomorrow"):
        target_date = (now + timedelta(days=1)).date()
    elif date_lower in ("послезавтра",):
        target_date = (now + timedelta(days=2)).date()
    else:
        # Try YYYY-MM-DD or DD.MM.YYYY or DD/MM/YYYY
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m"):
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                target_date = parsed.replace(year=now.year).date() if fmt == "%d.%m" else parsed.date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Не понял дату: '{date_str}'. Используй формат ГГГГ-ММ-ДД или 'сегодня'/'завтра'")

    service = _get_service()

    if time_str:
        # Timed event
        try:
            hour, minute = map(int, time_str.strip().split(":"))
        except Exception:
            raise ValueError(f"Не понял время: '{time_str}'. Используй формат ЧЧ:ММ")
        start_dt = tz.localize(datetime(target_date.year, target_date.month, target_date.day, hour, minute))
        end_dt = start_dt + timedelta(hours=duration_hours)
        event = {
            "summary": title,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        }
    else:
        # All-day event
        event = {
            "summary": title,
            "start": {"date": target_date.isoformat()},
            "end": {"date": (target_date + timedelta(days=1)).isoformat()},
        }

    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created


def format_events(events: list[dict], tz_name: str = TIMEZONE) -> str:
    """Format list of events for Telegram message."""
    if not events:
        return "Событий нет 🎉"

    tz = pytz.timezone(tz_name)
    lines = []
    for ev in events:
        title = ev.get("summary", "(без названия)")
        start = ev.get("start", {})

        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"])
            if dt.tzinfo is None:
                dt = tz.localize(dt)
            else:
                dt = dt.astimezone(tz)
            time_str = dt.strftime("%H:%M")
            date_str = dt.strftime("%d.%m")
            lines.append(f"🕐 {date_str} {time_str} — {title}")
        elif "date" in start:
            date_str = start["date"]  # YYYY-MM-DD
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
                date_str = d.strftime("%d.%m")
            except Exception:
                pass
            lines.append(f"📅 {date_str} — {title}")
        else:
            lines.append(f"• {title}")

    return "\n".join(lines)
