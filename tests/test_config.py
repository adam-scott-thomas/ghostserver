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
