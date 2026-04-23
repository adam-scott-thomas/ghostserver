# GhostServer

[English](README.md) · **中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

自托管 MCP 服务器，将任意 AI 工具连接到你真实的账户。令牌永远不会离开你的机器。

可与 Claude Code、Cursor、VS Code Copilot、Windsurf 以及任何兼容 MCP 的客户端配合使用。

## 为什么

市面上的"MCP 服务器"要么是指向他人云端的配置向导，要么被锁定到单一 AI 厂商。GhostServer 在本地运行，将凭据存储在你自己的 `vault` 中，并遵循标准 MCP 协议，因此任何客户端都可以使用它。

## 21 个工具，5 项服务

| 服务 | 工具 |
|---------|-------|
| **GitHub** | 列出仓库、创建议题、列出/获取 PR、搜索代码 |
| **Gmail** | 搜索、读取、发送、列出标签 |
| **Google Calendar** | 列出事件、创建事件、查询空闲/忙碌、获取事件 |
| **Cloudflare** | 列出 zone、DNS 记录、创建 DNS、列出 Workers |
| **AWS** | S3 存储桶/对象、EC2 实例、CloudWatch 指标 |

## 安装

```bash
pip install ghostserver
```

或从源码安装：

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## 快速开始

### 1. 配置

```bash
cp ghostserver.toml.example ghostserver.toml
```

编辑 `ghostserver.toml` —— 启用你需要的服务，并设置凭据引用。

### 2. 存储凭据

GhostServer 支持三种凭据后端：

**环境变量**（最简单）：
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

**凭据文件**（避免污染环境变量）：
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

**1Password CLI**（最安全）：
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**自动检测**（默认）：依次尝试 1Password、凭据文件、环境变量。

### 3. Google 服务（一次性设置）

Gmail 和 Google Calendar 需要 OAuth。只需运行一次设置向导：

```bash
python -m ghostserver.google_auth
```

它会打开浏览器、获取授权，并将刷新令牌存入你选择的后端。

### 4. 连接到你的 AI 工具

**Claude Code：**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code：**
添加到 MCP 设置中：
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**任何 MCP 客户端（stdio）：**
```bash
python -m ghostserver
```

## 架构

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

每个适配器都是单个文件。`gate` 按服务强制执行速率限制。`spine` 提供冻结的配置单例，因此适配器之间无需传递对象。

## 添加你自己的适配器

创建 `src/ghostserver/adapters/myservice.py`：

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

将服务配置加入 `config.py`，把模块名加入 `adapters/__init__.py`，即可完成。欢迎提交 PR。

## 开发

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## 许可证

Apache 2.0
