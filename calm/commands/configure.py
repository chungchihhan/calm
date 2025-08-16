import sys
from typing import Optional

import typer

from calm.infra.calendar_oauth import (get_calendar_credentials,
                                       import_oauth_client_from_json_string,
                                       import_oauth_client_from_path,
                                       reset_tokens)
from calm.infra.settings import GOOGLE_CREDENTIALS_PATH

configure_app = typer.Typer(help="Configure OAuth")

@configure_app.command("oauth")
def cfg_oauth(
    path: Optional[str] = typer.Option(None, "--path", help="Path to credentials.json (optional, can paste JSON instead)"),
    paste: bool = typer.Option(False, "--paste", help="Paste JSON in terminal (end with 'END')"),
):
    """Import OAuth client and run authorization immediately"""
    try:
        if paste:
            typer.echo("Please paste the complete JSON. End with a line containing only 'END':")
            lines = []
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                if line.strip() == "END":
                    break
                lines.append(line)
            raw = "".join(lines)
            import_oauth_client_from_json_string(raw)
        elif path:
            import_oauth_client_from_path(path)
        elif not GOOGLE_CREDENTIALS_PATH.exists():
            typer.secho("No --path / --paste provided, and no existing credentials.json found.", fg=typer.colors.RED)
            raise typer.Exit(1)

        _ = get_calendar_credentials()
        typer.secho("✓ OAuth configuration completed", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

@configure_app.command("reset")
def cfg_reset(delete_all: bool = typer.Option(False, "--all", help="Delete both token and credentials (full reset)")):
    """Reset: by default deletes only the token; use --all to delete both token and credentials."""
    if delete_all and GOOGLE_CREDENTIALS_PATH.exists():
        GOOGLE_CREDENTIALS_PATH.unlink()
        typer.secho("✓ credentials.json deleted", fg=typer.colors.GREEN)
    reset_tokens()
    typer.secho("✓ token deleted (will reauthorize next time)", fg=typer.colors.GREEN)

# （可選）提供根層別名：calm reset-token
@configure_app.command("alias-reset-token", hidden=True)
def _alias_reset_token():
    reset_tokens()
    typer.secho("✓ Token reset. Run a command to reauthorize.", fg=typer.colors.GREEN)