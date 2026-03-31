import pytest
import respx
import httpx
from ghostserver.adapters.cloudflare import server as cf_server


@pytest.fixture
def cf_core():
    from spine import Core
    from ghostserver.config import Config, ServiceConfig
    from ghostserver.gate import reset_counters
    from tests.adapters.conftest import MockTokenStore

    config = Config(cloudflare=ServiceConfig(
        enabled=True, token_ref="op://Dev/CF/token",
        rate_limit=100, rate_window=60,
    ))
    tokens = MockTokenStore({"op://Dev/CF/token": "cf_test_token_abc"})

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()
    return Core.instance()


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_zones(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/zones").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [
                {"id": "zone-abc", "name": "example.com", "status": "active"},
                {"id": "zone-def", "name": "example.org", "status": "active"},
            ],
        })
    )
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_zones", {})
        result_str = str(result)
        assert "example.com" in result_str
        assert "zone-abc" in result_str
        assert "active" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_dns(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/zones/zone-abc/dns_records").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [
                {"id": "rec-1", "type": "A", "name": "example.com", "content": "1.2.3.4", "ttl": 1},
                {"id": "rec-2", "type": "CNAME", "name": "www.example.com", "content": "example.com", "ttl": 300},
            ],
        })
    )
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_dns", {"zone_id": "zone-abc"})
        result_str = str(result)
        assert "rec-1" in result_str
        assert "1.2.3.4" in result_str
        assert "CNAME" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_dns_with_type_filter(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/zones/zone-abc/dns_records").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [
                {"id": "rec-1", "type": "A", "name": "example.com", "content": "1.2.3.4", "ttl": 1},
            ],
        })
    )
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_dns", {"zone_id": "zone-abc", "record_type": "A"})
        result_str = str(result)
        assert "rec-1" in result_str
        assert "1.2.3.4" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_cf_create_dns(cf_core):
    respx.post("https://api.cloudflare.com/client/v4/zones/zone-abc/dns_records").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": {
                "id": "rec-new", "type": "A", "name": "api.example.com", "content": "5.6.7.8",
                "ttl": 1, "proxied": False,
            },
        })
    )
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_create_dns", {
            "zone_id": "zone-abc",
            "record_type": "A",
            "name": "api.example.com",
            "content": "5.6.7.8",
        })
        result_str = str(result)
        assert "rec-new" in result_str
        assert "api.example.com" in result_str
        assert "5.6.7.8" in result_str


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_workers(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/accounts/acct-123/workers/scripts").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [
                {"id": "my-worker", "modified_on": "2026-03-01T12:00:00Z"},
                {"id": "another-worker", "modified_on": "2026-02-15T08:30:00Z"},
            ],
        })
    )
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_workers", {"account_id": "acct-123"})
        result_str = str(result)
        assert "my-worker" in result_str
        assert "another-worker" in result_str
        assert "2026-03-01" in result_str
