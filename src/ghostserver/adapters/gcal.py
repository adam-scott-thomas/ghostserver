"""Google Calendar adapter — 4 tools for listing, creating, and querying events."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import Field
from spine import Core

from ghostserver.gate import check_gate

SERVICE = "google"
API = "https://www.googleapis.com/calendar/v3"

server = FastMCP("Google Calendar")


def _get_access_token() -> str:
    core = Core.instance()
    config = core.get("config")
    tokens = core.get("tokens")

    client_id = tokens.get(config.google.client_id_ref)
    client_secret = tokens.get(config.google.client_secret_ref)
    refresh_token = tokens.get(config.google.refresh_token_ref)

    return tokens.refresh_google(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token()}"}


@server.tool
async def gcal_list_events(
    days_ahead: Annotated[int, Field(description="Number of days ahead to fetch events", ge=1, le=90)] = 7,
    calendar_id: Annotated[str, Field(description="Calendar ID to query (default: primary)")] = "primary",
) -> list[dict]:
    """List upcoming calendar events within the specified number of days."""
    check_gate(SERVICE)
    headers = _auth_headers()

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/calendars/{calendar_id}/events",
            headers=headers,
            params={
                "timeMin": now.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        resp.raise_for_status()

    items = resp.json().get("items", [])
    results = []
    for item in items:
        start = item.get("start", {})
        end = item.get("end", {})
        results.append({
            "id": item.get("id", ""),
            "summary": item.get("summary", ""),
            "start": start.get("dateTime", start.get("date", "")),
            "end": end.get("dateTime", end.get("date", "")),
            "url": item.get("htmlLink", ""),
        })
    return results


@server.tool
async def gcal_create_event(
    summary: Annotated[str, Field(description="Event title/summary")],
    start_time: Annotated[str, Field(description="Start datetime in ISO 8601 format (e.g. 2024-06-01T10:00:00Z)")],
    end_time: Annotated[str, Field(description="End datetime in ISO 8601 format (e.g. 2024-06-01T11:00:00Z)")],
    description: Annotated[str, Field(description="Optional event description")] = "",
    calendar_id: Annotated[str, Field(description="Calendar ID to create the event in (default: primary)")] = "primary",
) -> dict:
    """Create a new calendar event."""
    check_gate(SERVICE)
    headers = {**_auth_headers(), "Content-Type": "application/json"}

    body: dict = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
    }
    if description:
        body["description"] = description

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/calendars/{calendar_id}/events",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()

    data = resp.json()
    return {
        "id": data.get("id", ""),
        "summary": data.get("summary", ""),
        "url": data.get("htmlLink", ""),
    }


@server.tool
async def gcal_free_busy(
    days_ahead: Annotated[int, Field(description="Number of days ahead to check for busy slots", ge=1, le=30)] = 3,
) -> dict:
    """Query free/busy information for the primary calendar."""
    check_gate(SERVICE)
    headers = {**_auth_headers(), "Content-Type": "application/json"}

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/freeBusy",
            headers=headers,
            json={
                "timeMin": now.isoformat(),
                "timeMax": time_max.isoformat(),
                "items": [{"id": "primary"}],
            },
        )
        resp.raise_for_status()

    data = resp.json()
    busy_slots = data.get("calendars", {}).get("primary", {}).get("busy", [])
    return {
        "busy_slots": busy_slots,
        "count": len(busy_slots),
    }


@server.tool
async def gcal_get_event(
    event_id: Annotated[str, Field(description="Google Calendar event ID")],
    calendar_id: Annotated[str, Field(description="Calendar ID containing the event (default: primary)")] = "primary",
) -> dict:
    """Fetch full details for a specific calendar event."""
    check_gate(SERVICE)
    headers = _auth_headers()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/calendars/{calendar_id}/events/{event_id}",
            headers=headers,
        )
        resp.raise_for_status()

    data = resp.json()
    start = data.get("start", {})
    end = data.get("end", {})
    attendees = [
        {"email": a.get("email", ""), "status": a.get("responseStatus", "")}
        for a in data.get("attendees", [])
    ]
    return {
        "id": data.get("id", ""),
        "summary": data.get("summary", ""),
        "description": data.get("description", ""),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "attendees": attendees,
        "url": data.get("htmlLink", ""),
    }
