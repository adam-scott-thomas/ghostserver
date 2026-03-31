"""Credential backends for GhostServer."""
from __future__ import annotations

import os
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import TimeoutExpired

import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class CredentialBackend(ABC):
    """Base class for credential storage."""

    @abstractmethod
    def read(self, ref: str) -> str:
        """Read a credential by reference string."""
        ...


class EnvBackend(CredentialBackend):
    """Read credentials from environment variables.

    Ref format: env var name (e.g. "GITHUB_TOKEN").
    Config example: token_ref = "GITHUB_TOKEN"
    """

    def read(self, ref: str) -> str:
        value = os.environ.get(ref, "")
        if not value:
            raise RuntimeError(f"Environment variable '{ref}' is not set")
        return value


class OpBackend(CredentialBackend):
    """Read credentials from 1Password CLI.

    Ref format: op:// secret reference (e.g. "op://Vault/Item/Field").
    Requires `op` CLI to be installed and authenticated.
    """

    def read(self, ref: str) -> str:
        result = subprocess.run(
            ["op", "read", ref],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"1Password read failed: {result.stderr.strip()}")
        return result.stdout.strip()


class FileBackend(CredentialBackend):
    """Read credentials from a dotenv-style file.

    Ref format: KEY_NAME (looks up in the credentials file).
    File format: KEY=VALUE, one per line. Lines starting with # are comments.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        self._data[key.strip()] = value.strip()
        except FileNotFoundError:
            pass

    def read(self, ref: str) -> str:
        if ref not in self._data:
            raise RuntimeError(f"Key '{ref}' not found in {self._path}")
        return self._data[ref]


class TokenStore:
    """Cached credential access with Google OAuth refresh support."""

    def __init__(self, backend: CredentialBackend | None = None) -> None:
        self._backend = backend or _auto_detect_backend()
        self._cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl: float = 300.0

    def get(self, ref: str) -> str:
        now = time.time()
        if ref in self._cache:
            token, cached_at = self._cache[ref]
            if now - cached_at < self._cache_ttl:
                return token

        token = self._backend.read(ref)
        self._cache[ref] = (token, now)
        return token

    def refresh_google(
        self, client_id: str, client_secret: str, refresh_token: str,
    ) -> str:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def clear_cache(self) -> None:
        self._cache.clear()

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__


def _auto_detect_backend() -> CredentialBackend:
    """Pick the best available backend automatically.

    Priority:
    1. 1Password CLI (if `op` is on PATH)
    2. Credentials file (~/.ghostserver/credentials)
    3. Environment variables (always available)
    """
    # Check for 1Password
    try:
        result = subprocess.run(
            ["op", "--version"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return OpBackend()
    except (FileNotFoundError, TimeoutExpired):
        pass

    # Check for credentials file
    cred_file = Path.home() / ".ghostserver" / "credentials"
    if cred_file.exists():
        return FileBackend(str(cred_file))

    # Fallback to env vars
    return EnvBackend()
