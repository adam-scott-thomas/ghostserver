"""Spine bootstrap. Call boot() once at server startup."""
from __future__ import annotations

from pathlib import Path

from spine import Core

from ghostserver.config import Config, load_config
from ghostserver.tokens import (
    EnvBackend,
    FileBackend,
    OpBackend,
    TokenStore,
)

DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "ghostserver.toml"


def _make_token_store(config: Config) -> TokenStore:
    backend_name = config.server.credential_backend
    if backend_name == "auto":
        return TokenStore()  # auto-detect
    elif backend_name == "op":
        return TokenStore(backend=OpBackend())
    elif backend_name == "env":
        return TokenStore(backend=EnvBackend())
    elif backend_name == "file":
        path = str(Path(config.server.credential_file).expanduser())
        return TokenStore(backend=FileBackend(path))
    else:
        raise ValueError(f"Unknown credential backend: {backend_name}")


def boot(config_path: Path | None = None) -> Core:
    if config_path is None:
        config_path = DEFAULT_CONFIG

    config = load_config(config_path)

    def setup(c: Core) -> None:
        c.register("config", config)
        c.register("tokens", _make_token_store(config))
        c.boot(env="prod")

    return Core.boot_once(setup)
