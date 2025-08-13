from __future__ import annotations

import datetime as dt
import json
import sys
import textwrap
from typing import Optional

import typer
from tabulate import tabulate

from .auth import (get_calendar_credentials,
                   import_oauth_client_from_json_string,
                   import_oauth_client_from_path, reset_tokens)
from .calendar_service import (build_calendar_service, day_range, list_events,
                               week_range)
from .config import DEFAULT_TZ, GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

app = typer.Typer(help="calm: A simple CLI tool to interact with Google Calendar.")

cfg = typer.Typer(help="Configure OAuth")
app.add_typer(cfg, name="configure")

# --- 原本的 _ensure_onboard 改成這樣 ---
def _ensure_onboard(verbose_on_first_auth: bool = False):
    # 若沒 credentials.json，幫忙引導導入（保留你原本的導入流程）
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

    # 只有「這次呼叫前本來沒有 token」且「授權成功生成了 token」時，才印出成功訊息
    had_token_before = GOOGLE_TOKEN_PATH.exists()
    try:
        _ = get_calendar_credentials()  # 可能會開瀏覽器授權
        if verbose_on_first_auth and not had_token_before and GOOGLE_TOKEN_PATH.exists():
            typer.secho("✓ OAuth 授權完成", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ OAuth 授權失敗：{e}", fg=typer.colors.RED)
        raise typer.Exit(1)

@app.callback(invoke_without_command=True)
def _root():
    """
    直接輸入 `calm` → 如果尚未設定，進入引導；已設定則安靜不多話。
    """
    if not GOOGLE_TOKEN_PATH.exists():
        _ensure_onboard(verbose_on_first_auth=True)
    # 已就緒就什麼都不印；維持安靜

@cfg.command("oauth")
def cfg_oauth(
    path: Optional[str] = typer.Option(None, "--path", help="credentials.json 檔案路徑（可省略，改用貼 JSON）"),
    paste: bool = typer.Option(False, "--paste", help="於終端機貼上 JSON（以 END 結束）"),
):
    """重新設定 OAuth：導入 credentials 並立即跑授權"""
    try:
        if paste:
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
        elif path:
            import_oauth_client_from_path(path)
        elif not GOOGLE_CREDENTIALS_PATH.exists():
            typer.secho("未提供 --path / --paste，且本機無現有 credentials.json。", fg=typer.colors.RED)
            raise typer.Exit(1)

        _ = get_calendar_credentials()
        typer.secho("✓ OAuth 設定完成", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ 設定失敗：{e}", fg=typer.colors.RED)
        raise typer.Exit(1)

@cfg.command("reset")
def cfg_reset(all: bool = typer.Option(False, "--all", help="刪除 token 與 credentials（完全重置）")):
    """重置：預設只刪除 token；加 --all 連 credentials 一起刪"""
    if all and GOOGLE_CREDENTIALS_PATH.exists():
        GOOGLE_CREDENTIALS_PATH.unlink()
        typer.secho("✓ 已刪除 credentials.json", fg=typer.colors.GREEN)
    reset_tokens()
    typer.secho("✓ 已刪除 token（下次會重新跑授權）", fg=typer.colors.GREEN)

class ANSI:
    RESET = "\033[0m"
    GREEN = "\033[32m"        # 未來
    YELLOW = "\033[33m"  # 進行中
    GRAY = "\033[90m"  

def colorize_multiline(text: str, color_code: str) -> str:
    """讓多行文字每一行都帶相同顏色（避免只有第一行有色）。"""
    return "\n".join(f"{color_code}{line}{ANSI.RESET}" for line in text.splitlines() or [""])

def color_for_event(start_dt, end_dt) -> str:
    """依事件狀態回傳 ANSI 顏色：進行中=黃、未來=綠、過去=灰。"""
    now = dt.datetime.now(tz=DEFAULT_TZ)
    if start_dt <= now <= end_dt:
        return ANSI.YELLOW
    if start_dt > now:
        return ANSI.GREEN
    return ANSI.GRAY

def _print_events(items, as_json: bool):
    if as_json:
        typer.echo(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        typer.echo("No events found.")
        return

    rows = []
    for ev in items:
        # 1) 取得時間（使用你已有的工具；避免循環就放到函式內部 import）
        from .calendar_service import parse_event_times, time_span_str
        start_dt, end_dt, is_all_day = parse_event_times(ev)
        span = time_span_str(start_dt, end_dt, is_all_day)

        # 2) 你原本對 Subject 的對齊/換行在這裡做（保持你現在的邏輯）
        subject_raw = ev.get("summary") or "No Subject"
        subject_display = subject_raw
        # 例如你有自己的包裝器 _wrap_subject(subject_raw, width=30, max_lines=2)
        # subject_display = _wrap_subject(subject_raw, width=30, max_lines=2)

        # 3) 同列同色（多行每行都加色碼）
        color = color_for_event(start_dt, end_dt)
        subject_colored = colorize_multiline(subject_display, color)
        span_colored = colorize_multiline(span, color)

        rows.append([subject_colored, span_colored])

    out = tabulate(rows, headers=["Subject", "Time"], tablefmt="fancy_grid", disable_numparse=True)
    typer.echo(out)

@app.command()
def today(json_out: bool = typer.Option(False, "--json", help="以 JSON 輸出")):
    """List all events for today"""
    _ensure_onboard()
    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)
    start_iso, end_iso = day_range(dt.datetime.now(tz=DEFAULT_TZ).date())
    items = list_events(cal, start_iso, end_iso)
    _print_events(items, json_out)

@app.command()
def tomorrow(json_out: bool = typer.Option(False, "--json", help="以 JSON 輸出")):
    """List all events for tomorrow"""
    _ensure_onboard()
    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)
    d = dt.datetime.now(tz=DEFAULT_TZ).date() + dt.timedelta(days=1)
    start_iso, end_iso = day_range(d)
    items = list_events(cal, start_iso, end_iso)
    _print_events(items, json_out)

@app.command()
def week(json_out: bool = typer.Option(False, "--json", help="以 JSON 輸出")):
    """List all events for this week"""
    _ensure_onboard()
    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)
    start_iso, end_iso = week_range(dt.datetime.now(tz=DEFAULT_TZ).date())
    items = list_events(cal, start_iso, end_iso)
    _print_events(items, json_out)

@app.command("date")
def date_cmd(
    date: str = typer.Argument(..., help="日期格式 YYYY/MM/DD 或 YYYY-MM-DD"),
    json_out: bool = typer.Option(False, "--json", help="以 JSON 輸出"),
):
    """List all events for a specific date"""
    _ensure_onboard()
    # 解析日期
    try:
        if "/" in date:
            y, m, d = map(int, date.split("/"))
            target = dt.date(y, m, d)
        else:
            target = dt.date.fromisoformat(date)  # YYYY-MM-DD
    except Exception:
        typer.secho("日期格式錯誤，請用 YYYY/MM/DD 或 YYYY-MM-DD", fg=typer.colors.RED)
        raise typer.Exit(1)

    creds = get_calendar_credentials()
    cal = build_calendar_service(creds)
    start_iso, end_iso = day_range(target)
    items = list_events(cal, start_iso, end_iso)
    _print_events(items, json_out)