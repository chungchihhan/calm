from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict, Iterator, Optional, Tuple

import google.generativeai as genai

from calm.core.utils import parse_date, parse_local_datetime
from calm.infra.calendar_oauth import get_calendar_credentials
from calm.infra.settings import DEFAULT_TZ
from calm.services.calendar_service import (build_calendar_service,
                                            create_event, list_events)

# ---- Tool Declarations (Gemini function-calling) ----
FUNCTION_DECLS = [
    {
        "name": "list_events_between",
        "description": "List calendar events in a time range (inclusive). Use local ISO 8601 datetimes with timezone offset.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_iso": {"type": "string", "description": "ISO8601 datetime, e.g. 2025-08-14T00:00:00+08:00"},
                "end_iso":   {"type": "string", "description": "ISO8601 datetime, e.g. 2025-08-14T23:59:59+08:00"},
            },
            "required": ["start_iso", "end_iso"],
        },
    },
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
]


def _ensure_gemini(model: str, api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, tools=[{"function_declarations": FUNCTION_DECLS}])


def _now_local_iso() -> str:
    return dt.datetime.now(tz=DEFAULT_TZ).isoformat(timespec="seconds")


def _exec_toolcall(name: str, args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Execute the requested tool and return (tool_name, tool_result_dict).
    The result dict should be JSON-serializable; we feed it back to Gemini.
    """
    creds = get_calendar_credentials()
    service = build_calendar_service(creds)

    if name == "list_events_between":
        start_iso = args["start_iso"]
        end_iso = args["end_iso"]
        items = list_events(service, start_iso, end_iso)
        return name, {"ok": True, "items": items, "start_iso": start_iso, "end_iso": end_iso}

    if name == "create_event":
        title = args["title"]
        timezone = args.get("timezone")

        # Prefer timed event if start_dt/end_dt provided
        start_dt = args.get("start_dt")
        end_dt = args.get("end_dt")
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        created = None

        if start_dt and end_dt:
            # assume already ISO8601 with tz; parse to datetime just to be safe if you wish
            # (Calendar service accepts dt objects; you already have helpers)
            s_dt = dt.datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            e_dt = dt.datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
            created = create_event(
                service,
                title,
                start_dt=s_dt,
                end_dt=e_dt,
                description=args.get("description"),
                location=args.get("location"),
                timezone=timezone,
            )
        if start_dt and not end_dt:
            # Default: 1 hour event
            s_dt = dt.datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
            e_dt = s_dt + dt.timedelta(hours=1)
            created = create_event(
                service,
                title,
                start_dt=s_dt,
                end_dt=e_dt,
                description=args.get("description"),
                location=args.get("location"),
                timezone=timezone,
            )
        elif start_date and end_date:
            s_date = dt.date.fromisoformat(start_date)
            e_date = dt.date.fromisoformat(end_date)
            created = create_event(
                service,
                title,
                start_date=s_date,
                end_date=e_date,
                description=args.get("description"),
                location=args.get("location"),
                timezone=timezone,
            )
        else:
            # As a convenience: if user said a natural phrase we could compute here,
            # but we keep all reasoning on the model side.
            raise ValueError("create_event requires (start_dt,end_dt) or (start_date,end_date).")

        return name, {"ok": True, "created": created}

    raise ValueError(f"Unknown tool: {name}")


def agent_once(
    user_text: str,
    *,
    api_key: str,
    model: str = "gemini-1.5-flash",
    stream_final: bool = True,
) -> Optional[str]:
    """
    Single-turn agent:
      1) Send instruction + current time + user's text to Gemini with tools.
      2) If Gemini calls a tool -> execute, send tool result back, get final answer.
      3) Return final text (if stream_final=False) or stream to stdout (if stream_final=True via yielded chunks).
    Returns a string for non-stream, or None after streaming directly.
    """
    m = _ensure_gemini(model, api_key)

    sys_preamble = (
        "You are a command-line calendar assistant. "
        "Understand the user's intent in Chinese or English. "
        "CURRENT_TIME_LOCAL: " + _now_local_iso() + " "
        "If the user wants to view events, call list_events_between with a correct ISO range. "
        "If the user wants to add an event, call create_event with precise ISO datetimes or all-day dates. "
        "Default event duration is 1 hour if end is not provided and it's a timed add request. "
        "Always resolve relative times like '明天', '下週三', 'tomorrow 2pm' to absolute local times. "
        "If the user only greets or asks a general question, do not call tools—just answer briefly."
    )

    # Step 1: Ask Gemini; allow it to call functions
    first = m.generate_content(
        [{"role": "user", "parts": [sys_preamble, "\n\nUser: ", user_text]}]
    )

    # Detect tool call
    assistant_content = None
    calls = []
    for cand in getattr(first, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if not content:
            continue
        # remember the assistant content with function_call parts
        if assistant_content is None:
            assistant_content = content
        for part in getattr(content, "parts", []) or []:
            fc = getattr(part, "function_call", None)
            if fc:
                calls.append(fc)
        if calls:
            break  # take first candidate’s calls only

    if not calls:
        # No tool call: just answer. Stream or return.
        if stream_final:
            # stream plain text (second request for streaming simplicity)
            stream = m.generate_content(user_text, stream=True)
            for ev in stream:
                chunk = getattr(ev, "text", None)
                if chunk:
                    yield chunk
            return
        else:
            return getattr(first, "text", "") or "(No text response)"

    # Step 2: Execute tool
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

    tool_msg = {
        "role": "tool",
        "parts": responses,  # must match count of function_call parts
    }

    if stream_final:
        stream = m.generate_content(
            [
                {"role": "user", "parts": [sys_preamble, "\n\nUser: ", user_text]},
                assistant_content,
                tool_msg,
            ],
            stream=True,
        )
        for ev in stream:
            chunk = getattr(ev, "text", None)
            if chunk:
                yield chunk
        return
    else:
        final = m.generate_content(
            [
                {"role": "user", "parts": [sys_preamble, "\n\nUser: ", user_text]},
                assistant_content,
                tool_msg,
            ]
        )
        return getattr(final, "text", "") or "(No text response)"