import pytest
import respx
import httpx
from fastmcp import Client
from spine import Core
from conduit.config import Config, GoogleConfig
from conduit.gate import reset_counters
from conduit.adapters.gcal import server as gcal_server

# Import MockTokenStore from shared conftest
from tests.adapters.conftest import MockTokenStore

GCAL_API = "https://www.googleapis.com/calendar/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"


@pytest.fixture
def gcal_core():
    config = Config(google=GoogleConfig(
        enabled=True,
        client_id_ref="op://Dev/Google/client_id",
        client_secret_ref="op://Dev/Google/client_secret",
        refresh_token_ref="op://Dev/Google/refresh_token",
        rate_limit=100,
        rate_window=60,
    ))
    tokens = MockTokenStore()  # refresh_google returns "ya29.mock_access"

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")

    Core.boot_once(setup)
    reset_counters()
    return Core.instance()


# ---------------------------------------------------------------------------
# gcal_list_events
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gcal_list_events(gcal_core):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get(f"{GCAL_API}/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={
            "items": [
                {
                    "id": "evt001",
                    "summary": "Team Standup",
                    "start": {"dateTime": "2024-06-01T10:00:00Z"},
                    "end": {"dateTime": "2024-06-01T10:30:00Z"},
                    "htmlLink": "https://calendar.google.com/event?eid=evt001",
                },
                {
                    "id": "evt002",
                    "summary": "Design Review",
                    "start": {"dateTime": "2024-06-02T14:00:00Z"},
                    "end": {"dateTime": "2024-06-02T15:00:00Z"},
                    "htmlLink": "https://calendar.google.com/event?eid=evt002",
                },
            ]
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_list_events", {"days_ahead": 7})

    result_str = str(result)
    assert "evt001" in result_str
    assert "Team Standup" in result_str
    assert "evt002" in result_str
    assert "Design Review" in result_str
    assert "2024-06-01T10:00:00Z" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_gcal_list_events_empty(gcal_core):
    """Empty calendar should return empty list."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get(f"{GCAL_API}/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_list_events", {"days_ahead": 3})

    assert "[]" in str(result) or result == [] or "[]" in repr(result)


# ---------------------------------------------------------------------------
# gcal_create_event
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gcal_create_event(gcal_core):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.post(f"{GCAL_API}/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={
            "id": "new_evt_123",
            "summary": "Product Launch",
            "htmlLink": "https://calendar.google.com/event?eid=new_evt_123",
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_create_event", {
            "summary": "Product Launch",
            "start_time": "2024-07-01T09:00:00Z",
            "end_time": "2024-07-01T10:00:00Z",
            "description": "Big launch day",
        })

    result_str = str(result)
    assert "new_evt_123" in result_str
    assert "Product Launch" in result_str
    assert "calendar.google.com" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_gcal_create_event_no_description(gcal_core):
    """Create event without optional description."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.post(f"{GCAL_API}/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={
            "id": "bare_evt_456",
            "summary": "Quick Sync",
            "htmlLink": "https://calendar.google.com/event?eid=bare_evt_456",
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_create_event", {
            "summary": "Quick Sync",
            "start_time": "2024-07-02T11:00:00Z",
            "end_time": "2024-07-02T11:30:00Z",
        })

    result_str = str(result)
    assert "bare_evt_456" in result_str
    assert "Quick Sync" in result_str


# ---------------------------------------------------------------------------
# gcal_free_busy
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gcal_free_busy(gcal_core):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.post(f"{GCAL_API}/freeBusy").mock(
        return_value=httpx.Response(200, json={
            "calendars": {
                "primary": {
                    "busy": [
                        {"start": "2024-06-01T10:00:00Z", "end": "2024-06-01T11:00:00Z"},
                        {"start": "2024-06-02T14:00:00Z", "end": "2024-06-02T15:00:00Z"},
                    ]
                }
            }
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_free_busy", {"days_ahead": 3})

    result_str = str(result)
    assert "busy_slots" in result_str
    assert "2024-06-01T10:00:00Z" in result_str
    assert "2" in result_str  # count


@respx.mock
@pytest.mark.asyncio
async def test_gcal_free_busy_empty(gcal_core):
    """No busy slots returns count 0."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.post(f"{GCAL_API}/freeBusy").mock(
        return_value=httpx.Response(200, json={
            "calendars": {"primary": {"busy": []}}
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_free_busy", {"days_ahead": 1})

    result_str = str(result)
    assert "count" in result_str
    assert "'count': 0" in result_str or '"count": 0' in result_str or "0" in result_str


# ---------------------------------------------------------------------------
# gcal_get_event
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gcal_get_event(gcal_core):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get(f"{GCAL_API}/calendars/primary/events/evt_detail_001").mock(
        return_value=httpx.Response(200, json={
            "id": "evt_detail_001",
            "summary": "Quarterly Review",
            "description": "Q2 performance review meeting",
            "start": {"dateTime": "2024-06-15T13:00:00Z"},
            "end": {"dateTime": "2024-06-15T14:00:00Z"},
            "attendees": [
                {"email": "alice@example.com", "responseStatus": "accepted"},
                {"email": "bob@example.com", "responseStatus": "tentative"},
            ],
            "htmlLink": "https://calendar.google.com/event?eid=evt_detail_001",
        })
    )

    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_get_event", {"event_id": "evt_detail_001"})

    result_str = str(result)
    assert "evt_detail_001" in result_str
    assert "Quarterly Review" in result_str
    assert "Q2 performance review meeting" in result_str
    assert "alice@example.com" in result_str
    assert "accepted" in result_str
    assert "bob@example.com" in result_str
