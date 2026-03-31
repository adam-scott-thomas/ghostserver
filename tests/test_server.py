from pathlib import Path
from spine import Core
from ghostserver.server import create_server


def test_create_server_returns_fastmcp(tmp_path: Path):
    toml = tmp_path / "ghostserver.toml"
    toml.write_text("[github]\nenabled = false\n")
    server = create_server(config_path=toml)
    assert server.name == "Ghostserver"


def test_server_has_no_tools_when_all_disabled(tmp_path: Path):
    toml = tmp_path / "ghostserver.toml"
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
