from __future__ import annotations

import datetime as dt

import typer

from calm.infra.settings import DEFAULT_TZ


# ---- 顏色工具：整列同色（處理多行） ----
class ANSI:
    RESET = "\033[0m"
    GRAY = "\033[90m"      # 過去
    GREEN = "\033[1;32m"   # 進行中
    WHITE = "\033[97m"     # 未來

def colorize_multiline(text: str, color_code: str) -> str:
    """讓多行文字每一行都帶相同顏色（避免只有第一行有色）。"""
    return "\n".join(f"{color_code}{line}{ANSI.RESET}" for line in (text.splitlines() or [""]))

def color_for_event(start_dt, end_dt) -> str:
    now = dt.datetime.now(tz=DEFAULT_TZ)
    if start_dt <= now <= end_dt:
        return ANSI.GREEN
    if start_dt > now:
        return ANSI.WHITE
    return ANSI.GRAY

def _parse_google_time(s: str) -> tuple[dt.datetime, bool]:
    """
    解析 Google Calendar 的時間字串，回傳 (帶時區 datetime, 是否為全天)
    - dateTime: e.g. 2025-08-14T14:00:00+08:00 或 ...Z
    - date:     e.g. 2025-08-14  (全天，start=該日00:00、end=隔日00:00【排他】)
    """
    if "T" in s:  # dateTime
        s = s.replace("Z", "+00:00")
        t = dt.datetime.fromisoformat(s)
        if t.tzinfo is None:
            t = t.replace(tzinfo=DEFAULT_TZ)
        return t.astimezone(DEFAULT_TZ), False
    # 全天：轉當地 00:00
    d = dt.date.fromisoformat(s)
    return dt.datetime.combine(d, dt.time.min, tzinfo=DEFAULT_TZ), True

def parse_event_times(ev: dict) -> tuple[dt.datetime, dt.datetime, bool]:
    """回傳 (start_dt, end_dt, is_all_day)；都帶時區，避免 naive/aware 錯誤。"""
    start_raw = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
    end_raw   = ev.get("end", {}).get("dateTime")   or ev.get("end", {}).get("date")
    start_dt, start_all = _parse_google_time(start_raw)
    end_dt,   end_all   = _parse_google_time(end_raw)
    return start_dt, end_dt, (start_all or end_all)

def time_span_str(start_dt: dt.datetime, end_dt: dt.datetime, all_day: bool) -> str:
    """把區間轉成人看得懂的字串（含全天/多日全天處理）。"""
    if all_day:
        disp_end = end_dt - dt.timedelta(seconds=1)  # Google 全天的 end 是隔日 00:00（排他）
        if disp_end.date() == start_dt.date():
            return f"{start_dt.strftime('%Y/%m/%d')}" # Single Day All Day
        return f"{start_dt.strftime('%Y/%m/%d')} ~ {disp_end.strftime('%Y/%m/%d')}" # Multi-Day All Day
    return f"{start_dt.strftime('%Y/%m/%d %H:%M')} ~ {end_dt.strftime('%Y/%m/%d %H:%M')}"

def _legend_line() -> str:
    return "  ".join([
        f"{ANSI.GRAY}■{ANSI.RESET} Past",
        f"{ANSI.GREEN}■{ANSI.RESET} In Progress",
        f"{ANSI.WHITE}■{ANSI.RESET} Upcoming",
    ])

def print_events_table(items: list[dict]) -> None:
    if not items:
        typer.echo("No events found.")
        return

    typer.echo(_legend_line())

    for ev in items:
        subject = ev.get("summary") or "No Subject"
        start_dt, end_dt, is_all_day = parse_event_times(ev)
        span = time_span_str(start_dt, end_dt, is_all_day)

        color = color_for_event(start_dt, end_dt)
        subject_colored = colorize_multiline(subject, color)
        span_colored = colorize_multiline(span, color)

        typer.echo(f"{span_colored}：{subject_colored}")


def parse_local_datetime(s: str) -> dt.datetime:
    """Accept 'YYYY-MM-DD HH:MM' or 'YYYY/MM/DD HH:MM' in local tz."""
    s = s.strip()
    fmt = "%Y-%m-%d %H:%M" if "-" in s.split()[0] else "%Y/%m/%d %H:%M"
    return dt.datetime.strptime(s, fmt).replace(tzinfo=DEFAULT_TZ)

def parse_date(s: str) -> dt.date:
    """Accept 'YYYY-MM-DD' or 'YYYY/MM/DD'."""
    s = s.strip()
    if "-" in s:
        return dt.date.fromisoformat(s)
    y, m, d = map(int, s.split("/"))
    return dt.date(y, m, d)