import time
from unittest.mock import MagicMock
from spine import Core
from ghostserver.gate import check_gate, ServiceDisabled, RateLimitExceeded, reset_counters
from ghostserver.config import Config, ServiceConfig


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
    import ghostserver.gate as gm
    gm._windows["github"] = [time.time() - 2]
    check_gate("github")  # should pass — old entry expired
