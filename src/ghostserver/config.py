"""Configuration dataclasses and TOML loader."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServiceConfig:
    enabled: bool = False
    token_ref: str = ""
    rate_limit: int = 5000
    rate_window: int = 3600


@dataclass
class GoogleConfig:
    enabled: bool = False
    client_id_ref: str = ""
    client_secret_ref: str = ""
    refresh_token_ref: str = ""
    scopes: list[str] = field(default_factory=list)
    rate_limit: int = 500
    rate_window: int = 100


@dataclass
class AwsConfig:
    enabled: bool = False
    region: str = "us-east-1"
    rate_limit: int = 100
    rate_window: int = 1


@dataclass
class ServerConfig:
    credential_backend: str = "auto"
    credential_file: str = "~/.ghostserver/credentials"


@dataclass
class Config:
    github: ServiceConfig = field(default_factory=ServiceConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)
    cloudflare: ServiceConfig = field(default_factory=ServiceConfig)
    aws: AwsConfig = field(default_factory=AwsConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    def service_names(self) -> list[str]:
        return ["github", "google", "cloudflare", "aws"]

    def rate_for(self, service: str) -> tuple[int, int]:
        svc = getattr(self, service)
        return svc.rate_limit, svc.rate_window

    def is_enabled(self, service: str) -> bool:
        return getattr(self, service).enabled


def load_config(path: Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(
        github=ServiceConfig(**raw.get("github", {})),
        google=GoogleConfig(**raw.get("google", {})),
        cloudflare=ServiceConfig(**raw.get("cloudflare", {})),
        aws=AwsConfig(**raw.get("aws", {})),
        server=ServerConfig(**raw.get("server", {})),
    )
