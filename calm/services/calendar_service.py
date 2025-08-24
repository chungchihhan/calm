from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

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

def get_event(service, event_id: str) -> Dict:
    """Get a specific event by its ID."""
    return service.events().get(calendarId="primary", eventId=event_id).execute()

def delete_event(service, event_id: str) -> None:
    """Delete a specific event by its ID."""
    service.events().delete(calendarId="primary", eventId=event_id).execute()

def update_event(
    service,
    event_id: str,
    *,
    new_title: Optional[str] = None,
    new_start_dt: Optional[dt.datetime] = None,
    new_end_dt: Optional[dt.datetime] = None,
    new_start_date: Optional[dt.date] = None,
    new_end_date: Optional[dt.date] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: Optional[str] = None,
) -> Dict:
    """Patch the event with provided fields, return updated resource."""
    body: Dict = {}

    if new_title is not None:
        body.setdefault("summary", new_title)

    if description is not None:
        body.setdefault("description", description)

    if location is not None:
        body.setdefault("location", location)

    # Timed
    if new_start_dt or new_end_dt:
        if not (new_start_dt and new_end_dt):
            raise ValueError("Timed update requires both new_start_dt and new_end_dt.")
        start = {"dateTime": new_start_dt.astimezone(DEFAULT_TZ).isoformat()}
        end = {"dateTime": new_end_dt.astimezone(DEFAULT_TZ).isoformat()}
        if timezone:
            start["timeZone"] = timezone
            end["timeZone"] = timezone
        body["start"] = start
        body["end"] = end

    # All-day
    if new_start_date or new_end_date:
        if not (new_start_date and new_end_date):
            raise ValueError("All-day update requires both new_start_date and new_end_date.")
        body["start"] = {"date": new_start_date.isoformat()}
        body["end"] = {"date": new_end_date.isoformat()}

    if not body:
        raise ValueError("No update fields provided.")

    return service.events().patch(calendarId="primary", eventId=event_id, body=body).execute()

def list_events(service, start_iso: str, end_iso: str, query: str | None = None) -> list[dict]:
    """List events in the given ISO8601 time range, optionally filtered by a text query."""
    kwargs = dict(
        calendarId="primary",
        timeMin=start_iso,
        timeMax=end_iso,
        singleEvents=True,
        orderBy="startTime",
        timeZone=str(DEFAULT_TZ),
    )
    if query:
        kwargs["q"] = query  # <-- text search (title, description, etc.)
    res = service.events().list(**kwargs).execute()
    return res.get("items", [])

def create_event(
    service,
    title: str,
    *,
    start_dt: Optional[dt.datetime] = None,
    end_dt: Optional[dt.datetime] = None,
    start_date: Optional[dt.date] = None,
    end_date: Optional[dt.date] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: Optional[str] = None,
) -> Dict:
    """
    Create an event. Provide either (start_dt, end_dt) for timed events
    OR (start_date, end_date) for all-day events (end_date is exclusive).
    """
    tz = timezone or str(DEFAULT_TZ)

    if start_dt and end_dt:
        body = {
            "summary": title,
            "start": {"dateTime": start_dt.astimezone(DEFAULT_TZ).isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.astimezone(DEFAULT_TZ).isoformat(), "timeZone": tz},
        }
    elif start_date and end_date:
        # All-day events use date (end is exclusive)
        body = {
            "summary": title,
            "start": {"date": start_date.isoformat(), "timeZone": tz},
            "end": {"date": end_date.isoformat(), "timeZone": tz},
        }
    else:
        raise ValueError("Invalid arguments: provide timed (start_dt,end_dt) OR all-day (start_date,end_date).")

    if description:
        body["description"] = description
    if location:
        body["location"] = location

    return service.events().insert(calendarId="primary", body=body).execute()