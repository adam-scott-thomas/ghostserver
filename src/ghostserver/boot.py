"""Spine bootstrap. Call boot() once at server startup."""
from __future__ import annotations

from pathlib import Path

from spine import Core

from ghostserver.config import load_config
from ghostserver.tokens import TokenStore

DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "ghostserver.toml"


def boot(config_path: Path | None = None) -> Core:
    if config_path is None:
        config_path = DEFAULT_CONFIG

    config = load_config(config_path)

    def setup(c: Core) -> None:
        c.register("config", config)
        c.register("tokens", TokenStore())
        c.boot(env="prod")

    return Core.boot_once(setup)
