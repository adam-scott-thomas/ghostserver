# GhostServer

Self-hosted MCP server that connects any AI tool to your real accounts. Your tokens never leave your machine.

Works with Claude Code, Cursor, VS Code Copilot, Windsurf, and any MCP-compatible client.

## Why

Every "MCP server" out there is either a setup wizard pointing at someone else's cloud, or locked to one AI vendor. GhostServer runs locally, stores credentials in your own vault, and speaks standard MCP protocol so any client can use it.

## 21 Tools, 5 Services

| Service | Tools |
|---------|-------|
| **GitHub** | list repos, create issues, list/get PRs, search code |
| **Gmail** | search, read, send, list labels |
| **Google Calendar** | list events, create events, free/busy, get event |
| **Cloudflare** | list zones, DNS records, create DNS, list Workers |
| **AWS** | S3 buckets/objects, EC2 instances, CloudWatch metrics |

## Install

```bash
pip install ghostserver
```

Or from source:

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure

```bash
cp ghostserver.toml.example ghostserver.toml
```

Edit `ghostserver.toml` — enable the services you want and set your credential references.

### 2. Store Credentials

GhostServer supports three credential backends:

**Environment variables** (simplest):
```toml
[server]
credential_backend = "env"

[github]
enabled = true
token_ref = "GITHUB_TOKEN"
```
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

**Credentials file** (no env pollution):
```toml
[server]
credential_backend = "file"
credential_file = "~/.ghostserver/credentials"

[github]
enabled = true
token_ref = "GITHUB_TOKEN"
```
```
# ~/.ghostserver/credentials
GITHUB_TOKEN=ghp_your_token_here
CLOUDFLARE_TOKEN=your_cf_token
```

**1Password CLI** (most secure):
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**Auto-detect** (default): tries 1Password, then credentials file, then env vars.

### 3. Google Services (one-time setup)

Gmail and Google Calendar require OAuth. Run the setup wizard once:

```bash
python -m ghostserver.google_auth
```

This opens your browser, gets consent, and stores the refresh token in your chosen backend.

### 4. Connect to your AI tool

**Claude Code:**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code:**
Add to your MCP settings:
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**Any MCP client (stdio):**
```bash
python -m ghostserver
```

## Architecture

```
Your AI Tool (Claude Code, Cursor, etc.)
  |
  | MCP protocol (stdio)
  |
  v
GhostServer (local process)
  |
  |-- spine (frozen config registry)
  |-- gate (per-service rate limiting + enabled checks)
  |-- token store (pluggable: 1Password / env / file)
  |
  |-- GitHub adapter ──> api.github.com
  |-- Gmail adapter ──> gmail.googleapis.com
  |-- Calendar adapter ──> googleapis.com/calendar
  |-- Cloudflare adapter ──> api.cloudflare.com
  |-- AWS adapter ──> boto3 (local credentials)
```

Every adapter is a single file. The gate enforces rate limits per service. Spine provides the frozen config singleton so adapters don't pass objects around.

## Adding Your Own Adapter

Create `src/ghostserver/adapters/myservice.py`:

```python
from fastmcp import FastMCP
from spine import Core
from ghostserver.gate import check_gate

SERVICE = "myservice"
server = FastMCP("My Service")

@server.tool
async def myservice_do_thing(param: str) -> dict:
    """Description for the AI client."""
    check_gate(SERVICE)
    tokens = Core.instance().get("tokens")
    token = tokens.get(Core.instance().get("config").myservice.token_ref)
    # ... call your API ...
    return {"result": "done"}
```

Add the service config to `config.py`, add the module name to `adapters/__init__.py`, done. Submit a PR.

## Development

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## License

MIT
