import sys

import typer

from calm.infra.auth import (get_calendar_credentials,
                             import_oauth_client_from_json_string,
                             import_oauth_client_from_path)
from calm.infra.settings import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH


def ensure_onboard_if_needed(first_time_verbose: bool = False):
    """未設定就引導；第一次真的完成 OAuth 才顯示提示。"""
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
        _ = get_calendar_credentials()  # 可能會開瀏覽器授權
        if first_time_verbose and not had_token_before and GOOGLE_TOKEN_PATH.exists():
            typer.secho("✓ OAuth 授權完成", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ OAuth 授權失敗：{e}", fg=typer.colors.RED)
        raise typer.Exit(1)