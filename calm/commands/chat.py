from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from calm.infra.gemini_auth import load_api_key
from calm.services.gemini_service import one_time_chat

chat_app = typer.Typer(help="One-shot Gemini chat")

@chat_app.command("chat", help="Ask Gemini a question once and get an answer")
def chat(
    question: str = typer.Argument(..., help="Your question for Gemini"),
    model: str = typer.Option("gemini-1.5-flash", "--model", help="e.g. gemini-1.5-flash, gemini-1.5-pro"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Fallback: $GEMINI_API_KEY or ~/.config/calm/gemini.key"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON with model and answer"),
    stream: bool = typer.Option(
        True, "--stream/--no-stream",
        help="Stream output token-by-token (default: stream enabled)",
        show_default=True,
    ),
):
    """Ask Gemini a question and get an answer."""
    key = load_api_key(api_key)
    if not key:
        typer.secho(
            "Gemini API key not found. Provide via --api-key, GEMINI_API_KEY, or ~/.config/calm/gemini.key",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # If JSON requested, force non-stream (stream + JSON don’t mix well)
    if json_out:
        stream = False

    try:
        if stream:
            for chunk in one_time_chat(question, api_key=key, model=model, stream=True):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            sys.stdout.write("\n")
            return

        # non-streaming path
        text = one_time_chat(question, api_key=key, model=model, stream=False)

    except KeyboardInterrupt as exc:
        typer.secho("\n(Interrupted)", fg=typer.colors.BRIGHT_BLACK)
        raise typer.Exit(130) from exc
    except Exception as e:
        typer.secho(f"Gemini request failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps({"model": model, "answer": text}, ensure_ascii=False, indent=2))
    else:
        typer.echo(text)