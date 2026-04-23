# GhostServer

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · **한국어** · [Русский](README.ru.md) · [Deutsch](README.de.md)

모든 AI 도구를 실제 계정에 연결해 주는 자체 호스팅 MCP 서버입니다. 토큰은 절대로 기기를 벗어나지 않습니다.

Claude Code, Cursor, VS Code Copilot, Windsurf 등 MCP 호환 클라이언트에서 모두 동작합니다.

## 왜 필요한가

시중의 "MCP 서버"는 대부분 다른 회사 클라우드를 가리키는 설정 마법사이거나, 특정 AI 공급업체에 묶여 있습니다. GhostServer는 로컬에서 실행되고, 자격 증명을 사용자의 `vault`에 저장하며, 표준 MCP 프로토콜을 사용하기 때문에 어떤 클라이언트든 그대로 쓸 수 있습니다.

## 도구 21개, 서비스 5개

| 서비스 | 도구 |
|---------|-------|
| **GitHub** | 저장소 목록, 이슈 생성, PR 목록/조회, 코드 검색 |
| **Gmail** | 검색, 읽기, 보내기, 라벨 목록 |
| **Google Calendar** | 일정 목록, 일정 생성, free/busy 조회, 일정 조회 |
| **Cloudflare** | 존 목록, DNS 레코드, DNS 생성, Workers 목록 |
| **AWS** | S3 버킷/오브젝트, EC2 인스턴스, CloudWatch 지표 |

## 설치

```bash
pip install ghostserver
```

또는 소스에서 설치:

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## 빠른 시작

### 1. 설정

```bash
cp ghostserver.toml.example ghostserver.toml
```

`ghostserver.toml`을 편집하여 사용할 서비스를 활성화하고 자격 증명 참조를 설정합니다.

### 2. 자격 증명 저장

GhostServer는 세 가지 자격 증명 백엔드를 지원합니다.

**환경 변수**(가장 단순):
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

**자격 증명 파일**(환경 변수 오염 없음):
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

**1Password CLI**(가장 안전):
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**자동 감지**(기본값): 1Password, 자격 증명 파일, 환경 변수 순으로 시도합니다.

### 3. Google 서비스(최초 1회 설정)

Gmail과 Google Calendar는 OAuth가 필요합니다. 설정 마법사를 한 번만 실행합니다.

```bash
python -m ghostserver.google_auth
```

브라우저가 열려 동의 절차를 거치고, 리프레시 토큰이 선택한 백엔드에 저장됩니다.

### 4. AI 도구에 연결

**Claude Code:**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code:**
MCP 설정에 다음을 추가합니다.
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**임의의 MCP 클라이언트(stdio):**
```bash
python -m ghostserver
```

## 아키텍처

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

어댑터는 모두 단일 파일입니다. `gate`가 서비스별 속도 제한을 적용합니다. `spine`은 동결된 설정 싱글톤을 제공하므로 어댑터끼리 객체를 주고받을 필요가 없습니다.

## 직접 어댑터 추가하기

`src/ghostserver/adapters/myservice.py` 파일을 생성합니다.

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

`config.py`에 서비스 설정을 추가하고 `adapters/__init__.py`에 모듈 이름을 추가하면 끝입니다. PR을 보내 주세요.

## 개발

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## 라이선스

Apache 2.0
