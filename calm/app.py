from __future__ import annotations
import typer

from .commands.configure import configure_app
from .commands.events import events_app

app = typer.Typer(help="calm: A simple CLI tool to interact with Google Calendar.")
app.add_typer(configure_app, name="configure")
app.add_typer(events_app, name="") 

from .core.onboarding import ensure_onboard_if_needed
@app.callback(invoke_without_command=True)
def _root():
    ensure_onboard_if_needed(first_time_verbose=True)