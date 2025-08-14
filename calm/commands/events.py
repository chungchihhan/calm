import datetime as dt
import json
from typing import Optional

import typer

from calm.core.onboarding import ensure_onboard_if_needed
from calm.core.utils import (parse_date, parse_local_datetime,
                             print_events_table)
from calm.infra.auth import get_calendar_credentials
from calm.infra.settings import DEFAULT_TZ
from calm.services.calendar_service import (build_calendar_service,
                                            create_event, day_range,
                                            list_events, week_range)

events_app = typer.Typer(help="Calendar queries")

def output_events_in_range(start_iso: str, end_iso: str, json_out: bool):
    """Helper function to fetch and print events in a given range."""
    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)
    items = list_events(cal, start_iso, end_iso)
    if json_out:
        typer.echo(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print_events_table(items)

@events_app.command(name="today", help="List all events for today")
@events_app.command(name="t", hidden=True)  # alias
def today(json_out: bool = typer.Option(False, "--json", help="use JSON output")):
    """List all events for today"""
    ensure_onboard_if_needed()
    start_iso, end_iso = day_range(dt.datetime.now(tz=DEFAULT_TZ).date())
    output_events_in_range(start_iso, end_iso, json_out)

@events_app.command(name="tomorrow", help="List all events for tomorrow")
@events_app.command(name="tmr", hidden=True)  # alias
def tomorrow(json_out: bool = typer.Option(False, "--json", help="use JSON output")):
    """List all events for tomorrow"""
    ensure_onboard_if_needed()
    d = dt.datetime.now(tz=DEFAULT_TZ).date() + dt.timedelta(days=1)
    start_iso, end_iso = day_range(d)
    output_events_in_range(start_iso, end_iso, json_out)

@events_app.command(name="week", help="List all events for this week")
@events_app.command(name="w", hidden=True)  # alias
def week(json_out: bool = typer.Option(False, "--json", help="use JSON output")):
    """List all events for this week"""
    ensure_onboard_if_needed()
    start_iso, end_iso = week_range(dt.datetime.now(tz=DEFAULT_TZ).date())
    output_events_in_range(start_iso, end_iso, json_out)

@events_app.command("date", help="List all events for a specific date")
@events_app.command(name="d", hidden=True)  # alias
def date_cmd(
    date: str = typer.Argument(..., help="Date format: YYYY/MM/DD or YYYY-MM-DD"),
    json_out: bool = typer.Option(False, "--json", help="use JSON output"),
):
    """List all events for a specific date"""
    ensure_onboard_if_needed()
    try:
        if "/" in date:
            y, m, d = map(int, date.split("/"))
            target = dt.date(y, m, d)
        else:
            target = dt.date.fromisoformat(date)
    except Exception as e:
        typer.secho("Invalid date format. Please use YYYY/MM/DD or YYYY-MM-DD", fg=typer.colors.RED)
        raise typer.Exit(1) from e

    start_iso, end_iso = day_range(target)
    output_events_in_range(start_iso, end_iso, json_out)

@events_app.command(name="add", help="Create a calendar event")
def add_event(
    title: str = typer.Argument(..., help="Event title"),
    start: str = typer.Argument(..., help="Start time/date. 'YYYY-MM-DD HH:MM' or 'YYYY/MM/DD HH:MM' for timed; 'YYYY-MM-DD' or 'YYYY/MM/DD' for all-day."),
    end: Optional[str] = typer.Argument(None, help="End time/date. For timed: 'YYYY-MM-DD HH:MM' or 'YYYY/MM/DD HH:MM'. For all-day: omit and use --days."),
    desc: Optional[str] = typer.Option(None, "--desc", help="Description"),
    loc: Optional[str] = typer.Option(None, "--loc", help="Location"),
    tz: Optional[str] = typer.Option(None, "--tz", help="Timezone (defaults to app DEFAULT_TZ)"),
    days: int = typer.Option(1, "--days", help="All-day duration in days (end date is exclusive)"),
    json_out: bool = typer.Option(False, "--json", help="Print created event JSON"),
):
    """
    Examples:
      calm add "Kickoff" "2025-08-29 14:00" "2025-08-29 15:00" --loc "Room A"
      calm add "Holiday" "2025/08/29" --days 3
    """
    ensure_onboard_if_needed()
    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)

    try:
        if ":" in start:
            # Timed event
            start_dt = parse_local_datetime(start)
            if not end:
                typer.secho("End datetime required for timed events.", fg=typer.colors.RED)
                raise typer.Exit(1)
            end_dt = parse_local_datetime(end)
            created = create_event(
                cal,
                title,
                start_dt=start_dt,
                end_dt=end_dt,
                description=desc,
                location=loc,
                timezone=tz,
            )
        else:
            # All-day event
            start_date = parse_date(start)
            if end and ":" in end:
                typer.secho("All-day event end should be a date or omitted (use --days).", fg=typer.colors.RED)
                raise typer.Exit(1)
            if end:
                end_date = parse_date(end)  # end_date is exclusive by Google Calendar
            else:
                end_date = start_date + dt.timedelta(days=days)
            created = create_event(
                cal,
                title,
                start_date=start_date,
                end_date=end_date,
                description=desc,
                location=loc,
                timezone=tz,
            )
    except Exception as e:
        typer.secho(f"Create failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Output
    if json_out:
        typer.echo(json.dumps(created, ensure_ascii=False, indent=2))
    else:
        print_events_table([created])