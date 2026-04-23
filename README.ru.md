# GhostServer

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Русский** · [Deutsch](README.de.md)

Self-hosted MCP-сервер, который подключает любой AI-инструмент к вашим реальным учётным записям. Токены никогда не покидают вашу машину.

Работает с Claude Code, Cursor, VS Code Copilot, Windsurf и любым клиентом, совместимым с MCP.

## Зачем это нужно

Почти любой «MCP-сервер», что сегодня встречается, — это либо мастер настройки, направленный в чужое облако, либо решение, привязанное к одному AI-вендору. GhostServer запускается локально, хранит учётные данные в вашем собственном `vault` и говорит по стандартному протоколу MCP, поэтому его может использовать любой клиент.

## 21 инструмент, 5 сервисов

| Сервис | Инструменты |
|---------|-------|
| **GitHub** | список репозиториев, создание issue, список/получение PR, поиск по коду |
| **Gmail** | поиск, чтение, отправка, список меток |
| **Google Calendar** | список событий, создание события, free/busy, получение события |
| **Cloudflare** | список зон, DNS-записи, создание DNS, список Workers |
| **AWS** | бакеты и объекты S3, инстансы EC2, метрики CloudWatch |

## Установка

```bash
pip install ghostserver
```

Или из исходников:

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## Быстрый старт

### 1. Настройка

```bash
cp ghostserver.toml.example ghostserver.toml
```

Отредактируйте `ghostserver.toml` — включите нужные сервисы и задайте ссылки на учётные данные.

### 2. Хранение учётных данных

GhostServer поддерживает три бэкенда для учётных данных.

**Переменные окружения** (самый простой вариант):
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

**Файл с учётными данными** (без засорения окружения):
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

**1Password CLI** (самый безопасный вариант):
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**Автоопределение** (по умолчанию): сначала пробуется 1Password, затем файл с учётными данными, затем переменные окружения.

### 3. Сервисы Google (однократная настройка)

Gmail и Google Calendar требуют OAuth. Запустите мастер один раз:

```bash
python -m ghostserver.google_auth
```

Откроется браузер, вы дадите согласие, и refresh-токен будет сохранён в выбранный бэкенд.

### 4. Подключение к вашему AI-инструменту

**Claude Code:**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code:**
Добавьте в настройки MCP:
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**Любой MCP-клиент (stdio):**
```bash
python -m ghostserver
```

## Архитектура

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

Каждый адаптер — это один файл. `gate` применяет ограничение частоты запросов для каждого сервиса. `spine` предоставляет замороженный singleton конфигурации, поэтому адаптерам не нужно передавать объекты друг другу.

## Как добавить собственный адаптер

Создайте `src/ghostserver/adapters/myservice.py`:

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

Добавьте конфигурацию сервиса в `config.py`, имя модуля — в `adapters/__init__.py`, и готово. Присылайте PR.

## Разработка

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## Лицензия

Apache 2.0
