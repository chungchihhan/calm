from __future__ import annotations

import json
from typing import Optional

import typer

from calm.infra.gemini_auth import load_api_key
from calm.infra.settings import CONFIG_DIR  # only to mention path in error
from calm.services.gemini_service import ask_once

chat_app = typer.Typer(help="One-shot Gemini chat")

@chat_app.command("chat", help='One-time chat: ask Gemini a question and get an answer')
def chat(
    question: str = typer.Argument(..., help="Your question for Gemini"),
    model: str = typer.Option("gemini-1.5-flash", "--model", help="Gemini model (e.g., gemini-1.5-flash, gemini-1.5-pro)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Gemini API key (fallback: $GEMINI_API_KEY or ~/.config/calm/gemini.key)"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON with model and answer"),
):
    key = load_api_key(api_key)
    if not key:
        typer.secho(
            "Gemini API key not found. Provide one via:\n"
            "  1) --api-key 'YOUR_KEY'\n"
            "  2) env GEMINI_API_KEY\n"
            f"  3) {CONFIG_DIR}/gemini.key (first line)\n",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        text = ask_once(question, api_key=key, model=model)
    except Exception as e:
        typer.secho(f"Gemini request failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if json_out:
        typer.echo(json.dumps({"model": model, "answer": text}, ensure_ascii=False, indent=2))
    else:
        typer.echo(text)