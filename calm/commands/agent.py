from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from calm.infra.gemini_auth import load_api_key
from calm.services.gemini_agent_service import agent_once

agent_app = typer.Typer(help="Natural-language agent for Calendar")

@agent_app.command("agent", help="Understand natural language and read/add events via tools")
def agent(
    text: str = typer.Argument(..., help="Your instruction, e.g. '明天下午2點加會議' or '這週的行程'"),
    model: str = typer.Option("gemini-2.5-flash-lite", "--model", help="Gemini model to use, e.g. gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="GEMINI_API_KEY or ~/.config/calm/gemini.key if omitted"),
    json_out: bool = typer.Option(False, "--json", help="Return final text in JSON (disables streaming)"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream final answer (default on)"),
):
    key = load_api_key(api_key)
    if not key:
        typer.secho("Missing Gemini API key. Use --api-key, GEMINI_API_KEY, or ~/.config/calm/gemini.key", fg=typer.colors.RED)
        raise typer.Exit(1)

    # JSON mode -> no streaming
    if json_out:
        stream = False

    try:
        if stream:
            for chunk in agent_once(text, api_key=key, model=model, stream_final=True):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            sys.stdout.write("\n")
            return

        result = agent_once(text, api_key=key, model=model, stream_final=False)
    except KeyboardInterrupt:
        typer.secho("\n(Interrupted)", fg=typer.colors.BRIGHT_BLACK)
        raise typer.Exit(130)
    except Exception as e:
        typer.secho(f"Agent failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps({"answer": result}, ensure_ascii=False, indent=2))
    else:
        typer.echo(result or "(No text response)")