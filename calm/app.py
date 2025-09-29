from __future__ import annotations

import typer

from calm.commands.agent import agent_app
from calm.commands.chat import chat_app
from calm.commands.configure import configure_app
from calm.commands.events import events_app
from calm.core.onboarding import ensure_onboard_if_needed

app = typer.Typer(help="calm: A simple CLI tool to interact with Google Calendar.")
app.add_typer(configure_app, name="configure")
app.add_typer(events_app, name="") 
app.add_typer(chat_app, name="")  
app.add_typer(agent_app, name="")

@app.callback(invoke_without_command=True)
def _root():
    ensure_onboard_if_needed(first_time_verbose=True, offer_gemini_key=True)