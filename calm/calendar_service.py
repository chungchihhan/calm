from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

import typer
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import DEFAULT_TZ


def build_calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds)

def _iso(dtobj: dt.datetime) -> str:
    # 轉成 ISO8601，包含時區
    return dtobj.astimezone(DEFAULT_TZ).isoformat(timespec="seconds")

def day_range(target_date: dt.date) -> tuple[str, str]:
    start = dt.datetime.combine(target_date, dt.time.min, tzinfo=DEFAULT_TZ)
    end = dt.datetime.combine(target_date, dt.time.max, tzinfo=DEFAULT_TZ)
    return _iso(start), _iso(end)

def week_range(anchor_date: dt.date) -> tuple[str, str]:
    # 以週一為一週開始
    weekday = anchor_date.weekday()  # Monday=0
    monday = anchor_date - dt.timedelta(days=weekday)
    sunday = monday + dt.timedelta(days=6)
    start = dt.datetime.combine(monday, dt.time.min, tzinfo=DEFAULT_TZ)
    end = dt.datetime.combine(sunday, dt.time.max, tzinfo=DEFAULT_TZ)
    return _iso(start), _iso(end)

def list_events(service, start_iso: str, end_iso: str) -> List[Dict]:
    res = service.events().list(
        calendarId="primary",
        timeMin=start_iso,
        timeMax=end_iso,
        singleEvents=True,
        orderBy="startTime",
        timeZone=str(DEFAULT_TZ),
    ).execute()
    return res.get("items", [])

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
            return f"{start_dt.strftime('%Y/%m/%d')} (All Day)"
        return f"{start_dt.strftime('%Y/%m/%d')} ~ {disp_end.strftime('%Y/%m/%d')} (Multi-Day All Day)"
    return f"{start_dt.strftime('%Y/%m/%d %H:%M')} ~ {end_dt.strftime('%Y/%m/%d %H:%M')}"