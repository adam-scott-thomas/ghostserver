# GhostServer

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Русский](README.ru.md) · **Deutsch**

Selbstgehosteter MCP-Server, der jedes AI-Tool mit deinen echten Konten verbindet. Deine Tokens verlassen deine Maschine nie.

Funktioniert mit Claude Code, Cursor, VS Code Copilot, Windsurf und jedem MCP-kompatiblen Client.

## Warum

Jeder „MCP-Server" da draußen ist entweder ein Einrichtungs-Assistent, der auf die Cloud von jemand anderem zeigt, oder an einen einzigen AI-Anbieter gebunden. GhostServer läuft lokal, speichert Credentials in deinem eigenen Vault und spricht das Standard-MCP-Protokoll, sodass jeder Client ihn verwenden kann.

## 21 Tools, 5 Dienste

| Dienst | Tools |
|---------|-------|
| **GitHub** | Repositories auflisten, Issues anlegen, PRs auflisten/abrufen, Code durchsuchen |
| **Gmail** | Suchen, Lesen, Senden, Labels auflisten |
| **Google Calendar** | Termine auflisten, Termine anlegen, Free/Busy, Termin abrufen |
| **Cloudflare** | Zonen auflisten, DNS-Einträge, DNS anlegen, Workers auflisten |
| **AWS** | S3-Buckets/Objekte, EC2-Instanzen, CloudWatch-Metriken |

## Installation

```bash
pip install ghostserver
```

Oder aus dem Quellcode:

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## Schnellstart

### 1. Konfigurieren

```bash
cp ghostserver.toml.example ghostserver.toml
```

Bearbeite `ghostserver.toml` — aktiviere die gewünschten Dienste und setze deine Credential-Referenzen.

### 2. Credentials speichern

GhostServer unterstützt drei Credential-Backends.

**Umgebungsvariablen** (am einfachsten):
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

**Credentials-Datei** (ohne Env zu verschmutzen):
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

**1Password CLI** (am sichersten):
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**Automatisch erkennen** (Standard): probiert zuerst 1Password, dann die Credentials-Datei, dann Umgebungsvariablen.

### 3. Google-Dienste (einmalige Einrichtung)

Gmail und Google Calendar benötigen OAuth. Führe den Einrichtungs-Assistenten einmalig aus:

```bash
python -m ghostserver.google_auth
```

Das öffnet deinen Browser, holt die Zustimmung ein und speichert das Refresh-Token in deinem gewählten Backend.

### 4. Mit deinem AI-Tool verbinden

**Claude Code:**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code:**
Ergänze deine MCP-Einstellungen:
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**Beliebiger MCP-Client (stdio):**
```bash
python -m ghostserver
```

## Architektur

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

Jeder Adapter ist eine einzelne Datei. Das `gate` erzwingt Rate-Limits pro Dienst. `spine` stellt den eingefrorenen Config-Singleton bereit, damit Adapter keine Objekte herumreichen müssen.

## Eigenen Adapter hinzufügen

Lege `src/ghostserver/adapters/myservice.py` an:

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

Ergänze die Dienst-Konfiguration in `config.py`, füge den Modulnamen in `adapters/__init__.py` ein — fertig. Schick einen PR.

## Entwicklung

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## Lizenz

Apache 2.0
