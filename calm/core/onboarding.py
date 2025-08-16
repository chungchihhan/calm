# calm/core/onboarding.py
from __future__ import annotations

import sys

import typer

from calm.infra.calendar_oauth import (get_calendar_credentials,
                                       import_oauth_client_from_json_string,
                                       import_oauth_client_from_path)
from calm.infra.gemini_auth import load_api_key, save_api_key
from calm.infra.settings import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH


def _ensure_calendar_oauth(first_time_verbose: bool = False) -> None:
    """Current calendar OAuth onboarding (unchanged behavior)."""
    if not GOOGLE_CREDENTIALS_PATH.exists():
        typer.secho("需要導入 Google OAuth client (Desktop) 的 credentials.json。", fg=typer.colors.CYAN)
        choice = typer.prompt("提供方式：1) 貼 JSON  2) 指定檔案路徑", default="2")
        try:
            if choice.strip() == "1":
                typer.echo("請貼上完整 JSON，結束請輸入單獨一行 END：")
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
            else:
                path = typer.prompt("credentials.json 檔案路徑")
                import_oauth_client_from_path(path)
            typer.secho(f"✓ OAuth client 已保存到 {GOOGLE_CREDENTIALS_PATH}", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"❌ 導入失敗：{e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    had_token_before = GOOGLE_TOKEN_PATH.exists()
    try:
        _ = get_calendar_credentials()  # may open browser
        if first_time_verbose and not had_token_before and GOOGLE_TOKEN_PATH.exists():
            typer.secho("✓ OAuth 授權完成", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ OAuth 授權失敗：{e}", fg=typer.colors.RED)
        raise typer.Exit(1)

def _ensure_gemini_key_interactive() -> None:
    """
    First-run friendly: if no Gemini API key is configured anywhere,
    *offer* to save one. Skippable so Calendar-only users aren't blocked.
    """
    if load_api_key() is not None:
        return  # already present (flag/env/file)

    typer.secho("（可選）設定 Gemini API Key 以啟用 calm ask", fg=typer.colors.CYAN)
    if not typer.confirm("現在要設定嗎？", default=False):
        return

    while True:
        key = typer.prompt("請輸入 Gemini API Key（輸入空白可取消）", hide_input=True)
        if not key.strip():
            typer.echo("已跳過設定 Gemini API Key。")
            return
        try:
            save_api_key(key)
            typer.secho("✓ 已保存 Gemini API Key（~/.config/calm/gemini.key）", fg=typer.colors.GREEN)
            return
        except Exception as e: # pylint: disable=broad-except
            typer.secho(f"❌ 儲存失敗：{e}", fg=typer.colors.RED)
            if not typer.confirm("要再試一次嗎？", default=True):
                return

def ensure_onboard_if_needed(first_time_verbose: bool = False, offer_gemini_key: bool = True) -> None:
    """
    Main entry: ensure Calendar OAuth (required) and *optionally*
    offer to setup Gemini key once.
    """
    _ensure_calendar_oauth(first_time_verbose=first_time_verbose)
    if offer_gemini_key:
        _ensure_gemini_key_interactive()