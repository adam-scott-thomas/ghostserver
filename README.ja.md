# GhostServer

[English](README.md) · [中文](README.zh-CN.md) · **日本語** · [한국어](README.ko.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

あらゆる AI ツールを実際のアカウントに接続する、セルフホスト型の MCP サーバーです。トークンがマシンの外に出ることはありません。

Claude Code、Cursor、VS Code Copilot、Windsurf、その他 MCP 対応クライアントで動作します。

## なぜ必要か

世に出回っている「MCP サーバー」は、他社クラウドを指し示すだけのセットアップウィザードか、特定の AI ベンダーに縛られたものばかりです。GhostServer はローカルで動作し、認証情報をあなた自身のボールトに保存し、標準 MCP プロトコルを話すため、どのクライアントからでも利用できます。

## 21 のツール、5 つのサービス

| サービス | ツール |
|---------|-------|
| **GitHub** | リポジトリ一覧、Issue 作成、PR の一覧/取得、コード検索 |
| **Gmail** | 検索、読み取り、送信、ラベル一覧 |
| **Google Calendar** | イベント一覧、イベント作成、Free/Busy、イベント取得 |
| **Cloudflare** | ゾーン一覧、DNS レコード、DNS 作成、Workers 一覧 |
| **AWS** | S3 バケット/オブジェクト、EC2 インスタンス、CloudWatch メトリクス |

## インストール

```bash
pip install ghostserver
```

またはソースから：

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
```

## クイックスタート

### 1. 設定

```bash
cp ghostserver.toml.example ghostserver.toml
```

`ghostserver.toml` を編集し、使用するサービスを有効にして、認証情報への参照を設定します。

### 2. 認証情報の保存

GhostServer は 3 種類の認証情報バックエンドに対応しています。

**環境変数**（最もシンプル）:
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

**認証情報ファイル**（環境変数を汚さない）:
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

**1Password CLI**（最も安全）:
```toml
[server]
credential_backend = "op"

[github]
enabled = true
token_ref = "op://Development/GitHub PAT/credential"
```

**自動検出**（デフォルト）: 1Password、認証情報ファイル、環境変数の順に試します。

### 3. Google サービス（初回のみ設定）

Gmail と Google Calendar には OAuth が必要です。一度だけセットアップウィザードを実行してください。

```bash
python -m ghostserver.google_auth
```

ブラウザが開いて同意を求められ、リフレッシュトークンが選択したバックエンドに保存されます。

### 4. AI ツールへの接続

**Claude Code:**
```bash
claude mcp add --transport stdio ghostserver -- python -m ghostserver
```

**Cursor / VS Code:**
MCP 設定に追加します:
```json
{
  "ghostserver": {
    "command": "python",
    "args": ["-m", "ghostserver"]
  }
}
```

**任意の MCP クライアント（stdio）:**
```bash
python -m ghostserver
```

## アーキテクチャ

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

各アダプターは単一ファイルです。`gate` はサービスごとにレート制限を適用します。`spine` は凍結された設定シングルトンを提供し、アダプター間でオブジェクトを受け渡す必要をなくします。

## 独自アダプターの追加

`src/ghostserver/adapters/myservice.py` を作成します。

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

サービス設定を `config.py` に追加し、モジュール名を `adapters/__init__.py` に追加すれば完了です。PR をお待ちしています。

## 開発

```bash
git clone https://github.com/adam-scott-thomas/ghostserver.git
cd ghostserver
pip install -e ".[dev]"
pytest -v
```

## ライセンス

Apache 2.0
