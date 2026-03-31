import pytest
from unittest.mock import MagicMock
from spine import Core
from ghostserver.config import Config, ServiceConfig, GoogleConfig, AwsConfig
from ghostserver.gate import reset_counters


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
