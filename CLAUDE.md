# Conduit — Local MCP Server

Self-hosted MCP server connecting Claude Code to GitHub, Gmail, Google Calendar, Cloudflare, and AWS. All tokens stored locally via 1Password. No cloud proxy.

## Quick Start

```bash
pip install -e ".[dev]"
# One-time: set up Google OAuth
python -m conduit.google_auth
# Run server
python -m conduit
```

## Architecture

- **spine** manages frozen config registry + token store singleton
- **gate** enforces per-service: enabled check, token validity, time-windowed rate limits
- **fastmcp** handles MCP protocol; each adapter is a mounted sub-server
- **1Password CLI** (`op`) stores all tokens — nothing in env vars or .env files

## Config

Edit `conduit.toml` to enable/disable services and set 1Password token references.

## Tests

```bash
pytest -v
```

## 21 Tools

**GitHub** (5): list_repos, create_issue, list_prs, get_pr, search_code
**Gmail** (4): search, read, send, labels
**Google Calendar** (4): list_events, create_event, free_busy, get_event
**Cloudflare** (4): list_zones, list_dns, create_dns, list_workers
**AWS** (4): list_buckets, list_objects, describe_instances, cloudwatch_metrics

## Adding a new adapter

1. Create `src/conduit/adapters/{name}.py`
2. Define `SERVICE = "{name}"` and `server = FastMCP("{Name}")`
3. Add `@server.tool` functions that call `check_gate(SERVICE)` first
4. Add the service to `Config` in `config.py`
5. Add to the import list in `adapters/__init__.py`
