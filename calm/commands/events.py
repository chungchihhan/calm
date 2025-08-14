import datetime as dt
import json

import typer

from calm.core.display import print_events_table
from calm.core.onboarding import ensure_onboard_if_needed
from calm.infra.auth import get_calendar_credentials
from calm.infra.settings import DEFAULT_TZ
from calm.services.calendar_service import (build_calendar_service, day_range,
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
