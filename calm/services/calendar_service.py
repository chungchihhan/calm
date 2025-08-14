from __future__ import annotations

import datetime as dt
from typing import Dict, List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from calm.infra.settings import DEFAULT_TZ


def build_calendar_service(creds: Credentials):
    """Build a Google Calendar API resource object."""
    return build("calendar", "v3", credentials=creds)

def _iso(dtobj: dt.datetime) -> str:
    # Convert to ISO8601 string with timezone info
    return dtobj.astimezone(DEFAULT_TZ).isoformat(timespec="seconds")

def day_range(target_date: dt.date) -> tuple[str, str]:
    """Return ISO8601 strings for the start and end of a day."""
    start = dt.datetime.combine(target_date, dt.time.min, tzinfo=DEFAULT_TZ)
    end = dt.datetime.combine(target_date, dt.time.max, tzinfo=DEFAULT_TZ)
    return _iso(start), _iso(end)

def week_range(anchor_date: dt.date) -> tuple[str, str]:
    """Return ISO8601 strings for the start and end of the week containing anchor_date."""
    # Set Monday as the start of the week
    weekday = anchor_date.weekday()  # Monday=0
    monday = anchor_date - dt.timedelta(days=weekday)
    sunday = monday + dt.timedelta(days=6)
    start = dt.datetime.combine(monday, dt.time.min, tzinfo=DEFAULT_TZ)
    end = dt.datetime.combine(sunday, dt.time.max, tzinfo=DEFAULT_TZ)
    return _iso(start), _iso(end)

def list_events(service, start_iso: str, end_iso: str) -> List[Dict]:
    """List events in the specified time range."""
    res = service.events().list(
        calendarId="primary",
        timeMin=start_iso,
        timeMax=end_iso,
        singleEvents=True,
        orderBy="startTime",
        timeZone=str(DEFAULT_TZ),
    ).execute()
    return res.get("items", [])
