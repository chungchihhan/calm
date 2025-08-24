from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict, Iterator, Optional, Tuple

import google.generativeai as genai

from calm.core.utils import parse_date, parse_local_datetime
from calm.infra.calendar_oauth import get_calendar_credentials
from calm.infra.settings import DEFAULT_TZ
from calm.services.calendar_service import (build_calendar_service,
                                            create_event, delete_event,
                                            get_event, list_events,
                                            update_event)

# ---- Tool Declarations (Gemini function-calling) ----
FUNCTION_DECLS = [
    # list
    {
        "name": "list_events_between",
        "description": "List calendar events in a time range (inclusive). Use local ISO 8601 datetimes with timezone offset. Optionally filter by keyword.",
        "parameters": {
            "type": "object",
            "properties": {
            "start_iso": {"type": "string", "description": "ISO8601 datetime, e.g. 2025-08-01T00:00:00+08:00"},
            "end_iso":   {"type": "string", "description": "ISO8601 datetime, e.g. 2025-08-31T23:59:59+08:00"},
            "query":     {"type": "string", "description": "Keyword filter, e.g. '大阪' or 'Osaka'"},
            },
            "required": ["start_iso", "end_iso"]
        }
    },
    # create
    {
        "name": "create_event",
        "description": "Create a calendar event. Use either (start_dt,end_dt) for timed event, OR (start_date,end_date) for all-day. end_date is exclusive for all-day.",
        "parameters": {
            "type": "object",
            "properties": {
                "title":       {"type": "string"},
                "start_dt":    {"type": "string", "description": "ISO8601 datetime with tz (timed event)"},
                "end_dt":      {"type": "string", "description": "ISO8601 datetime with tz (timed event)"},
                "start_date":  {"type": "string", "description": "YYYY-MM-DD (all-day)"},
                "end_date":    {"type": "string", "description": "YYYY-MM-DD (all-day, exclusive)"},
                "description": {"type": "string"},
                "location":    {"type": "string"},
                "timezone":    {"type": "string", "description": "IANA tz name; default is app DEFAULT_TZ"},
            },
            "required": ["title"],
        },
    },
    # delete
    {
        "name": "delete_event",
        "description": "Delete one calendar event by event_id. If the user references a title/time, first call list_events_between to obtain the id.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Google Calendar event id"},
            },
            "required": ["event_id"],
        },
    },
    # update
    {
        "name": "update_event",
        "description": "Update one event by id. For timed updates provide both new_start_dt and new_end_dt (ISO with tz). For all-day provide both new_start_date and new_end_date (YYYY-MM-DD, end exclusive).",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id":       {"type": "string"},
                "new_title":      {"type": "string"},
                "new_start_dt":   {"type": "string"},
                "new_end_dt":     {"type": "string"},
                "new_start_date": {"type": "string"},
                "new_end_date":   {"type": "string"},
                "description":    {"type": "string"},
                "location":       {"type": "string"},
                "timezone":       {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
]


def _ensure_gemini(model: str, api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, tools=[{"function_declarations": FUNCTION_DECLS}])


def _now_local_iso() -> str:
    return dt.datetime.now(tz=DEFAULT_TZ).isoformat(timespec="seconds")

def _parse_iso_dt(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def _exec_toolcall(name: str, args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    creds = get_calendar_credentials()
    service = build_calendar_service(creds)

    if name == "list_events_between":
        start_iso = args["start_iso"]
        end_iso   = args["end_iso"]
        query     = args.get("query")
        items = list_events(service, start_iso, end_iso, query=query)
        return name, {"ok": True, "items": items, "start_iso": start_iso, "end_iso": end_iso, "query": query}

    if name == "create_event":
        title = args["title"]
        timezone = args.get("timezone")
        start_dt = args.get("start_dt")
        end_dt   = args.get("end_dt")
        start_date = args.get("start_date")
        end_date   = args.get("end_date")

        if start_dt and not end_dt:
            # default +1h
            s_dt = _parse_iso_dt(start_dt)
            e_dt = s_dt + dt.timedelta(hours=1)
            created = create_event(service, title, start_dt=s_dt, end_dt=e_dt,
                                   description=args.get("description"), location=args.get("location"),
                                   timezone=timezone)
        elif start_dt and end_dt:
            s_dt = _parse_iso_dt(start_dt)
            e_dt = _parse_iso_dt(end_dt)
            created = create_event(service, title, start_dt=s_dt, end_dt=e_dt,
                                   description=args.get("description"), location=args.get("location"),
                                   timezone=timezone)
        elif start_date and end_date:
            s_date = dt.date.fromisoformat(start_date)
            e_date = dt.date.fromisoformat(end_date)
            created = create_event(service, title, start_date=s_date, end_date=e_date,
                                   description=args.get("description"), location=args.get("location"),
                                   timezone=timezone)
        else:
            raise ValueError("create_event requires (start_dt[,end_dt]) or (start_date,end_date).")

        return name, {"ok": True, "created": created}

    if name == "delete_event":
        event_id = args["event_id"]
        before = get_event(service, event_id)
        delete_event(service, event_id)
        # After is none (deleted)
        return name, {"ok": True, "before": before, "after": None, "event_id": event_id}

    if name == "update_event":
        event_id = args["event_id"]
        before = get_event(service, event_id)

        new_title = args.get("new_title")
        description = args.get("description")
        location = args.get("location")
        tz = args.get("timezone")

        new_start_dt = args.get("new_start_dt")
        new_end_dt   = args.get("new_end_dt")
        new_start_date = args.get("new_start_date")
        new_end_date   = args.get("new_end_date")

        s_dt = e_dt = None
        s_date = e_date = None
        if new_start_dt or new_end_dt:
            if not (new_start_dt and new_end_dt):
                # convenience: if only start_dt provided, default +1h
                if new_start_dt and not new_end_dt:
                    s_dt = _parse_iso_dt(new_start_dt)
                    e_dt = s_dt + dt.timedelta(hours=1)
                else:
                    raise ValueError("Timed update needs both new_start_dt and new_end_dt (or start only to default +1h).")
            else:
                s_dt = _parse_iso_dt(new_start_dt)
                e_dt = _parse_iso_dt(new_end_dt)

        if new_start_date or new_end_date:
            if not (new_start_date and new_end_date):
                raise ValueError("All-day update needs both new_start_date and new_end_date.")
            s_date = dt.date.fromisoformat(new_start_date)
            e_date = dt.date.fromisoformat(new_end_date)

        after = update_event(
            service,
            event_id,
            new_title=new_title,
            new_start_dt=s_dt,
            new_end_dt=e_dt,
            new_start_date=s_date,
            new_end_date=e_date,
            description=description,
            location=location,
            timezone=tz,
        )
        return name, {"ok": True, "event_id": event_id, "before": before, "after": after}

    raise ValueError(f"Unknown tool: {name}")

def _extract_function_calls(resp) -> tuple[Optional[dict], list]:
    """Return (assistant_content, list_of_function_calls) from a response."""
    assistant_content = None
    calls = []
    for cand in getattr(resp, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if not content:
            continue
        if assistant_content is None:
            assistant_content = content
        for part in getattr(content, "parts", []) or []:
            fc = getattr(part, "function_call", None)
            if fc:
                calls.append(fc)
        if calls:
            break  # take first candidate that has calls
    return assistant_content, calls

def agent_once(
    user_text: str,
    *,
    api_key: str,
    model: str = "gemini-1.5-flash",
    stream_final: bool = True,
):
    m = _ensure_gemini(model, api_key)

    sys_preamble = (
        "You are a command-line calendar assistant. "
        "Understand the user's intent in Chinese or English. "
        f"CURRENT_TIME_LOCAL: {_now_local_iso()} "
        "If the user wants to view events, call list_events_between with a correct ISO range. "
        "If the user references a title/place/keyword (e.g.,'會議', 'meeting', '開會', '訪談', '面試'...), include it as the 'query' parameter to list_events_between. "
        "Default time range if the user does not specify is from 30 days before today to 30 days after today (local time). "
        "For vague scopes (e.g. '最近', '近期', 'recent'), convert the time duration to 7 days before and after today. "
        "If the goal is delete/update and the user only gives a title/keyword, first call list_events_between (with 'query') to get ids, "
        "then call delete_event or update_event using the chosen id. "
        "If the request is '把X換成Y', update the title by replacing X with Y and keep the same time window unless a new time is given. "
        "Default event duration is 1 hour if end is not provided for timed adds or updates. "
        "Always resolve relative times like '明天', '下週三', 'tomorrow 2pm' to absolute local times. "
        "If the user only greets or asks a general question, do not call tools—just answer briefly."
    )

    messages = [{"role": "user", "parts": [sys_preamble, "\n\nUser: ", user_text]}]

    # Tool-call loop
    MAX_STEPS = 4
    for _ in range(MAX_STEPS):
        resp = m.generate_content(messages)

        assistant_content, calls = _extract_function_calls(resp)
        if not calls:
            # final answer
            final_text = getattr(resp, "text", "") or "(No text response)"
            if stream_final:
                # stream the FINAL answer for better UX
                stream = m.generate_content(messages, stream=True)
                for ev in stream:
                    chunk = getattr(ev, "text", None)
                    if chunk:
                        yield chunk
                return
            else:
                return final_text

        # Execute ALL function calls in this turn
        responses = []
        for fc in calls:
            args = json.loads(fc.args) if isinstance(fc.args, str) else dict(fc.args)
            tool_name, tool_result = _exec_toolcall(fc.name, args)
            responses.append({
                "function_response": {
                    "name": tool_name,
                    "response": tool_result,
                }
            })

        # Append assistant (function_call turn) and our tool response, then continue the loop
        messages.append(assistant_content)
        messages.append({"role": "tool", "parts": responses})

    # Safety bail-out
    return "(No final answer after tool steps)"