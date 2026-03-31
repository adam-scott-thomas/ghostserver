"""Cloudflare adapter — 4 tools for zones, DNS, and Workers."""
from __future__ import annotations

from typing import Annotated
from pydantic import Field

import httpx
from fastmcp import FastMCP
from spine import Core
from conduit.gate import check_gate

SERVICE = "cloudflare"
API = "https://api.cloudflare.com/client/v4"

server = FastMCP("Cloudflare")


def _headers() -> dict[str, str]:
    tokens = Core.instance().get("tokens")
    config = Core.instance().get("config")
    token = tokens.get(config.cloudflare.token_ref)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@server.tool
async def cf_list_zones() -> list[dict]:
    """List all Cloudflare zones (domains) on the account."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/zones",
            headers=_headers(),
            params={"per_page": 50},
        )
        resp.raise_for_status()
    data = resp.json()
    return [
        {"id": z["id"], "name": z["name"], "status": z["status"]}
        for z in data["result"]
    ]


@server.tool
async def cf_list_dns(
    zone_id: Annotated[str, Field(description="Cloudflare zone ID")],
    record_type: Annotated[str, Field(description="Optional DNS record type filter (e.g. A, CNAME, MX)")] = "",
) -> list[dict]:
    """List DNS records for a Cloudflare zone, with optional type filter."""
    check_gate(SERVICE)
    params: dict = {}
    if record_type:
        params["type"] = record_type
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/zones/{zone_id}/dns_records",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
    data = resp.json()
    return [
        {
            "id": r["id"],
            "type": r["type"],
            "name": r["name"],
            "content": r["content"],
            "ttl": r["ttl"],
        }
        for r in data["result"]
    ]


@server.tool
async def cf_create_dns(
    zone_id: Annotated[str, Field(description="Cloudflare zone ID")],
    record_type: Annotated[str, Field(description="DNS record type (e.g. A, CNAME, TXT)")],
    name: Annotated[str, Field(description="DNS record name (e.g. subdomain or @)")],
    content: Annotated[str, Field(description="DNS record content (e.g. IP address or target hostname)")],
    ttl: Annotated[int, Field(description="Time to live in seconds; 1 = automatic")] = 1,
    proxied: Annotated[bool, Field(description="Whether to proxy traffic through Cloudflare")] = False,
) -> dict:
    """Create a new DNS record in a Cloudflare zone."""
    check_gate(SERVICE)
    payload = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/zones/{zone_id}/dns_records",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
    r = resp.json()["result"]
    return {"id": r["id"], "type": r["type"], "name": r["name"], "content": r["content"]}


@server.tool
async def cf_list_workers(
    account_id: Annotated[str, Field(description="Cloudflare account ID")],
) -> list[dict]:
    """List all Cloudflare Workers scripts for an account."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/accounts/{account_id}/workers/scripts",
            headers=_headers(),
        )
        resp.raise_for_status()
    data = resp.json()
    return [
        {"id": w["id"], "modified": w.get("modified_on", "")}
        for w in data["result"]
    ]
