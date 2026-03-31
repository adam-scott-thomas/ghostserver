import pytest
import respx
import httpx
from fastmcp import Client
from spine import Core
from ghostserver.config import Config, GoogleConfig
from ghostserver.gate import reset_counters
from ghostserver.adapters.gmail import server as gmail_server

# Import MockTokenStore from shared conftest
from tests.adapters.conftest import MockTokenStore


@pytest.fixture
def google_core():
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
# gmail_search
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gmail_search(google_core):
    # Mock token refresh
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    # Mock message list
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages").mock(
        return_value=httpx.Response(200, json={
            "messages": [{"id": "msg001", "threadId": "thread001"}]
        })
    )
    # Mock metadata fetch for msg001
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/msg001").mock(
        return_value=httpx.Response(200, json={
            "id": "msg001",
            "snippet": "Hello from test",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                ]
            },
        })
    )

    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_search", {"query": "from:alice"})

    result_str = str(result)
    assert "msg001" in result_str
    assert "alice@example.com" in result_str
    assert "Test Subject" in result_str
    assert "Hello from test" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_gmail_search_empty(google_core):
    """Search that returns no results should return an empty list."""
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages").mock(
        return_value=httpx.Response(200, json={})
    )

    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_search", {"query": "nothing"})

    assert "[]" in str(result) or result == [] or "[]" in repr(result)


# ---------------------------------------------------------------------------
# gmail_read
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gmail_read(google_core):
    import base64

    body_text = "Hi there, this is the email body."
    encoded_body = base64.urlsafe_b64encode(body_text.encode()).decode()

    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/msg002").mock(
        return_value=httpx.Response(200, json={
            "id": "msg002",
            "snippet": "Hi there...",
            "payload": {
                "headers": [
                    {"name": "From", "value": "bob@example.com"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Subject", "value": "Hello"},
                    {"name": "Date", "value": "Tue, 2 Jan 2024 09:00:00 +0000"},
                ],
                "body": {"data": encoded_body},
            },
        })
    )

    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_read", {"message_id": "msg002"})

    result_str = str(result)
    assert "msg002" in result_str
    assert "bob@example.com" in result_str
    assert "Hello" in result_str
    assert "Hi there, this is the email body." in result_str


# ---------------------------------------------------------------------------
# gmail_send
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gmail_send(google_core):
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={
            "id": "sent001",
            "threadId": "thread001",
        })
    )

    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_send", {
            "to": "recipient@example.com",
            "subject": "Test Send",
            "body": "This is a test email.",
        })

    result_str = str(result)
    assert "sent001" in result_str
    assert "sent" in result_str


# ---------------------------------------------------------------------------
# gmail_labels
# ---------------------------------------------------------------------------

@respx.mock
@pytest.mark.asyncio
async def test_gmail_labels(google_core):
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29.mock_access"})
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/labels").mock(
        return_value=httpx.Response(200, json={
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "SENT", "name": "SENT", "type": "system"},
                {"id": "Label_1", "name": "Work", "type": "user"},
            ]
        })
    )

    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_labels", {})

    result_str = str(result)
    assert "INBOX" in result_str
    assert "Work" in result_str
