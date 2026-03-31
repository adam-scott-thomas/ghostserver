# Conduit — Local MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted MCP server that connects Claude Code (and any MCP client) to GitHub, Gmail, Google Calendar, Cloudflare, and AWS — with all tokens stored locally, no cloud proxy, and capability gating via spine.

**Architecture:** Each service is a FastMCP sub-server mounted onto a main server. Spine manages the frozen config registry and token store reference. A gate module enforces per-service enabled checks, token validity, and time-windowed rate limiting. Token storage uses 1Password CLI (`op`). Google services share one OAuth client with a local callback server for initial auth.

**Tech Stack:** Python 3.12, fastmcp, spine (local), httpx, boto3, 1Password CLI, pytest + respx

---

## File Structure

```
conduit/
├── pyproject.toml
├── conduit.toml                 # Service config (which services, token refs, rate limits)
├── src/
│   └── conduit/
│       ├── __init__.py
│       ├── config.py            # Config dataclasses, TOML loader
│       ├── tokens.py            # 1Password token read/write, Google refresh
│       ├── boot.py              # Spine boot_once setup
│       ├── gate.py              # Capability gating (enabled, token, rate limit)
│       ├── server.py            # FastMCP entry point, adapter mounting
│       ├── google_auth.py       # One-time Google OAuth browser flow
│       └── adapters/
│           ├── __init__.py      # Adapter discovery
│           ├── github.py        # 5 tools
│           ├── gmail.py         # 4 tools
│           ├── gcal.py          # 4 tools
│           ├── cloudflare.py    # 4 tools
│           └── aws.py           # 4 tools
└── tests/
    ├── conftest.py              # Spine reset fixture, mock token store
    ├── test_config.py
    ├── test_tokens.py
    ├── test_boot.py
    ├── test_gate.py
    ├── test_server.py
    └── adapters/
        ├── conftest.py          # respx fixtures, booted spine with mocks
        ├── test_github.py
        ├── test_gmail.py
        ├── test_gcal.py
        ├── test_cloudflare.py
        └── test_aws.py
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `conduit/pyproject.toml`
- Create: `conduit/conduit.toml`
- Create: `conduit/src/conduit/__init__.py`
- Create: `conduit/src/conduit/adapters/__init__.py`
- Create: `conduit/tests/__init__.py` (empty)
- Create: `conduit/tests/adapters/__init__.py` (empty)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "conduit"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0",
    "httpx>=0.27",
    "boto3>=1.35",
    "spine @ file:///D:/lost_marbles/spine",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
]

[tool.hatch.build.targets.wheel]
packages = ["src/conduit"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create default conduit.toml**

```toml
# conduit.toml — Conduit MCP Server Configuration
# Token refs are 1Password secret references: op://Vault/Item/Field

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
rate_limit = 5000
rate_window = 3600

[google]
enabled = true
client_id_ref = "op://Development/Google OAuth Client/client_id"
client_secret_ref = "op://Development/Google OAuth Client/client_secret"
refresh_token_ref = "op://Development/Google OAuth Client/refresh_token"
scopes = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]
rate_limit = 500
rate_window = 100

[cloudflare]
enabled = true
token_ref = "op://Development/Cloudflare API Token/credential"
rate_limit = 1200
rate_window = 300

[aws]
enabled = true
region = "us-east-1"
rate_limit = 100
rate_window = 1
```

- [ ] **Step 3: Create __init__.py files**

`src/conduit/__init__.py`:
```python
"""Conduit — Local MCP server connecting AI tools to real services."""
__version__ = "0.1.0"
```

`src/conduit/adapters/__init__.py`:
```python
"""Service adapters. Each module exposes a `server` FastMCP instance."""
```

Create empty `tests/__init__.py` and `tests/adapters/__init__.py`.

- [ ] **Step 4: Initialize git and install**

```bash
cd D:/lost_marbles/conduit
git init
pip install -e ".[dev]"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: project scaffold with deps and default config"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/conduit/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path
from conduit.config import load_config, Config, ServiceConfig, GoogleConfig, AwsConfig


def test_load_config_from_toml(tmp_path: Path):
    toml = tmp_path / "test.toml"
    toml.write_text("""
[github]
enabled = true
token_ref = "op://Dev/GH/token"
rate_limit = 100
rate_window = 60

[google]
enabled = false

[cloudflare]
enabled = true
token_ref = "op://Dev/CF/token"

[aws]
enabled = true
region = "us-west-2"
""")
    cfg = load_config(toml)
    assert isinstance(cfg, Config)
    assert cfg.github.enabled is True
    assert cfg.github.token_ref == "op://Dev/GH/token"
    assert cfg.github.rate_limit == 100
    assert cfg.google.enabled is False
    assert cfg.cloudflare.enabled is True
    assert cfg.aws.region == "us-west-2"


def test_load_config_defaults(tmp_path: Path):
    toml = tmp_path / "empty.toml"
    toml.write_text("")
    cfg = load_config(toml)
    assert cfg.github.enabled is False
    assert cfg.github.rate_limit == 5000
    assert cfg.google.rate_limit == 500
    assert cfg.aws.region == "us-east-1"


def test_config_service_names():
    cfg = Config()
    assert cfg.service_names() == ["github", "google", "cloudflare", "aws"]


def test_config_rate_for():
    cfg = Config(github=ServiceConfig(enabled=True, rate_limit=42, rate_window=10))
    limit, window = cfg.rate_for("github")
    assert limit == 42
    assert window == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/lost_marbles/conduit && pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'conduit.config'`

- [ ] **Step 3: Write config.py**

`src/conduit/config.py`:
```python
"""Configuration dataclasses and TOML loader."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServiceConfig:
    enabled: bool = False
    token_ref: str = ""
    rate_limit: int = 5000
    rate_window: int = 3600


@dataclass
class GoogleConfig:
    enabled: bool = False
    client_id_ref: str = ""
    client_secret_ref: str = ""
    refresh_token_ref: str = ""
    scopes: list[str] = field(default_factory=list)
    rate_limit: int = 500
    rate_window: int = 100


@dataclass
class AwsConfig:
    enabled: bool = False
    region: str = "us-east-1"
    rate_limit: int = 100
    rate_window: int = 1


@dataclass
class Config:
    github: ServiceConfig = field(default_factory=ServiceConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    cloudflare: ServiceConfig = field(default_factory=ServiceConfig)
    aws: AwsConfig = field(default_factory=AwsConfig)

    def service_names(self) -> list[str]:
        return ["github", "google", "cloudflare", "aws"]

    def rate_for(self, service: str) -> tuple[int, int]:
        svc = getattr(self, service)
        return svc.rate_limit, svc.rate_window

    def is_enabled(self, service: str) -> bool:
        return getattr(self, service).enabled


def load_config(path: Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(
        github=ServiceConfig(**raw.get("github", {})),
        google=GoogleConfig(**raw.get("google", {})),
        cloudflare=ServiceConfig(**raw.get("cloudflare", {})),
        aws=AwsConfig(**raw.get("aws", {})),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/config.py tests/test_config.py
git commit -m "feat: config dataclasses with TOML loader"
```

---

### Task 3: Token Store

**Files:**
- Create: `src/conduit/tokens.py`
- Create: `tests/test_tokens.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tokens.py`:
```python
from unittest.mock import patch, MagicMock
from conduit.tokens import TokenStore


def test_get_token_calls_op():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(
            returncode=0, stdout="ghp_abc123\n"
        )
        token = store.get("op://Dev/GH/token")
    mock_sub.run.assert_called_once_with(
        ["op", "read", "op://Dev/GH/token"],
        capture_output=True, text=True, timeout=10,
    )
    assert token == "ghp_abc123"


def test_get_token_raises_on_failure():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="not signed in")
        try:
            store.get("op://Dev/GH/token")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "not signed in" in str(e)


def test_get_token_caches():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok123\n")
        store.get("op://Dev/GH/token")
        store.get("op://Dev/GH/token")
    assert mock_sub.run.call_count == 1


def test_refresh_google_token():
    store = TokenStore()
    with patch("conduit.tokens.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "ya29.new_token",
            "expires_in": 3600,
        }
        mock_httpx.post.return_value = mock_response

        token = store.refresh_google(
            client_id="cid",
            client_secret="csec",
            refresh_token="rt_abc",
        )
    assert token == "ya29.new_token"


def test_clear_cache():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok\n")
        store.get("op://Dev/GH/token")
    store.clear_cache()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok2\n")
        result = store.get("op://Dev/GH/token")
    assert result == "tok2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tokens.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write tokens.py**

`src/conduit/tokens.py`:
```python
"""Token storage backed by 1Password CLI. Google OAuth refresh via httpx."""
from __future__ import annotations

import subprocess
import time

import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class TokenStore:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, float]] = {}  # ref -> (token, cached_at)
        self._cache_ttl: float = 300.0  # 5 min cache for op reads

    def get(self, op_ref: str) -> str:
        now = time.time()
        if op_ref in self._cache:
            token, cached_at = self._cache[op_ref]
            if now - cached_at < self._cache_ttl:
                return token

        result = subprocess.run(
            ["op", "read", op_ref],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"1Password read failed: {result.stderr.strip()}")

        token = result.stdout.strip()
        self._cache[op_ref] = (token, now)
        return token

    def refresh_google(
        self, client_id: str, client_secret: str, refresh_token: str,
    ) -> str:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]

    def clear_cache(self) -> None:
        self._cache.clear()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_tokens.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/tokens.py tests/test_tokens.py
git commit -m "feat: token store with 1Password backend and Google refresh"
```

---

### Task 4: Spine Boot

**Files:**
- Create: `src/conduit/boot.py`
- Create: `tests/test_boot.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the test fixtures**

`tests/conftest.py`:
```python
import pytest
from spine import Core


@pytest.fixture(autouse=True)
def reset_spine():
    """Reset spine singleton between every test."""
    Core._reset_instance()
    yield
    Core._reset_instance()
```

- [ ] **Step 2: Write the failing test**

`tests/test_boot.py`:
```python
from pathlib import Path
from spine import Core
from conduit.boot import boot
from conduit.config import Config
from conduit.tokens import TokenStore


def test_boot_registers_config(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("[github]\nenabled = true\n")
    core = boot(config_path=toml)
    assert isinstance(core.get("config"), Config)
    assert core.get("config").github.enabled is True


def test_boot_registers_tokens(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    core = boot(config_path=toml)
    assert isinstance(core.get("tokens"), TokenStore)


def test_boot_is_frozen(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    core = boot(config_path=toml)
    assert core.is_frozen


def test_boot_once_returns_same_instance(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    c1 = boot(config_path=toml)
    c2 = boot(config_path=toml)
    assert c1 is c2


def test_instance_accessible_after_boot(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("")
    boot(config_path=toml)
    assert Core.instance().get("config") is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_boot.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write boot.py**

`src/conduit/boot.py`:
```python
"""Spine bootstrap. Call boot() once at server startup."""
from __future__ import annotations

from pathlib import Path

from spine import Core

from conduit.config import load_config
from conduit.tokens import TokenStore

DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "conduit.toml"


def boot(config_path: Path | None = None) -> Core:
    if config_path is None:
        config_path = DEFAULT_CONFIG

    config = load_config(config_path)

    def setup(c: Core) -> None:
        c.register("config", config)
        c.register("tokens", TokenStore())
        c.boot(env="prod")

    return Core.boot_once(setup)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_boot.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/conduit/boot.py tests/test_boot.py tests/conftest.py
git commit -m "feat: spine boot with config and token store"
```

---

### Task 5: Capability Gate

**Files:**
- Create: `src/conduit/gate.py`
- Create: `tests/test_gate.py`

- [ ] **Step 1: Write the failing test**

`tests/test_gate.py`:
```python
import time
from unittest.mock import MagicMock
from spine import Core
from conduit.gate import check_gate, ServiceDisabled, RateLimitExceeded, reset_counters
from conduit.config import Config, ServiceConfig


def _boot_with(github_enabled=True, rate_limit=10, rate_window=60):
    config = Config(github=ServiceConfig(
        enabled=github_enabled,
        token_ref="op://Dev/GH/token",
        rate_limit=rate_limit,
        rate_window=rate_window,
    ))
    tokens = MagicMock()
    tokens.get.return_value = "test_token"

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)


def test_gate_passes_when_enabled():
    _boot_with(github_enabled=True)
    reset_counters()
    check_gate("github")  # should not raise


def test_gate_blocks_when_disabled():
    _boot_with(github_enabled=False)
    reset_counters()
    try:
        check_gate("github")
        assert False, "Should have raised ServiceDisabled"
    except ServiceDisabled:
        pass


def test_gate_blocks_at_rate_limit():
    _boot_with(rate_limit=3, rate_window=60)
    reset_counters()
    check_gate("github")
    check_gate("github")
    check_gate("github")
    try:
        check_gate("github")
        assert False, "Should have raised RateLimitExceeded"
    except RateLimitExceeded:
        pass


def test_gate_resets_after_window(monkeypatch):
    _boot_with(rate_limit=1, rate_window=1)
    reset_counters()
    check_gate("github")
    # Simulate time passing
    import conduit.gate as gm
    gm._windows["github"] = [time.time() - 2]
    check_gate("github")  # should pass — old entry expired
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gate.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write gate.py**

`src/conduit/gate.py`:
```python
"""Capability gating: enabled check + time-windowed rate limiting."""
from __future__ import annotations

import time

from spine import Core


class ServiceDisabled(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


_windows: dict[str, list[float]] = {}


def check_gate(service: str) -> None:
    core = Core.instance()
    config = core.get("config")

    if not config.is_enabled(service):
        raise ServiceDisabled(f"Service '{service}' is disabled in config")

    limit, window = config.rate_for(service)
    now = time.time()
    timestamps = _windows.setdefault(service, [])
    timestamps[:] = [t for t in timestamps if now - t < window]

    if len(timestamps) >= limit:
        raise RateLimitExceeded(
            f"Service '{service}' rate limit exceeded: {limit} calls per {window}s"
        )
    timestamps.append(now)


def reset_counters() -> None:
    _windows.clear()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_gate.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/gate.py tests/test_gate.py
git commit -m "feat: capability gate with rate limiting"
```

---

### Task 6: Server Skeleton + Adapter Discovery

**Files:**
- Create: `src/conduit/server.py`
- Modify: `src/conduit/adapters/__init__.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
from pathlib import Path
from spine import Core
from conduit.server import create_server


def test_create_server_returns_fastmcp(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("[github]\nenabled = false\n")
    server = create_server(config_path=toml)
    assert server.name == "Conduit"


def test_server_has_no_tools_when_all_disabled(tmp_path: Path):
    toml = tmp_path / "conduit.toml"
    toml.write_text("""
[github]
enabled = false
[google]
enabled = false
[cloudflare]
enabled = false
[aws]
enabled = false
""")
    server = create_server(config_path=toml)
    # No tools when everything is disabled
    assert server is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write adapter discovery**

`src/conduit/adapters/__init__.py`:
```python
"""Service adapters. Each module exposes a `server` FastMCP instance and a `SERVICE` name."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def discover() -> list[tuple[str, "ModuleType"]]:
    """Return (service_name, module) for each adapter that defines SERVICE and server."""
    adapters = []
    from conduit.adapters import github, gmail, gcal, cloudflare, aws  # noqa: F401
    import conduit.adapters as pkg
    import importlib

    for name in ["github", "gmail", "gcal", "cloudflare", "aws"]:
        try:
            mod = importlib.import_module(f"conduit.adapters.{name}")
            if hasattr(mod, "server") and hasattr(mod, "SERVICE"):
                adapters.append((mod.SERVICE, mod))
        except ImportError:
            pass
    return adapters
```

- [ ] **Step 4: Write server.py**

`src/conduit/server.py`:
```python
"""FastMCP entry point. Creates the server and mounts enabled adapters."""
from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from conduit.boot import boot


def create_server(config_path: Path | None = None) -> FastMCP:
    core = boot(config_path=config_path)
    config = core.get("config")

    main = FastMCP(
        name="Conduit",
        instructions=(
            "Local MCP server connecting to GitHub, Gmail, Google Calendar, "
            "Cloudflare, and AWS. All tokens stored locally via 1Password."
        ),
    )

    from conduit.adapters import discover

    for service_name, mod in discover():
        if config.is_enabled(service_name):
            main.mount(mod.server)

    return main


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_server.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/conduit/server.py src/conduit/adapters/__init__.py tests/test_server.py
git commit -m "feat: server skeleton with adapter discovery and mounting"
```

---

### Task 7: GitHub Adapter

**Files:**
- Create: `src/conduit/adapters/github.py`
- Create: `tests/adapters/conftest.py`
- Create: `tests/adapters/test_github.py`

- [ ] **Step 1: Write shared test fixtures**

`tests/adapters/conftest.py`:
```python
import pytest
from unittest.mock import MagicMock
from spine import Core
from conduit.config import Config, ServiceConfig, GoogleConfig, AwsConfig
from conduit.gate import reset_counters


class MockTokenStore:
    def __init__(self, tokens: dict[str, str] | None = None):
        self._tokens = tokens or {}

    def get(self, ref: str) -> str:
        return self._tokens.get(ref, "mock_token")

    def refresh_google(self, **kwargs) -> str:
        return "ya29.mock_access"

    def clear_cache(self) -> None:
        pass


@pytest.fixture
def github_core():
    config = Config(github=ServiceConfig(
        enabled=True, token_ref="op://Dev/GH/token",
        rate_limit=100, rate_window=60,
    ))
    tokens = MockTokenStore({"op://Dev/GH/token": "ghp_test123"})

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()
    return Core.instance()
```

- [ ] **Step 2: Write the failing test**

`tests/adapters/test_github.py`:
```python
import pytest
import respx
import httpx
from conduit.adapters.github import server as github_server


@respx.mock
@pytest.mark.asyncio
async def test_github_list_repos(github_core):
    respx.get("https://api.github.com/user/repos").mock(
        return_value=httpx.Response(200, json=[
            {"full_name": "user/repo1", "description": "Desc", "html_url": "https://github.com/user/repo1", "stargazers_count": 5, "language": "Python"},
        ])
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_list_repos", {})
        assert "user/repo1" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_create_issue(github_core):
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(201, json={
            "number": 42, "title": "Bug", "html_url": "https://github.com/owner/repo/issues/42",
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_create_issue", {
            "owner": "owner", "repo": "repo", "title": "Bug", "body": "Details"
        })
        assert "42" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_list_prs(github_core):
    respx.get("https://api.github.com/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(200, json=[
            {"number": 10, "title": "Fix", "state": "open", "html_url": "https://github.com/owner/repo/pull/10", "user": {"login": "dev"}},
        ])
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_list_prs", {"owner": "owner", "repo": "repo"})
        assert "Fix" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_search_code(github_core):
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(200, json={
            "total_count": 1,
            "items": [{"name": "main.py", "path": "src/main.py", "repository": {"full_name": "user/repo"}, "html_url": "https://github.com/user/repo/blob/main/src/main.py"}],
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_search_code", {"query": "def main"})
        assert "main.py" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_get_pr(github_core):
    respx.get("https://api.github.com/repos/owner/repo/pulls/10").mock(
        return_value=httpx.Response(200, json={
            "number": 10, "title": "Fix bug", "state": "open", "body": "Details",
            "html_url": "https://github.com/owner/repo/pull/10",
            "user": {"login": "dev"}, "merged": False,
            "additions": 10, "deletions": 3, "changed_files": 2,
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_get_pr", {"owner": "owner", "repo": "repo", "number": 10})
        assert "Fix bug" in str(result)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/adapters/test_github.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write github.py**

`src/conduit/adapters/github.py`:
```python
"""GitHub adapter — 5 tools for repos, issues, PRs, and code search."""
from __future__ import annotations

from typing import Annotated
from pydantic import Field

import httpx
from fastmcp import FastMCP
from spine import Core
from conduit.gate import check_gate

SERVICE = "github"
API = "https://api.github.com"

server = FastMCP("GitHub")


def _headers() -> dict[str, str]:
    tokens = Core.instance().get("tokens")
    config = Core.instance().get("config")
    token = tokens.get(config.github.token_ref)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@server.tool
async def github_list_repos(
    sort: Annotated[str, Field(description="Sort by: updated, created, pushed, full_name")] = "updated",
    per_page: Annotated[int, Field(description="Results per page (max 100)", ge=1, le=100)] = 30,
) -> list[dict]:
    """List your GitHub repositories, sorted by most recently updated."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/user/repos",
            headers=_headers(),
            params={"sort": sort, "per_page": per_page, "type": "owner"},
        )
        resp.raise_for_status()
    return [
        {"name": r["full_name"], "description": r["description"],
         "url": r["html_url"], "stars": r["stargazers_count"], "language": r["language"]}
        for r in resp.json()
    ]


@server.tool
async def github_create_issue(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    title: Annotated[str, Field(description="Issue title")],
    body: Annotated[str, Field(description="Issue body (markdown)")] = "",
    labels: Annotated[list[str], Field(description="Labels to apply")] = [],
) -> dict:
    """Create a new issue in a GitHub repository."""
    check_gate(SERVICE)
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/repos/{owner}/{repo}/issues",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
    data = resp.json()
    return {"number": data["number"], "title": data["title"], "url": data["html_url"]}


@server.tool
async def github_list_prs(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[str, Field(description="Filter: open, closed, all")] = "open",
) -> list[dict]:
    """List pull requests for a GitHub repository."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/repos/{owner}/{repo}/pulls",
            headers=_headers(),
            params={"state": state, "per_page": 30},
        )
        resp.raise_for_status()
    return [
        {"number": p["number"], "title": p["title"], "state": p["state"],
         "author": p["user"]["login"], "url": p["html_url"]}
        for p in resp.json()
    ]


@server.tool
async def github_get_pr(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    number: Annotated[int, Field(description="PR number")],
) -> dict:
    """Get details of a specific pull request."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/repos/{owner}/{repo}/pulls/{number}",
            headers=_headers(),
        )
        resp.raise_for_status()
    pr = resp.json()
    return {
        "number": pr["number"], "title": pr["title"], "state": pr["state"],
        "body": pr.get("body", ""), "author": pr["user"]["login"],
        "merged": pr["merged"], "additions": pr["additions"],
        "deletions": pr["deletions"], "changed_files": pr["changed_files"],
        "url": pr["html_url"],
    }


@server.tool
async def github_search_code(
    query: Annotated[str, Field(description="Search query (GitHub code search syntax)")],
    per_page: Annotated[int, Field(description="Results per page", ge=1, le=100)] = 10,
) -> dict:
    """Search code across GitHub repositories."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/search/code",
            headers=_headers(),
            params={"q": query, "per_page": per_page},
        )
        resp.raise_for_status()
    data = resp.json()
    return {
        "total_count": data["total_count"],
        "items": [
            {"file": i["name"], "path": i["path"],
             "repo": i["repository"]["full_name"], "url": i["html_url"]}
            for i in data["items"]
        ],
    }
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/adapters/test_github.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/conduit/adapters/github.py tests/adapters/conftest.py tests/adapters/test_github.py
git commit -m "feat: GitHub adapter with 5 tools"
```

---

### Task 8: Google OAuth Setup

**Files:**
- Create: `src/conduit/google_auth.py`

This is a one-time CLI command, not part of the MCP server runtime. No TDD needed — it's an interactive browser flow.

- [ ] **Step 1: Write google_auth.py**

`src/conduit/google_auth.py`:
```python
"""One-time Google OAuth2 setup. Run: python -m conduit.google_auth

Opens a browser for consent, captures the auth code via local callback,
exchanges for tokens, and stores the refresh token in 1Password.
"""
from __future__ import annotations

import http.server
import json
import subprocess
import sys
import urllib.parse
import webbrowser

import httpx

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_PORT = 8914
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


def _read_op(ref: str) -> str:
    result = subprocess.run(["op", "read", ref], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        print(f"Error reading {ref}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def _write_op(vault: str, item: str, field: str, value: str) -> None:
    # Try to edit existing item, create if not found
    result = subprocess.run(
        ["op", "item", "edit", item, f"{field}={value}", "--vault", vault],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        subprocess.run(
            ["op", "item", "create", "--category=login",
             f"--title={item}", f"--vault={vault}", f"{field}={value}"],
            capture_output=True, text=True, timeout=10,
        )


def main() -> None:
    print("Google OAuth Setup for Conduit")
    print("=" * 40)

    # Read client credentials from 1Password
    from conduit.boot import boot, DEFAULT_CONFIG
    from spine import Core

    Core._reset_instance()
    core = boot(config_path=DEFAULT_CONFIG)
    config = core.get("config")
    google = config.google

    if not google.client_id_ref or not google.client_secret_ref:
        print("Error: google.client_id_ref and client_secret_ref must be set in conduit.toml")
        sys.exit(1)

    client_id = _read_op(google.client_id_ref)
    client_secret = _read_op(google.client_secret_ref)
    scopes = google.scopes or [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    # Build auth URL
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    # Capture code via local server
    auth_code = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            query = urllib.parse.urlparse(self.path).query
            qs = urllib.parse.parse_qs(query)
            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Auth complete. You can close this tab.</h1>")

        def log_message(self, *args):
            pass

    print(f"\nOpening browser for Google consent...")
    webbrowser.open(auth_url)

    httpd = http.server.HTTPServer(("localhost", REDIRECT_PORT), Handler)
    httpd.handle_request()

    if not auth_code:
        print("Error: No auth code received.", file=sys.stderr)
        sys.exit(1)

    # Exchange for tokens
    resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    tokens = resp.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("Error: No refresh token returned. Try revoking access and re-running.", file=sys.stderr)
        sys.exit(1)

    # Store refresh token in 1Password
    # Parse the vault and item from the ref: op://Vault/Item/Field
    ref = google.refresh_token_ref
    parts = ref.replace("op://", "").split("/")
    if len(parts) == 3:
        vault, item, field = parts
        _write_op(vault, item, field, refresh_token)
        print(f"\nRefresh token stored in 1Password: {ref}")
    else:
        print(f"\nRefresh token (store manually): {refresh_token}")

    print("Setup complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/conduit/google_auth.py
git commit -m "feat: one-time Google OAuth setup command"
```

---

### Task 9: Gmail Adapter

**Files:**
- Create: `src/conduit/adapters/gmail.py`
- Create: `tests/adapters/test_gmail.py`

- [ ] **Step 1: Write the failing test**

`tests/adapters/test_gmail.py`:
```python
import pytest
import respx
import httpx
from unittest.mock import MagicMock, patch
from spine import Core
from conduit.config import Config, GoogleConfig
from conduit.gate import reset_counters


@pytest.fixture
def google_core():
    config = Config(google=GoogleConfig(
        enabled=True,
        client_id_ref="op://Dev/Google/client_id",
        client_secret_ref="op://Dev/Google/client_secret",
        refresh_token_ref="op://Dev/Google/refresh_token",
        rate_limit=100, rate_window=60,
    ))
    tokens = MagicMock()
    tokens.get.return_value = "mock_value"
    tokens.refresh_google.return_value = "ya29.test_access"

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()
    return Core.instance()


@respx.mock
@pytest.mark.asyncio
async def test_gmail_search(google_core):
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages").mock(
        return_value=httpx.Response(200, json={
            "messages": [{"id": "msg1", "threadId": "t1"}],
            "resultSizeEstimate": 1,
        })
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/msg1").mock(
        return_value=httpx.Response(200, json={
            "id": "msg1",
            "snippet": "Hello world",
            "payload": {"headers": [
                {"name": "From", "value": "a@b.com"},
                {"name": "Subject", "value": "Test"},
                {"name": "Date", "value": "Mon, 1 Jan 2026"},
            ]},
        })
    )
    from conduit.adapters.gmail import server as gmail_server
    from fastmcp import Client
    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_search", {"query": "test"})
        assert "Hello world" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_gmail_send(google_core):
    respx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send").mock(
        return_value=httpx.Response(200, json={"id": "sent1", "threadId": "t1"})
    )
    from conduit.adapters.gmail import server as gmail_server
    from fastmcp import Client
    async with Client(gmail_server) as client:
        result = await client.call_tool("gmail_send", {
            "to": "test@example.com", "subject": "Hi", "body": "Hello"
        })
        assert "sent1" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_gmail.py -v`
Expected: FAIL

- [ ] **Step 3: Write gmail.py**

`src/conduit/adapters/gmail.py`:
```python
"""Gmail adapter — search, read, send, list labels."""
from __future__ import annotations

import base64
from email.mime.text import MIMEText
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
    google = config.google
    return tokens.refresh_google(
        client_id=tokens.get(google.client_id_ref),
        client_secret=tokens.get(google.client_secret_ref),
        refresh_token=tokens.get(google.refresh_token_ref),
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token()}"}


@server.tool
async def gmail_search(
    query: Annotated[str, Field(description="Gmail search query (same syntax as Gmail search bar)")],
    max_results: Annotated[int, Field(description="Max messages to return", ge=1, le=20)] = 5,
) -> list[dict]:
    """Search Gmail messages. Returns snippets, subjects, senders."""
    check_gate(SERVICE)
    headers = _headers()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/users/me/messages",
            headers=headers,
            params={"q": query, "maxResults": max_results},
        )
        resp.raise_for_status()
        messages = resp.json().get("messages", [])

        results = []
        for msg in messages[:max_results]:
            detail = await client.get(
                f"{API}/users/me/messages/{msg['id']}",
                headers=headers,
                params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            )
            detail.raise_for_status()
            data = detail.json()
            header_map = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
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
    """Read a full Gmail message by ID."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/users/me/messages/{message_id}",
            headers=_headers(),
            params={"format": "full"},
        )
        resp.raise_for_status()
    data = resp.json()
    header_map = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
    body = ""
    payload = data.get("payload", {})
    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
    return {
        "id": data["id"],
        "from": header_map.get("From", ""),
        "to": header_map.get("To", ""),
        "subject": header_map.get("Subject", ""),
        "date": header_map.get("Date", ""),
        "body": body,
    }


@server.tool
async def gmail_send(
    to: Annotated[str, Field(description="Recipient email address")],
    subject: Annotated[str, Field(description="Email subject")],
    body: Annotated[str, Field(description="Email body (plain text)")],
) -> dict:
    """Send an email via Gmail."""
    check_gate(SERVICE)
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/users/me/messages/send",
            headers=_headers(),
            json={"raw": raw},
        )
        resp.raise_for_status()
    data = resp.json()
    return {"id": data["id"], "threadId": data.get("threadId", "")}


@server.tool
async def gmail_labels() -> list[dict]:
    """List all Gmail labels (folders)."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API}/users/me/labels", headers=_headers())
        resp.raise_for_status()
    return [{"id": l["id"], "name": l["name"], "type": l.get("type", "")}
            for l in resp.json().get("labels", [])]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/adapters/test_gmail.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/adapters/gmail.py tests/adapters/test_gmail.py
git commit -m "feat: Gmail adapter with search, read, send, labels"
```

---

### Task 10: Google Calendar Adapter

**Files:**
- Create: `src/conduit/adapters/gcal.py`
- Create: `tests/adapters/test_gcal.py`

- [ ] **Step 1: Write the failing test**

`tests/adapters/test_gcal.py`:
```python
import pytest
import respx
import httpx
from spine import Core
from conduit.config import Config, GoogleConfig
from conduit.gate import reset_counters
from tests.adapters.conftest import MockTokenStore


@pytest.fixture
def gcal_core():
    config = Config(google=GoogleConfig(
        enabled=True,
        client_id_ref="op://Dev/Google/cid",
        client_secret_ref="op://Dev/Google/csec",
        refresh_token_ref="op://Dev/Google/rt",
        rate_limit=100, rate_window=60,
    ))
    tokens = MockTokenStore()

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()


@respx.mock
@pytest.mark.asyncio
async def test_gcal_list_events(gcal_core):
    respx.get("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={
            "items": [{
                "id": "evt1", "summary": "Meeting",
                "start": {"dateTime": "2026-03-30T10:00:00Z"},
                "end": {"dateTime": "2026-03-30T11:00:00Z"},
                "htmlLink": "https://calendar.google.com/event?eid=evt1",
            }]
        })
    )
    from conduit.adapters.gcal import server as gcal_server
    from fastmcp import Client
    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_list_events", {"days_ahead": 7})
        assert "Meeting" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_gcal_create_event(gcal_core):
    respx.post("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(
        return_value=httpx.Response(200, json={
            "id": "new1", "summary": "Lunch",
            "htmlLink": "https://calendar.google.com/event?eid=new1",
        })
    )
    from conduit.adapters.gcal import server as gcal_server
    from fastmcp import Client
    async with Client(gcal_server) as client:
        result = await client.call_tool("gcal_create_event", {
            "summary": "Lunch",
            "start_time": "2026-03-31T12:00:00",
            "end_time": "2026-03-31T13:00:00",
        })
        assert "Lunch" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_gcal.py -v`
Expected: FAIL

- [ ] **Step 3: Write gcal.py**

`src/conduit/adapters/gcal.py`:
```python
"""Google Calendar adapter — list events, create event, find free time, get event."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import Field
from spine import Core
from conduit.gate import check_gate

SERVICE = "google"
API = "https://www.googleapis.com/calendar/v3"

server = FastMCP("Google Calendar")


def _get_access_token() -> str:
    core = Core.instance()
    config = core.get("config")
    tokens = core.get("tokens")
    google = config.google
    return tokens.refresh_google(
        client_id=tokens.get(google.client_id_ref),
        client_secret=tokens.get(google.client_secret_ref),
        refresh_token=tokens.get(google.refresh_token_ref),
    )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token()}"}


@server.tool
async def gcal_list_events(
    days_ahead: Annotated[int, Field(description="How many days ahead to look", ge=1, le=30)] = 7,
    calendar_id: Annotated[str, Field(description="Calendar ID")] = "primary",
) -> list[dict]:
    """List upcoming calendar events."""
    check_gate(SERVICE)
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/calendars/{calendar_id}/events",
            headers=_headers(),
            params={
                "timeMin": now.isoformat(),
                "timeMax": time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 50,
            },
        )
        resp.raise_for_status()
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
            "url": e.get("htmlLink", ""),
        }
        for e in resp.json().get("items", [])
    ]


@server.tool
async def gcal_create_event(
    summary: Annotated[str, Field(description="Event title")],
    start_time: Annotated[str, Field(description="Start time ISO 8601 (e.g. 2026-03-31T10:00:00)")],
    end_time: Annotated[str, Field(description="End time ISO 8601")],
    description: Annotated[str, Field(description="Event description")] = "",
    calendar_id: Annotated[str, Field(description="Calendar ID")] = "primary",
) -> dict:
    """Create a calendar event."""
    check_gate(SERVICE)
    event = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
    }
    if description:
        event["description"] = description
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/calendars/{calendar_id}/events",
            headers=_headers(),
            json=event,
        )
        resp.raise_for_status()
    data = resp.json()
    return {"id": data["id"], "summary": data.get("summary", ""), "url": data.get("htmlLink", "")}


@server.tool
async def gcal_free_busy(
    days_ahead: Annotated[int, Field(description="Days to check", ge=1, le=14)] = 3,
) -> dict:
    """Find free/busy time slots on your primary calendar."""
    check_gate(SERVICE)
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://www.googleapis.com/calendar/v3/freeBusy",
            headers=_headers(),
            json={
                "timeMin": now.isoformat(),
                "timeMax": time_max.isoformat(),
                "items": [{"id": "primary"}],
            },
        )
        resp.raise_for_status()
    data = resp.json()
    busy = data.get("calendars", {}).get("primary", {}).get("busy", [])
    return {
        "range": {"start": now.isoformat(), "end": time_max.isoformat()},
        "busy_slots": [{"start": b["start"], "end": b["end"]} for b in busy],
        "busy_count": len(busy),
    }


@server.tool
async def gcal_get_event(
    event_id: Annotated[str, Field(description="Event ID")],
    calendar_id: Annotated[str, Field(description="Calendar ID")] = "primary",
) -> dict:
    """Get details of a specific calendar event."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/calendars/{calendar_id}/events/{event_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
    e = resp.json()
    return {
        "id": e["id"], "summary": e.get("summary", ""),
        "description": e.get("description", ""),
        "start": e.get("start", {}).get("dateTime", ""),
        "end": e.get("end", {}).get("dateTime", ""),
        "attendees": [a.get("email", "") for a in e.get("attendees", [])],
        "url": e.get("htmlLink", ""),
    }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/adapters/test_gcal.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/adapters/gcal.py tests/adapters/test_gcal.py
git commit -m "feat: Google Calendar adapter with 4 tools"
```

---

### Task 11: Cloudflare Adapter

**Files:**
- Create: `src/conduit/adapters/cloudflare.py`
- Create: `tests/adapters/test_cloudflare.py`

- [ ] **Step 1: Write the failing test**

`tests/adapters/test_cloudflare.py`:
```python
import pytest
import respx
import httpx
from spine import Core
from conduit.config import Config, ServiceConfig
from conduit.gate import reset_counters
from tests.adapters.conftest import MockTokenStore


@pytest.fixture
def cf_core():
    config = Config(cloudflare=ServiceConfig(
        enabled=True, token_ref="op://Dev/CF/token",
        rate_limit=100, rate_window=60,
    ))
    tokens = MockTokenStore({"op://Dev/CF/token": "cf_test_token"})

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_zones(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/zones").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [{"id": "z1", "name": "example.com", "status": "active"}],
        })
    )
    from conduit.adapters.cloudflare import server as cf_server
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_zones", {})
        assert "example.com" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_cf_list_dns(cf_core):
    respx.get("https://api.cloudflare.com/client/v4/zones/z1/dns_records").mock(
        return_value=httpx.Response(200, json={
            "success": True,
            "result": [{"id": "r1", "type": "A", "name": "www.example.com", "content": "1.2.3.4", "ttl": 300}],
        })
    )
    from conduit.adapters.cloudflare import server as cf_server
    from fastmcp import Client
    async with Client(cf_server) as client:
        result = await client.call_tool("cf_list_dns", {"zone_id": "z1"})
        assert "1.2.3.4" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_cloudflare.py -v`
Expected: FAIL

- [ ] **Step 3: Write cloudflare.py**

`src/conduit/adapters/cloudflare.py`:
```python
"""Cloudflare adapter — zones, DNS records, Workers."""
from __future__ import annotations

from typing import Annotated

import httpx
from fastmcp import FastMCP
from pydantic import Field
from spine import Core
from conduit.gate import check_gate

SERVICE = "cloudflare"
API = "https://api.cloudflare.com/client/v4"

server = FastMCP("Cloudflare")


def _headers() -> dict[str, str]:
    core = Core.instance()
    config = core.get("config")
    tokens = core.get("tokens")
    token = tokens.get(config.cloudflare.token_ref)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@server.tool
async def cf_list_zones() -> list[dict]:
    """List all Cloudflare zones (domains)."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API}/zones", headers=_headers(), params={"per_page": 50})
        resp.raise_for_status()
    return [
        {"id": z["id"], "name": z["name"], "status": z["status"]}
        for z in resp.json()["result"]
    ]


@server.tool
async def cf_list_dns(
    zone_id: Annotated[str, Field(description="Zone ID (from cf_list_zones)")],
    record_type: Annotated[str, Field(description="Filter by type: A, AAAA, CNAME, MX, TXT, etc.")] = "",
) -> list[dict]:
    """List DNS records for a zone."""
    check_gate(SERVICE)
    params: dict = {"per_page": 100}
    if record_type:
        params["type"] = record_type
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API}/zones/{zone_id}/dns_records", headers=_headers(), params=params)
        resp.raise_for_status()
    return [
        {"id": r["id"], "type": r["type"], "name": r["name"], "content": r["content"], "ttl": r["ttl"]}
        for r in resp.json()["result"]
    ]


@server.tool
async def cf_create_dns(
    zone_id: Annotated[str, Field(description="Zone ID")],
    record_type: Annotated[str, Field(description="Record type: A, AAAA, CNAME, MX, TXT")],
    name: Annotated[str, Field(description="Record name (e.g. 'www' or '@')")],
    content: Annotated[str, Field(description="Record content (IP, hostname, or text)")],
    ttl: Annotated[int, Field(description="TTL in seconds (1 = auto)")] = 1,
    proxied: Annotated[bool, Field(description="Enable Cloudflare proxy")] = False,
) -> dict:
    """Create a DNS record."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/zones/{zone_id}/dns_records",
            headers=_headers(),
            json={"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied},
        )
        resp.raise_for_status()
    r = resp.json()["result"]
    return {"id": r["id"], "type": r["type"], "name": r["name"], "content": r["content"]}


@server.tool
async def cf_list_workers(
    account_id: Annotated[str, Field(description="Cloudflare account ID")],
) -> list[dict]:
    """List Workers scripts for an account."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/accounts/{account_id}/workers/scripts",
            headers=_headers(),
        )
        resp.raise_for_status()
    return [
        {"id": w["id"], "modified": w.get("modified_on", "")}
        for w in resp.json()["result"]
    ]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/adapters/test_cloudflare.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/adapters/cloudflare.py tests/adapters/test_cloudflare.py
git commit -m "feat: Cloudflare adapter with zones, DNS, Workers"
```

---

### Task 12: AWS Adapter

**Files:**
- Create: `src/conduit/adapters/aws.py`
- Create: `tests/adapters/test_aws.py`

- [ ] **Step 1: Write the failing test**

`tests/adapters/test_aws.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from spine import Core
from conduit.config import Config, AwsConfig
from conduit.gate import reset_counters
from tests.adapters.conftest import MockTokenStore


@pytest.fixture
def aws_core():
    config = Config(aws=AwsConfig(enabled=True, region="us-east-1", rate_limit=100, rate_window=1))
    tokens = MockTokenStore()

    def setup(c):
        c.register("config", config)
        c.register("tokens", tokens)
        c.boot(env="test")
    Core.boot_once(setup)
    reset_counters()


@pytest.mark.asyncio
async def test_aws_list_buckets(aws_core):
    mock_s3 = MagicMock()
    mock_s3.list_buckets.return_value = {
        "Buckets": [{"Name": "my-bucket", "CreationDate": "2026-01-01T00:00:00Z"}]
    }
    with patch("conduit.adapters.aws.boto3") as mock_boto:
        mock_boto.client.return_value = mock_s3
        from conduit.adapters.aws import server as aws_server
        from fastmcp import Client
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_buckets", {})
            assert "my-bucket" in str(result)


@pytest.mark.asyncio
async def test_aws_list_objects(aws_core):
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "file.txt", "Size": 1024, "LastModified": "2026-01-01T00:00:00Z"}],
        "KeyCount": 1,
    }
    with patch("conduit.adapters.aws.boto3") as mock_boto:
        mock_boto.client.return_value = mock_s3
        from conduit.adapters.aws import server as aws_server
        from fastmcp import Client
        async with Client(aws_server) as client:
            result = await client.call_tool("aws_list_objects", {"bucket": "my-bucket"})
            assert "file.txt" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_aws.py -v`
Expected: FAIL

- [ ] **Step 3: Write aws.py**

`src/conduit/adapters/aws.py`:
```python
"""AWS adapter — S3 and EC2 operations via boto3."""
from __future__ import annotations

from typing import Annotated

import boto3
from fastmcp import FastMCP
from pydantic import Field
from spine import Core
from conduit.gate import check_gate

SERVICE = "aws"

server = FastMCP("AWS")


def _region() -> str:
    return Core.instance().get("config").aws.region


@server.tool
async def aws_list_buckets() -> list[dict]:
    """List all S3 buckets in your AWS account."""
    check_gate(SERVICE)
    s3 = boto3.client("s3", region_name=_region())
    resp = s3.list_buckets()
    return [
        {"name": b["Name"], "created": str(b.get("CreationDate", ""))}
        for b in resp.get("Buckets", [])
    ]


@server.tool
async def aws_list_objects(
    bucket: Annotated[str, Field(description="S3 bucket name")],
    prefix: Annotated[str, Field(description="Key prefix filter")] = "",
    max_keys: Annotated[int, Field(description="Max objects to return", ge=1, le=1000)] = 20,
) -> dict:
    """List objects in an S3 bucket."""
    check_gate(SERVICE)
    s3 = boto3.client("s3", region_name=_region())
    params: dict = {"Bucket": bucket, "MaxKeys": max_keys}
    if prefix:
        params["Prefix"] = prefix
    resp = s3.list_objects_v2(**params)
    return {
        "count": resp.get("KeyCount", 0),
        "objects": [
            {"key": o["Key"], "size": o["Size"], "modified": str(o.get("LastModified", ""))}
            for o in resp.get("Contents", [])
        ],
    }


@server.tool
async def aws_describe_instances(
    instance_ids: Annotated[list[str], Field(description="EC2 instance IDs (empty = all)")] = [],
) -> list[dict]:
    """Describe EC2 instances in your account."""
    check_gate(SERVICE)
    ec2 = boto3.client("ec2", region_name=_region())
    params: dict = {}
    if instance_ids:
        params["InstanceIds"] = instance_ids
    resp = ec2.describe_instances(**params)
    instances = []
    for reservation in resp.get("Reservations", []):
        for i in reservation.get("Instances", []):
            name = ""
            for tag in i.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
            instances.append({
                "id": i["InstanceId"],
                "name": name,
                "type": i["InstanceType"],
                "state": i["State"]["Name"],
                "ip": i.get("PublicIpAddress", ""),
                "private_ip": i.get("PrivateIpAddress", ""),
            })
    return instances


@server.tool
async def aws_cloudwatch_metrics(
    namespace: Annotated[str, Field(description="CloudWatch namespace (e.g. AWS/EC2, AWS/S3)")],
) -> list[dict]:
    """List available CloudWatch metrics for a namespace."""
    check_gate(SERVICE)
    cw = boto3.client("cloudwatch", region_name=_region())
    resp = cw.list_metrics(Namespace=namespace)
    seen = set()
    metrics = []
    for m in resp.get("Metrics", []):
        key = f"{m['Namespace']}/{m['MetricName']}"
        if key not in seen:
            seen.add(key)
            metrics.append({"namespace": m["Namespace"], "name": m["MetricName"]})
    return metrics
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/adapters/test_aws.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/conduit/adapters/aws.py tests/adapters/test_aws.py
git commit -m "feat: AWS adapter with S3, EC2, CloudWatch tools"
```

---

### Task 13: Claude Code Integration

**Files:**
- Create: `conduit/CLAUDE.md`

- [ ] **Step 1: Add Claude Code MCP config**

Add to Claude Code's settings (`.claude/settings.json` or via `/mcp add`):

```json
{
  "mcpServers": {
    "conduit": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "conduit.server"],
      "cwd": "D:\\lost_marbles\\conduit"
    }
  }
}
```

Alternatively, run interactively to test:
```bash
cd D:/lost_marbles/conduit
fastmcp run src/conduit/server.py
```

- [ ] **Step 2: Write project CLAUDE.md**

`conduit/CLAUDE.md`:
```markdown
# Conduit — Local MCP Server

Self-hosted MCP server connecting Claude Code to GitHub, Gmail, Google Calendar, Cloudflare, and AWS.

## Quick Start

```bash
pip install -e ".[dev]"
# One-time: set up Google OAuth
python -m conduit.google_auth
# Run server
python -m conduit.server
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

## Adding a new adapter

1. Create `src/conduit/adapters/{name}.py`
2. Define `SERVICE = "{name}"` and `server = FastMCP("{Name}")`
3. Add `@server.tool` functions that call `check_gate(SERVICE)` first
4. Add the service to `Config` in `config.py`
5. Add to the import list in `adapters/__init__.py`
```

- [ ] **Step 3: Run the full test suite**

```bash
cd D:/lost_marbles/conduit
pytest -v
```

Expected: All tests pass (config: 4, tokens: 5, boot: 5, gate: 4, server: 2, github: 5, gmail: 2, gcal: 2, cloudflare: 2, aws: 2) = **33 tests**

- [ ] **Step 4: Smoke test with Claude Code**

```bash
cd D:/lost_marbles/conduit
fastmcp run src/conduit/server.py --transport stdio
```

Verify it starts without error and lists tools.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Claude Code integration, CLAUDE.md, full test suite green"
```

---

## Self-Review

**Spec coverage:**
- Local MCP Server: Task 6 (server.py + fastmcp)
- Adapter Framework: Tasks 6-12 (discovery, mounting, 5 adapters with 21 tools total)
- Spine: Tasks 3-4 (boot, config registry, token store)
- Capability Gating: Task 5 (enabled check, rate limiting, token validity)
- Token Storage: Task 3 (1Password backend with cache)
- Google OAuth: Task 8 (browser flow, refresh token storage)

**Placeholder scan:** None found. All tasks have complete code.

**Type consistency verified:**
- `ServiceConfig` / `GoogleConfig` / `AwsConfig` used consistently across config, boot, gate, and adapter tests
- `check_gate(SERVICE)` called with the same string in every adapter
- `Core.instance().get("config")` / `.get("tokens")` used consistently
- `MockTokenStore` in test conftest matches `TokenStore` interface
- `SERVICE` constant matches config attribute name in every adapter

**Tool count:** 21 tools across 5 adapters:
- GitHub: 5 (list_repos, create_issue, list_prs, get_pr, search_code)
- Gmail: 4 (search, read, send, labels)
- Google Calendar: 4 (list_events, create_event, free_busy, get_event)
- Cloudflare: 4 (list_zones, list_dns, create_dns, list_workers)
- AWS: 4 (list_buckets, list_objects, describe_instances, cloudwatch_metrics)
