"""Gmail adapter — 4 tools for search, read, send, and labels."""
from __future__ import annotations

import base64
import email.mime.text
from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import Field
from spine import Core

from conduit.gate import check_gate

SERVICE = "google"
API = "https://gmail.googleapis.com/gmail/v1"

server = FastMCP("Gmail")


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
async def gmail_search(
    query: Annotated[str, Field(description="Gmail search query (e.g. 'from:alice subject:invoice')")],
    max_results: Annotated[int, Field(description="Maximum number of messages to return", ge=1, le=50)] = 5,
) -> list[dict]:
    """Search Gmail messages and return metadata for each result."""
    check_gate(SERVICE)
    headers = _auth_headers()

    async with httpx.AsyncClient() as client:
        # Step 1: list matching message IDs
        list_resp = await client.get(
            f"{API}/users/me/messages",
            headers=headers,
            params={"q": query, "maxResults": max_results},
        )
        list_resp.raise_for_status()
        messages = list_resp.json().get("messages", [])

        if not messages:
            return []

        # Step 2: fetch metadata for each message
        results = []
        for msg in messages:
            meta_resp = await client.get(
                f"{API}/users/me/messages/{msg['id']}",
                headers=headers,
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            )
            meta_resp.raise_for_status()
            data = meta_resp.json()

            header_map = {
                h["name"]: h["value"]
                for h in data.get("payload", {}).get("headers", [])
            }
            results.append({
                "id": data["id"],
                "from": header_map.get("From", ""),
                "subject": header_map.get("Subject", ""),
                "date": header_map.get("Date", ""),
                "snippet": data.get("snippet", ""),
            })

    return results


@server.tool
async def gmail_read(
    message_id: Annotated[str, Field(description="Gmail message ID")],
) -> dict:
    """Read the full body of a Gmail message, decoded from base64url."""
    check_gate(SERVICE)
    headers = _auth_headers()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "full"},
        )
        resp.raise_for_status()
    data = resp.json()

    # Extract headers
    header_map = {
        h["name"]: h["value"]
        for h in data.get("payload", {}).get("headers", [])
    }

    # Decode body — may be in payload.body or payload.parts
    body = ""
    payload = data.get("payload", {})
    raw_body = payload.get("body", {}).get("data", "")

    if raw_body:
        body = base64.urlsafe_b64decode(raw_body + "==").decode("utf-8", errors="replace")
    else:
        # Multipart: look for text/plain part first, fallback to text/html
        for part in payload.get("parts", []):
            mime = part.get("mimeType", "")
            part_data = part.get("body", {}).get("data", "")
            if part_data and mime == "text/plain":
                body = base64.urlsafe_b64decode(part_data + "==").decode("utf-8", errors="replace")
                break
        if not body:
            for part in payload.get("parts", []):
                part_data = part.get("body", {}).get("data", "")
                if part_data:
                    body = base64.urlsafe_b64decode(part_data + "==").decode("utf-8", errors="replace")
                    break

    return {
        "id": data["id"],
        "from": header_map.get("From", ""),
        "to": header_map.get("To", ""),
        "subject": header_map.get("Subject", ""),
        "date": header_map.get("Date", ""),
        "body": body,
        "snippet": data.get("snippet", ""),
    }


@server.tool
async def gmail_send(
    to: Annotated[str, Field(description="Recipient email address")],
    subject: Annotated[str, Field(description="Email subject line")],
    body: Annotated[str, Field(description="Email body (plain text)")],
) -> dict:
    """Send an email via Gmail."""
    check_gate(SERVICE)
    headers = _auth_headers()

    # Build MIME message
    msg = email.mime.text.MIMEText(body, "plain")
    msg["To"] = to
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/users/me/messages/send",
            headers={**headers, "Content-Type": "application/json"},
            json={"raw": raw},
        )
        resp.raise_for_status()

    data = resp.json()
    return {"id": data.get("id", ""), "thread_id": data.get("threadId", ""), "status": "sent"}


@server.tool
async def gmail_labels() -> list[dict]:
    """List all Gmail labels in the account."""
    check_gate(SERVICE)
    headers = _auth_headers()

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API}/users/me/labels", headers=headers)
        resp.raise_for_status()

    return [
        {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "")}
        for lbl in resp.json().get("labels", [])
    ]
